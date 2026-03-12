"""Textual TUI app — Sub-project 2. Stub for now."""
from __future__ import annotations

from prowlr_doctor.models import Finding, PatchPlan, Recommendations, TokenBudget


class EnvDoctorApp:
    """Textual full-screen app. Requires: pip install prowlr-doctor[tui]"""

    def __init__(
        self,
        findings: list[Finding],
        budget: TokenBudget,
        rec: Recommendations,
        plan: PatchPlan,
    ) -> None:
        self.findings = findings
        self.budget = budget
        self.rec = rec
        self.plan = plan

    def run(self) -> None:
        try:
            from textual.app import App, ComposeResult
            from textual.widgets import Header, Footer, DataTable, Static
            from textual.binding import Binding
        except ImportError:
            raise ImportError("Install textual: pip install prowlr-doctor[tui]")

        findings = self.findings
        budget = self.budget
        rec = self.rec

        class _App(App):
            BINDINGS = [
                Binding("q", "quit", "Quit"),
                Binding("d", "approve", "Disable"),
                Binding("s", "skip", "Skip"),
            ]

            def compose(self) -> ComposeResult:
                yield Header(show_clock=True)
                yield Static(
                    f"Findings: {len(findings)}  ·  "
                    f"Auto-fixable: {len(rec.disable)}  ·  "
                    f"Wasted: ~{budget.wasted // 1000}k tokens"
                )
                table = DataTable()
                table.add_columns("Severity", "Title", "Tokens Wasted")
                for f in sorted(findings, key=lambda x: -x.severity):
                    table.add_row(
                        f.severity.name,
                        f.title,
                        f"~{f.tokens_wasted // 1000}k" if f.tokens_wasted else "—",
                    )
                yield table
                yield Footer()

            def action_approve(self) -> None:
                pass  # Sub-project 2

            def action_skip(self) -> None:
                pass  # Sub-project 2

        _App().run()
