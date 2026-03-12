from pathlib import Path

import pytest

from prowlr_doctor.auditors.hooks import HooksAuditor
from prowlr_doctor.models import Severity


def test_no_findings_on_minimal(minimal_env):
    findings = HooksAuditor().audit(minimal_env)
    assert findings == []


def test_detects_multiple_pretooluse(bloated_env):
    findings = HooksAuditor().audit(bloated_env)
    multi = [f for f in findings if f.id == "multi-pretooluse-hooks"]
    assert len(multi) == 1
    assert multi[0].severity == Severity.HIGH


def test_detects_broken_import(bloated_env):
    findings = HooksAuditor().audit(bloated_env)
    broken = [f for f in findings if "broken-import" in f.id]
    assert len(broken) >= 1


def test_broken_hook_file_missing(tmp_path, minimal_env):
    minimal_env.hooks = [{"event": "PreToolUse", "command": "python /nonexistent/hook.py"}]
    findings = HooksAuditor().audit(minimal_env)
    missing = [f for f in findings if "broken-hook" in f.id]
    assert len(missing) == 1
    assert missing[0].severity == Severity.HIGH
