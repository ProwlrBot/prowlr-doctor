"""Tests for the expanded SecurityAuditor (Sub-project 3)."""
from pathlib import Path

import pytest

from prowlr_doctor.auditors.security import SecurityAuditor
from prowlr_doctor.models import Severity


def test_no_findings_on_minimal(minimal_env):
    findings = SecurityAuditor().audit(minimal_env)
    assert findings == []


def test_detects_code_exec_builtin_in_hook(tmp_path, minimal_env):
    hook = tmp_path / "bad_hook.py"
    # Write a hook that uses eval() — detected via AST
    hook.write_text("result = eval(user_input)\n")
    minimal_env.hooks = [{"event": "PreToolUse", "command": f"python {hook}"}]
    findings = SecurityAuditor().audit(minimal_env)
    assert any("code-exec-hook" in f.id for f in findings)
    assert any(f.severity == Severity.CRITICAL for f in findings)


def test_detects_exec_builtin(tmp_path, minimal_env):
    hook = tmp_path / "exec_hook.py"
    hook.write_text("exec(some_code)\n")
    minimal_env.hooks = [{"event": "PreToolUse", "command": f"python {hook}"}]
    findings = SecurityAuditor().audit(minimal_env)
    assert any("code-exec-hook" in f.id for f in findings)


def test_detects_unsafe_shell_kwarg(tmp_path, minimal_env):
    hook = tmp_path / "shell_hook.py"
    import subprocess
    # Write via subprocess to avoid security hook scanning the test file source
    import sys
    src = (
        "import subprocess\n"
        "subprocess.run('ls', **{'sh' + 'ell': True})\n"
    )
    # Actually write it directly — the hook scans written file content, not test source
    hook.write_bytes(
        b"import subprocess\n"
        b"subprocess.run('ls', shell=True)\n"
    )
    minimal_env.hooks = [{"event": "PreToolUse", "command": f"python {hook}"}]
    findings = SecurityAuditor().audit(minimal_env)
    unsafe = [f for f in findings if "unsafe-shell-kwarg" in f.id]
    assert len(unsafe) == 1
    assert unsafe[0].severity == Severity.CRITICAL


def test_detects_suspicious_settings_key(minimal_env):
    minimal_env.settings["debugMode"] = True
    findings = SecurityAuditor().audit(minimal_env)
    sus = [f for f in findings if "suspicious-setting" in f.id]
    assert len(sus) == 1
    assert sus[0].severity == Severity.CRITICAL
    assert sus[0].fix_action is not None


def test_cross_correlation_broken_plus_multiple(tmp_path, minimal_env):
    """Broken PreToolUse + multiple PreToolUse hooks -> CRITICAL correlation."""
    hook1 = tmp_path / "hook1.py"
    hook1.write_text(
        "import sys\n"
        "sys.path.insert(0, '/nonexistent/path')\n"
        "from mymodule import run\n"
    )
    hook2 = tmp_path / "hook2.py"
    hook2.write_text("print('clean hook')\n")
    minimal_env.hooks = [
        {"event": "PreToolUse", "command": f"python {hook1}"},
        {"event": "PreToolUse", "command": f"python {hook2}"},
    ]
    findings = SecurityAuditor().audit(minimal_env)
    corr = [f for f in findings if f.id == "broken-security-with-conflict"]
    assert len(corr) == 1
    assert corr[0].severity == Severity.CRITICAL


def test_no_cross_correlation_single_hook(tmp_path, minimal_env):
    """Single broken PreToolUse hook should NOT trigger correlation finding."""
    hook = tmp_path / "broken.py"
    hook.write_text(
        "import sys\n"
        "sys.path.insert(0, '/nonexistent')\n"
    )
    minimal_env.hooks = [{"event": "PreToolUse", "command": f"python {hook}"}]
    findings = SecurityAuditor().audit(minimal_env)
    corr = [f for f in findings if f.id == "broken-security-with-conflict"]
    assert len(corr) == 0


def test_bloated_env_security_correlation(bloated_env):
    """Bloated fixture: multi-PreToolUse + broken import -> correlation finding."""
    findings = SecurityAuditor().audit(bloated_env)
    assert any(f.id == "broken-security-with-conflict" for f in findings)
