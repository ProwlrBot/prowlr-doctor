"""TUI smoke tests using Textual's built-in test pilot."""
import pytest

pytest.importorskip("textual", reason="textual not installed")

from prowlr_doctor.models import Finding, FixAction, PatchPlan, Recommendations, Severity, TokenBudget
from prowlr_doctor.tui.app import EnvDoctorApp

import datetime


def _make_finding(fid: str, sev: Severity, fixable: bool = True) -> Finding:
    fix = FixAction(
        action_type="disable",
        target=fid,
        settings_path=["enabledPlugins", fid],
        before=True,
        after=False,
    ) if fixable else None
    return Finding(
        id=fid,
        severity=sev,
        category="duplicate",
        title=f"Test finding: {fid}",
        detail="Detail text",
        explainability="Why it matters",
        tokens_wasted=1000 if fixable else 0,
        fix_action=fix,
    )


def _make_app(findings: list[Finding]) -> EnvDoctorApp:
    budget = TokenBudget(
        per_session_fixed=5000,
        per_turn_recurring=2000,
        wasted=sum(f.tokens_wasted for f in findings),
        savings_if_cleaned=sum(f.tokens_wasted for f in findings),
        session_estimate_20turn=45000,
    )
    rec = Recommendations(
        profile="developer",
        disable=[f for f in findings if f.fix_action],
    )
    plan = PatchPlan(
        version="1",
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        profile="developer",
        findings_count=len(findings),
        actions=[f.fix_action for f in findings if f.fix_action],
        estimated_savings=budget.savings_if_cleaned,
        settings_diff={"before": {}, "after": {}},
        plan_path=None,
    )
    return EnvDoctorApp(findings=findings, budget=budget, rec=rec, plan=plan)


@pytest.mark.asyncio
async def test_tui_mounts_with_findings():
    findings = [
        _make_finding("dup-a", Severity.CRITICAL),
        _make_finding("dup-b", Severity.HIGH),
        _make_finding("info-c", Severity.INFO, fixable=False),
    ]
    app = _make_app(findings)
    async with app.run_test() as pilot:
        # Summary bar should be present
        summary = app.query_one("#summary")
        assert summary is not None
        # Findings list should have 3 items
        from prowlr_doctor.tui.app import FindingItem
        items = app.query(FindingItem)
        assert len(items) == 3


@pytest.mark.asyncio
async def test_tui_approve_with_d():
    findings = [_make_finding("dup-x", Severity.CRITICAL)]
    app = _make_app(findings)
    # Pre-clear approved set to test keypress
    app._approved.clear()
    async with app.run_test() as pilot:
        await pilot.press("d")
        assert "dup-x" in app._approved


@pytest.mark.asyncio
async def test_tui_skip_with_s():
    findings = [_make_finding("dup-y", Severity.HIGH)]
    app = _make_app(findings)
    app._approved.clear()
    async with app.run_test() as pilot:
        await pilot.press("s")
        assert "dup-y" in app._skipped


@pytest.mark.asyncio
async def test_tui_cycle_profile():
    findings = [_make_finding("dup-z", Severity.MEDIUM)]
    app = _make_app(findings)
    async with app.run_test() as pilot:
        initial = app.current_profile
        await pilot.press("p")
        assert app.current_profile != initial
