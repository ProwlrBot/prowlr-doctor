"""Click CLI entry point for prowlr-doctor."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from prowlr_doctor import paths, telemetry
from prowlr_doctor.scanner import load_snapshot, run_audit
from prowlr_doctor.recommender import recommend
from prowlr_doctor.patch_planner import build_plan, apply_plan
from prowlr_doctor.reporter import render


@click.command("prowlr-doctor")
@click.option(
    "--profile",
    default="developer",
    type=click.Choice(["developer", "security", "minimal", "agent-builder", "research"]),
    show_default=True,
    help="Recommendation profile.",
)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable JSON output.")
@click.option("--write-plan", is_flag=True, help="Write fix plan to ~/.claude/doctor-plan.json.")
@click.option("--diff", is_flag=True, help="Show settings.json diff from plan on disk.")
@click.option("--apply", is_flag=True, help="Apply plan at ~/.claude/doctor-plan.json.")
@click.option("--no-tui", is_flag=True, help="Rich report only (no Textual app).")
@click.option("--opt-in-telemetry", is_flag=True, help="Opt in to anonymous aggregate telemetry.")
@click.option("--opt-out-telemetry", is_flag=True, help="Opt out of telemetry.")
@click.version_option(package_name="prowlr-doctor")
def main(
    profile: str,
    as_json: bool,
    write_plan: bool,
    diff: bool,
    apply: bool,
    no_tui: bool,
    opt_in_telemetry: bool,
    opt_out_telemetry: bool,
) -> None:
    """Audit your Claude Code environment for token waste and security issues."""
    if opt_in_telemetry:
        telemetry.opt_in()
        click.echo("Telemetry enabled. Thank you — your aggregate data helps improve ProwlrDoctor.")
        click.echo("No PII is collected. No file paths, no plugin names, counts only.")
        return
    if opt_out_telemetry:
        telemetry.opt_out()
        click.echo("Telemetry disabled.")
        return

    if apply:
        _cmd_apply()
        return

    if diff:
        _cmd_diff()
        return

    env = load_snapshot()
    findings, budget = run_audit(env)
    rec = recommend(findings, profile)
    telemetry.maybe_send(env, findings, budget, profile)

    if as_json or write_plan:
        plan = build_plan(env, rec)
        output = _build_json_output(env, findings, budget, rec, plan)

        if as_json:
            click.echo(json.dumps(output, indent=2))
            # Always write cache for statusline
            cache = paths.doctor_cache_path()
            cache.write_text(json.dumps(output, indent=2))

        if write_plan:
            plan_path = paths.doctor_plan_path()
            plan_path.write_text(plan.to_json())
            click.echo(f"Plan written to {plan_path}")
            click.echo(f"  {len(plan.actions)} actions  ·  saves {budget.savings_if_cleaned:,} tokens/session")
            click.echo(f"Run: prowlr-doctor --diff   to preview")
            click.echo(f"Run: prowlr-doctor --apply  to apply")
        return

    if no_tui:
        render(findings, budget, rec)
        return

    # Default: try TUI, fall back to Rich report
    try:
        from prowlr_doctor.tui.app import EnvDoctorApp
        plan = build_plan(env, rec)
        app = EnvDoctorApp(findings=findings, budget=budget, rec=rec, plan=plan)
        app.run()
    except ImportError:
        click.echo(
            "[dim]Textual not installed — falling back to Rich report. "
            "Install with: pip install prowlr-doctor[tui][/dim]"
        )
        render(findings, budget, rec)


def _cmd_apply() -> None:
    plan_path = paths.doctor_plan_path()
    if not plan_path.exists():
        click.echo(
            f"No plan found at {plan_path}.\n"
            "Run: prowlr-doctor --write-plan  to generate one first.",
            err=True,
        )
        sys.exit(1)

    from prowlr_doctor.models import PatchPlan
    data = json.loads(plan_path.read_text())
    # Reconstruct minimal plan for apply
    from prowlr_doctor.models import FixAction
    actions = [
        FixAction(
            action_type=a["action_type"],
            target=a["target"],
            settings_path=a.get("settings_path"),
            before=a["before"],
            after=a["after"],
            reversible=a.get("reversible", True),
            requires_restart=a.get("requires_restart", False),
        )
        for a in data.get("actions", [])
        if a.get("action_type") != "condense"
    ]
    plan = PatchPlan(
        version=data["version"],
        generated_at=data["generated_at"],
        profile=data["profile"],
        findings_count=data["findings_count"],
        actions=actions,
        estimated_savings=data["estimated_savings"],
        settings_diff=data["settings_diff"],
        plan_path=plan_path,
    )
    apply_plan(plan)
    click.echo(f"Applied {len(actions)} changes to settings.json.")
    click.echo(f"Backup saved. Restart Claude Code to pick up changes.")


def _cmd_diff() -> None:
    plan_path = paths.doctor_plan_path()
    if not plan_path.exists():
        click.echo(f"No plan found at {plan_path}. Run --write-plan first.", err=True)
        sys.exit(1)
    data = json.loads(plan_path.read_text())
    before = json.dumps(data["settings_diff"]["before"], indent=2).splitlines()
    after = json.dumps(data["settings_diff"]["after"], indent=2).splitlines()
    import difflib
    from rich.syntax import Syntax
    from prowlr_doctor.reporter import _make_console
    diff = "\n".join(difflib.unified_diff(before, after, fromfile="before", tofile="after", lineterm=""))
    _make_console().print(Syntax(diff, "diff", theme="monokai"))


def _build_json_output(env, findings, budget, rec, plan) -> dict:
    return {
        "version": "1",
        "generated_at": plan.generated_at,
        "profile": rec.profile,
        "environment": {
            "plugins_enabled": sum(1 for v in env.enabled_plugins.values() if v),
            "hooks_count": len(env.hooks),
            "mcp_servers": len(env.mcp_servers),
        },
        "token_budget": {
            "per_session_fixed": budget.per_session_fixed,
            "per_turn_recurring": budget.per_turn_recurring,
            "on_demand": budget.on_demand,
            "wasted": budget.wasted,
            "savings_if_cleaned": budget.savings_if_cleaned,
            "session_estimate_20turn": budget.session_estimate_20turn,
        },
        "findings": [
            {
                "id": f.id,
                "severity": f.severity.name.lower(),
                "category": f.category,
                "title": f.title,
                "tokens_wasted": f.tokens_wasted,
                "fix_action": {
                    "action_type": f.fix_action.action_type,
                    "target": f.fix_action.target,
                    "settings_path": f.fix_action.settings_path,
                    "before": f.fix_action.before,
                    "after": f.fix_action.after,
                    "reversible": f.fix_action.reversible,
                    "requires_restart": f.fix_action.requires_restart,
                } if f.fix_action else None,
            }
            for f in findings
        ],
        "recommendations": {
            "disable": [f.id for f in rec.disable],
            "review": [f.id for f in rec.review],
            "keep": [f.id for f in rec.keep],
            "condense": [f.id for f in rec.condense],
        },
    }
