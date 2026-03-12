"""Textual TUI app — full-screen htop/lazygit-style audit viewer."""
from __future__ import annotations

from typing import ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from prowlr_doctor.models import Finding, PatchPlan, Recommendations, Severity, TokenBudget
from prowlr_doctor import tokens as tok

_PROFILES = ["developer", "security", "minimal", "agent-builder", "research"]

_SEVER_BADGE = {
    Severity.CRITICAL: "● ",
    Severity.HIGH:     "◆ ",
    Severity.MEDIUM:   "◆ ",
    Severity.INFO:     "ℹ ",
}

_SEVER_CLASS = {
    Severity.CRITICAL: "critical",
    Severity.HIGH:     "high",
    Severity.MEDIUM:   "medium",
    Severity.INFO:     "info",
}


class SummaryBar(Static):
    """Top summary strip."""

    DEFAULT_CSS = """
    SummaryBar {
        background: $panel;
        color: $text;
        padding: 0 2;
        height: 1;
    }
    """

    def update_stats(
        self,
        findings: list[Finding],
        budget: TokenBudget,
        profile: str,
        approved: set[str],
    ) -> None:
        n_critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        n_high = sum(1 for f in findings if f.severity == Severity.HIGH)
        n_approved = len(approved)
        savings = sum(f.tokens_wasted for f in findings if f.id in approved)
        parts = [
            f"Profile: [bold]{profile}[/]",
            f"Findings: [bold]{len(findings)}[/]",
        ]
        if n_critical:
            parts.append(f"[red]● {n_critical} critical[/]")
        if n_high:
            parts.append(f"[yellow]◆ {n_high} high[/]")
        if n_approved:
            parts.append(f"[green]✓ {n_approved} approved ({tok.display(savings)} savings)[/]")
        self.update("  ·  ".join(parts))


class FindingItem(ListItem):
    """A single row in the findings list."""

    DEFAULT_CSS = """
    FindingItem {
        padding: 0 1;
        height: 1;
    }
    FindingItem.critical Label { color: $error; }
    FindingItem.high Label { color: $warning; }
    FindingItem.medium Label { color: $warning-darken-1; }
    FindingItem.info Label { color: $text-muted; }
    FindingItem.approved Label { color: $success; text-style: strike; }
    FindingItem.skipped Label { color: $text-disabled; text-style: strike; }
    """

    def __init__(self, finding: Finding) -> None:
        super().__init__()
        self.finding = finding
        sev_class = _SEVER_CLASS.get(finding.severity, "info")
        self.add_class(sev_class)
        badge = _SEVER_BADGE.get(finding.severity, "  ")
        truncated = finding.title[:48] + "…" if len(finding.title) > 48 else finding.title
        self._label = Label(f"{badge}{truncated}")

    def compose(self) -> ComposeResult:
        yield self._label

    def mark_approved(self) -> None:
        self.remove_class("skipped")
        self.add_class("approved")

    def mark_skipped(self) -> None:
        self.remove_class("approved")
        self.add_class("skipped")

    def mark_pending(self) -> None:
        self.remove_class("approved", "skipped")


