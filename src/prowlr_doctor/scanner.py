"""Orchestrates all auditors → list[Finding] + TokenBudget."""
from __future__ import annotations

import json
from pathlib import Path

from prowlr_doctor import paths, tokens
from prowlr_doctor.models import EnvironmentSnapshot, Finding, TokenBudget
from prowlr_doctor.auditors.plugins import PluginsAuditor
from prowlr_doctor.auditors.hooks import HooksAuditor
from prowlr_doctor.auditors.agents import AgentsAuditor
from prowlr_doctor.auditors.mcp import McpAuditor
from prowlr_doctor.auditors.claude_md import ClaudeMdAuditor
from prowlr_doctor.auditors.memory import MemoryAuditor
from prowlr_doctor.auditors.security import SecurityAuditor


def load_snapshot(cwd: Path | None = None) -> EnvironmentSnapshot:
    """Parse ~/.claude/settings.json and surrounding environment into a snapshot."""
    sp = paths.settings_path()
    settings: dict = {}
    if sp.exists():
        try:
            settings = json.loads(sp.read_text())
        except Exception:
            pass

    enabled_plugins: dict[str, bool] = settings.get("enabledPlugins", {})
    mcp_servers: dict[str, dict] = settings.get("mcpServers", {})
    hooks: list[dict] = settings.get("hooks", [])

    cache_dir = paths.plugin_cache_dir()
    installed_plugin_dirs: dict[str, Path] = {}
    if cache_dir.exists():
        for plugin_id in enabled_plugins:
            # plugin cache dirs are typically named by plugin_id with @ replaced by /
            candidate = cache_dir / plugin_id.replace("@", "/")
            if candidate.exists():
                installed_plugin_dirs[plugin_id] = candidate
            else:
                # flat layout: just the plugin name before @
                name = plugin_id.split("@")[0]
                flat = cache_dir / name
                if flat.exists():
                    installed_plugin_dirs[plugin_id] = flat

    return EnvironmentSnapshot(
        settings_path=sp,
        settings=settings,
        enabled_plugins=enabled_plugins,
        mcp_servers=mcp_servers,
        hooks=hooks,
        plugin_cache_dir=cache_dir,
        global_claude_md=paths.global_claude_md(),
        project_claude_md=paths.project_claude_md_files(cwd),
        memory_files=paths.memory_files(),
        installed_plugin_dirs=installed_plugin_dirs,
    )


def run_audit(env: EnvironmentSnapshot) -> tuple[list[Finding], TokenBudget]:
    """Run all auditors against the snapshot. Returns (findings, budget)."""
    auditors = [
        PluginsAuditor(),
        HooksAuditor(),
        AgentsAuditor(),
        McpAuditor(),
        ClaudeMdAuditor(),
        MemoryAuditor(),
        SecurityAuditor(),
    ]
    all_findings: list[Finding] = []
    for auditor in auditors:
        try:
            all_findings.extend(auditor.audit(env))
        except Exception as exc:
            # Never let a buggy auditor crash the whole run
            all_findings.append(Finding(
                id=f"auditor-error-{type(auditor).__name__}",
                severity=__import__("prowlr_doctor.models", fromlist=["Severity"]).Severity.INFO,
                category="verbosity",
                title=f"Auditor error: {type(auditor).__name__}",
                detail=str(exc),
                explainability="An auditor raised an exception — report this as a bug.",
            ))

    budget = _compute_budget(env, all_findings)
    return all_findings, budget


def _compute_budget(env: EnvironmentSnapshot, findings: list[Finding]) -> TokenBudget:
    fixed = 0
    if env.global_claude_md:
        fixed += tokens.count_file(env.global_claude_md)
    for p in env.project_claude_md:
        fixed += tokens.count_file(p)
    for mem in env.memory_files:
        fixed += tokens.count_file(mem)

    # Per-turn: skill list overhead (~150 chars per enabled plugin agent)
    enabled_count = sum(1 for v in env.enabled_plugins.values() if v)
    per_turn = enabled_count * 50  # conservative: 50 tokens per plugin entry

    wasted = sum(f.tokens_wasted for f in findings if f.tokens_wasted > 0)

    budget = TokenBudget(
        per_session_fixed=fixed,
        per_turn_recurring=per_turn,
        on_demand=0,
        wasted=wasted,
        savings_if_cleaned=wasted,
    )
    budget.session_estimate_20turn = budget.compute_session_estimate()
    return budget
