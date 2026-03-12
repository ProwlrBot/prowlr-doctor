from prowlr_doctor.auditors.memory import MemoryAuditor
from prowlr_doctor.models import Severity


def test_no_findings_on_minimal(minimal_env):
    findings = MemoryAuditor().audit(minimal_env)
    assert findings == []


def test_stale_memory_detected_on_bloated(bloated_env):
    findings = MemoryAuditor().audit(bloated_env)
    stale = [f for f in findings if f.category == "stale"]
    assert len(stale) >= 1


def test_stale_memory_has_tokens(bloated_env):
    findings = MemoryAuditor().audit(bloated_env)
    stale = [f for f in findings if f.category == "stale"]
    assert all(f.tokens_wasted > 0 for f in stale)
