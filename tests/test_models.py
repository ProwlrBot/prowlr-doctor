from prowlr_doctor.models import Finding, FixAction, Severity, TokenBudget, PatchPlan


def test_severity_ordering():
    assert Severity.CRITICAL > Severity.HIGH > Severity.MEDIUM > Severity.INFO


def test_finding_defaults():
    f = Finding(
        id="test-001",
        severity=Severity.HIGH,
        category="duplicate",
        title="Test finding",
        detail="Some detail",
        explainability="Why it matters",
    )
    assert f.tokens_wasted == 0
    assert f.fix_action is None


def test_finding_with_fix():
    fix = FixAction(
        action_type="disable",
        target="plugin@registry",
        settings_path=["enabledPlugins", "plugin@registry"],
        before=True,
        after=False,
    )
    f = Finding(
        id="dup-plugin",
        severity=Severity.CRITICAL,
        category="duplicate",
        title="Duplicate plugin",
        detail="Details",
        explainability="Why",
        tokens_wasted=133533,
        fix_action=fix,
    )
    assert f.fix_action.action_type == "disable"
    assert f.fix_action.reversible is True


def test_token_budget_estimate():
    b = TokenBudget(per_session_fixed=18000, per_turn_recurring=4800)
    estimate = b.compute_session_estimate()
    assert estimate == 18000 + 4800 * 20
