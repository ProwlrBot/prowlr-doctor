"""Rich terminal report renderer (--no-tui mode)."""
from __future__ import annotations

from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from rich import box

from prowlr_doctor.models import Finding, Recommendations, Severity, TokenBudget
from prowlr_doctor import tokens

_SEVERITY_STYLE = {
    Severity.CRITICAL: "[bold red]● CRITICAL[/]",
    Severity.HIGH:     "[bold yellow]◆ HIGH    [/]",
    Severity.MEDIUM:   "[yellow]◆ MEDIUM  [/]",
    Severity.INFO:     "[dim]ℹ INFO    [/]",
}

_SEVERITY_COLOR = {
    Severity.CRITICAL: "red",
    Severity.HIGH:     "yellow",
    Severity.MEDIUM:   "yellow",
    Severity.INFO:     "dim",
}


def render(
    findings: list[Finding],
    budget: TokenBudget,
    rec: Recommendations,
    console: Console | None = None,
) -> None:
    con = console or Console()

    con.print()
    con.print(Rule("[bold cyan]ProwlrDoctor v0.1[/bold cyan]"))
    con.print(
        f"  Profile: [bold]{rec.profile}[/bold]  ·  "
        f"Findings: [bold]{len(findings)}[/bold]  ·  "
        f"Auto-fixable: [bold]{len(rec.disable)}[/bold]"
    )
    con.print()

    if not findings:
        con.print("  [bold green]✓ Environment looks clean![/bold green]")
    else:
        for f in sorted(findings, key=lambda x: -x.severity):
            badge = _SEVERITY_STYLE.get(f.severity, str(f.severity))
            wasted = f"  [dim]{tokens.display(f.tokens_wasted)} t wasted[/dim]" if f.tokens_wasted else ""
            con.print(f"  {badge}  {f.title}{wasted}")
            con.print(f"         [dim]{f.explainability}[/dim]")
            if f.fix_action and f.fix_action.action_type not in ("condense",):
                con.print(f"         [dim cyan]Fix: {f.fix_action.action_type} {f.fix_action.target}[/dim cyan]")
            con.print()

    _render_budget(con, budget)

    if rec.disable:
        con.print(
            f"  [dim]Run [cyan]prowlr-doctor --write-plan[/cyan] then "
            f"[cyan]prowlr-doctor --apply[/cyan] to save {tokens.display(budget.savings_if_cleaned)} tokens/session[/dim]"
        )
    con.print()


def _render_budget(con: Console, budget: TokenBudget) -> None:
    con.print(Rule("[dim]Token Budget[/dim]"))
    rows = [
        ("Session fixed", budget.per_session_fixed),
        ("Per-turn (×20)", budget.per_turn_recurring * 20),
        ("20-turn estimate", budget.session_estimate_20turn),
        ("Wasted (duplicates)", budget.wasted),
        ("Savings potential", budget.savings_if_cleaned),
    ]
    for label, value in rows:
        color = "red" if "Wasted" in label or "Savings" in label else "white"
        con.print(f"  {label:<26} [{color}]{tokens.display(value):>8}[/{color}] tokens")
    con.print()
