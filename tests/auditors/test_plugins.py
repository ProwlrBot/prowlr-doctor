from prowlr_doctor.auditors.plugins import PluginsAuditor
from prowlr_doctor.models import Severity


def test_no_findings_on_minimal(minimal_env):
    findings = PluginsAuditor().audit(minimal_env)
    dup_findings = [f for f in findings if f.category == "duplicate"]
    assert len(dup_findings) == 0


def test_detects_duplicate_on_typical(typical_env):
    findings = PluginsAuditor().audit(typical_env)
    dup_findings = [f for f in findings if f.category == "duplicate"]
    assert len(dup_findings) >= 1
    assert any("example-skills" in f.id for f in dup_findings)


def test_duplicate_severity_is_critical(typical_env):
    findings = PluginsAuditor().audit(typical_env)
    dup = [f for f in findings if "example-skills" in f.id]
    assert len(dup) >= 1
    assert dup[0].severity == Severity.CRITICAL


def test_duplicate_has_fix_action(typical_env):
    findings = PluginsAuditor().audit(typical_env)
    dup = [f for f in findings if "example-skills" in f.id]
    assert dup[0].fix_action is not None
    assert dup[0].fix_action.action_type == "disable"
    assert dup[0].fix_action.reversible is True


def test_large_bundle_detected_on_bloated(bloated_env):
    findings = PluginsAuditor().audit(bloated_env)
    large = [f for f in findings if "large-bundle" in f.id]
    assert len(large) >= 1
