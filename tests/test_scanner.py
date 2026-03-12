"""Integration tests: run full audit pipeline against fixture environments."""
from prowlr_doctor.scanner import run_audit
from prowlr_doctor.recommender import recommend


def test_minimal_env_runs_cleanly(minimal_env):
    findings, budget = run_audit(minimal_env)
    # May have no findings or only info-level
    assert isinstance(findings, list)
    assert budget.per_session_fixed >= 0


def test_typical_env_finds_duplicate(typical_env):
    findings, budget = run_audit(typical_env)
    dup_findings = [f for f in findings if f.category == "duplicate"]
    assert len(dup_findings) >= 1
    assert budget.wasted > 0


def test_bloated_env_finds_multiple_issues(bloated_env):
    findings, budget = run_audit(bloated_env)
    categories = {f.category for f in findings}
    # Should find security (multi-pretooluse), stale, verbosity, duplicate
    assert len(findings) >= 3
    assert budget.wasted > 0


def test_recommender_developer_profile(typical_env):
    findings, budget = run_audit(typical_env)
    rec = recommend(findings, "developer")
    assert rec.profile == "developer"
    # Duplicates → disable in developer profile
    assert any(f.category == "duplicate" for f in rec.disable)


def test_recommender_minimal_profile(bloated_env):
    findings, budget = run_audit(bloated_env)
    rec = recommend(findings, "minimal")
    # Minimal profile should disable more than developer
    developer_rec = recommend(findings, "developer")
    assert len(rec.disable) >= len(developer_rec.disable)