class DetailPanel(Static):
    """Right panel — shows full detail for the selected finding."""

    DEFAULT_CSS = """
    DetailPanel {
        padding: 1 2;
        background: $surface;
        height: 100%;
        overflow-y: auto;
    }
    """

    def show_finding(self, finding: Finding | None, approved: set[str], skipped: set[str]) -> None:
        if finding is None:
            self.update("[dim]No findings[/dim]")
            return

        badge = _SEVER_BADGE.get(finding.severity, "  ")
        sev_name = finding.severity.name
        lines = [
            f"[bold]{badge}{finding.title}[/bold]",
            f"[dim]{sev_name}  ·  {finding.category}[/dim]",
            "",
            finding.detail,
            "",
            f"[italic dim]{finding.explainability}[/italic dim]",
        ]

        if finding.tokens_wasted:
            lines += ["", f"[yellow]Tokens wasted: {tok.display(finding.tokens_wasted)}/session[/yellow]"]

        if finding.fix_action:
            fa = finding.fix_action
            if fa.action_type == "condense":
                lines += ["", "[dim]Fix: manual edit required (cannot be auto-applied)[/dim]"]
            else:
                lines += [
                    "",
                    f"[cyan]Fix: {fa.action_type} → {fa.target}[/cyan]",
                    f"[dim]Reversible: {'yes' if fa.reversible else 'no'}[/dim]",
                ]
        else:
            lines += ["", "[dim]No automatic fix available[/dim]"]

        # Status
        if finding.id in approved:
            lines += ["", "[green]✓ APPROVED — will be applied on [A]pply[/green]"]
        elif finding.id in skipped:
            lines += ["", "[dim]↷ SKIPPED[/dim]"]
        else:
            lines += ["", "[dim]Pending — press [D] to approve, [S] to skip[/dim]"]

        self.update("\n".join(lines))

    def show_diff(self, plan: PatchPlan | None) -> None:
        if plan is None:
            self.update("[dim]No plan generated yet. Press [W] first.[/dim]")
            return
        import json, difflib
        before = json.dumps(plan.settings_diff["before"], indent=2).splitlines()
        after = json.dumps(plan.settings_diff["after"], indent=2).splitlines()
        diff_lines = list(difflib.unified_diff(before, after, fromfile="before", tofile="after", lineterm=""))
        if not diff_lines:
            self.update("[green]No changes — nothing to apply.[/green]")
            return
        rendered = []
        for line in diff_lines[:60]:  # cap at 60 lines in panel
            if line.startswith("+"):
                rendered.append(f"[green]{line}[/green]")
            elif line.startswith("-"):
                rendered.append(f"[red]{line}[/red]")
            else:
                rendered.append(f"[dim]{line}[/dim]")
        self.update("\n".join(rendered))


class StatusBar(Static):
    """Bottom token savings bar."""

    DEFAULT_CSS = """
    StatusBar {
        background: $panel;
        color: $text-muted;
        padding: 0 2;
        height: 1;
    }
    """

    def update_budget(self, budget: TokenBudget) -> None:
        parts = [
            f"Session: [bold]{tok.display(budget.session_estimate_20turn)}[/bold] (20 turns)",
            f"Wasted: [red]{tok.display(budget.wasted)}[/red]",
            f"Saveable: [yellow]{tok.display(budget.savings_if_cleaned)}[/yellow]",
        ]
        self.update("  ·  ".join(parts))


