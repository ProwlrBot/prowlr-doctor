from prowlr_doctor.auditors.claude_md import ClaudeMdAuditor
from prowlr_doctor.models import Severity


def test_no_findings_on_minimal(minimal_env):
    findings = ClaudeMdAuditor().audit(minimal_env)
    assert findings == []


def test_detects_verbose_claude_md(bloated_env):
    findings = ClaudeMdAuditor().audit(bloated_env)
    verbose = [f for f in findings if f.category == "verbosity"]
    assert len(verbose) >= 1
    assert all(f.tokens_wasted > 0 for f in verbose)


def test_verbosity_severity(bloated_env):
    findings = ClaudeMdAuditor().audit(bloated_env)
    for f in findings:
        assert f.severity in (Severity.MEDIUM, Severity.HIGH)