class EnvDoctorApp(App):
    """Full-screen ProwlrDoctor TUI."""

    TITLE = "ProwlrDoctor v0.1"

    CSS = """
    Screen {
        background: $background;
    }
    #main {
        height: 1fr;
    }
    #findings-pane {
        width: 40%;
        border-right: solid $panel-darken-2;
    }
    #findings-list {
        height: 1fr;
    }
    #detail-pane {
        width: 1fr;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Quit"),
        Binding("d", "approve", "Disable"),
        Binding("s", "skip", "Skip"),
        Binding("v", "view_diff", "Diff"),
        Binding("a", "apply_all", "Apply"),
        Binding("p", "cycle_profile", "Profile"),
        Binding("w", "write_plan", "Write plan"),
    ]

    current_profile: reactive[str] = reactive("developer")

    def __init__(
        self,
        findings: list[Finding],
        budget: TokenBudget,
        rec: Recommendations,
        plan: PatchPlan,
    ) -> None:
        super().__init__()
        self._findings = sorted(findings, key=lambda f: -f.severity)
        self._budget = budget
        self._rec = rec
        self._plan = plan
        self._approved: set[str] = set()
        self._skipped: set[str] = set()
        self.current_profile = rec.profile
        # Pre-approve all "disable" recommendations
        for f in rec.disable:
            if f.fix_action and f.fix_action.action_type != "condense":
                self._approved.add(f.id)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield SummaryBar(id="summary")
        with Horizontal(id="main"):
            with Vertical(id="findings-pane"):
                items = [FindingItem(f) for f in self._findings]
                yield ListView(*items, id="findings-list")
            yield DetailPanel(id="detail")
        yield StatusBar(id="status")
        yield Footer()

    def on_mount(self) -> None:
        # Apply initial approved styling after widgets are mounted
        for item in self.query(FindingItem):
            if item.finding.id in self._approved:
                item.mark_approved()
        self._refresh_summary()
        self._refresh_status()
        lv = self.query_one("#findings-list", ListView)
        if self._findings:
            lv.index = 0
            self._show_finding(self._findings[0])

    @on(ListView.Highlighted)
    def on_list_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and isinstance(event.item, FindingItem):
            self._show_finding(event.item.finding)

    def _show_finding(self, finding: Finding) -> None:
        self.query_one("#detail", DetailPanel).show_finding(
            finding, self._approved, self._skipped
        )

    def _current_finding(self) -> Finding | None:
        lv = self.query_one("#findings-list", ListView)
        if lv.highlighted_child and isinstance(lv.highlighted_child, FindingItem):
            return lv.highlighted_child.finding
        return None

    def _current_item(self) -> FindingItem | None:
        lv = self.query_one("#findings-list", ListView)
        if isinstance(lv.highlighted_child, FindingItem):
            return lv.highlighted_child
        return None

    def action_approve(self) -> None:
        finding = self._current_finding()
        item = self._current_item()
        if finding is None or item is None:
            return
        if finding.fix_action is None or finding.fix_action.action_type == "condense":
            self.notify("No auto-fix available for this finding.", severity="warning")
            return
        self._approved.add(finding.id)
        self._skipped.discard(finding.id)
        item.mark_approved()
        self._show_finding(finding)
        self._refresh_summary()

    def action_skip(self) -> None:
        finding = self._current_finding()
        item = self._current_item()
        if finding is None or item is None:
            return
        self._skipped.add(finding.id)
        self._approved.discard(finding.id)
        item.mark_skipped()
        self._show_finding(finding)
        self._refresh_summary()

    def action_view_diff(self) -> None:
        self.query_one("#detail", DetailPanel).show_diff(self._plan)

    def action_write_plan(self) -> None:
        from prowlr_doctor import paths
        from prowlr_doctor.models import FixAction, PatchPlan
        from prowlr_doctor.scanner import load_snapshot
        from prowlr_doctor.recommender import recommend
        from prowlr_doctor.patch_planner import build_plan
        import datetime

        approved_findings = [f for f in self._findings if f.id in self._approved]
        actions = [
            f.fix_action for f in approved_findings
            if f.fix_action and f.fix_action.action_type != "condense"
        ]
        savings = sum(f.tokens_wasted for f in approved_findings)
        plan = PatchPlan(
            version="1",
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            profile=self.current_profile,
            findings_count=len(self._findings),
            actions=actions,
            estimated_savings=savings,
            settings_diff=self._plan.settings_diff,
            plan_path=paths.doctor_plan_path(),
        )
        self._plan = plan
        plan_path = paths.doctor_plan_path()
        plan_path.write_text(plan.to_json())
        self.notify(f"Plan written to {plan_path}  ({len(actions)} actions)", severity="information")

    def action_apply_all(self) -> None:
        approved = [f for f in self._findings if f.id in self._approved]
        if not approved:
            self.notify("No approved fixes. Press [D] on findings first.", severity="warning")
            return
        self.action_write_plan()
        try:
            from prowlr_doctor.patch_planner import apply_plan
            apply_plan(self._plan)
            self.notify(
                f"Applied {len(self._plan.actions)} changes. Restart Claude Code to reload.",
                severity="information",
            )
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error")

    def action_cycle_profile(self) -> None:
        idx = _PROFILES.index(self.current_profile)
        self.current_profile = _PROFILES[(idx + 1) % len(_PROFILES)]
        self._refresh_summary()
        self.notify(f"Profile: {self.current_profile}", severity="information")

    def _refresh_summary(self) -> None:
        self.query_one("#summary", SummaryBar).update_stats(
            self._findings, self._budget, self.current_profile, self._approved
        )

    def _refresh_status(self) -> None:
        self.query_one("#status", StatusBar).update_budget(self._budget)
