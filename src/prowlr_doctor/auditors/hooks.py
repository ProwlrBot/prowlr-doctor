"""Auditor: hooks — broken imports, multiple PreToolUse, large injections.

Detection is via static AST analysis only. No hook files are executed.
"""
from __future__ import annotations

import ast
from pathlib import Path

from prowlr_doctor.auditors.base import BaseAuditor
from prowlr_doctor.models import EnvironmentSnapshot, Finding, FixAction, Severity
from prowlr_doctor import tokens

# Subprocess-related attribute names that indicate shell-execution risk
_SUBPROCESS_ATTRS = frozenset(["run", "Popen", "call", "check_output", "popen"])
# os module attributes that indicate shell-execution risk
_OS_SHELL_ATTRS = frozenset(["system", "popen"])
# Combined set of risky module names
_RISKY_MODULES = frozenset(["subprocess", "os"])


class HooksAuditor(BaseAuditor):
    def audit(self, env: EnvironmentSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        pretool_hooks = [h for h in env.hooks if h.get("event") == "PreToolUse"]
        if len(pretool_hooks) > 1:
            findings.append(Finding(
                id="multi-pretooluse-hooks",
                severity=Severity.HIGH,
                category="security",
                title=f"Multiple PreToolUse hooks ({len(pretool_hooks)})",
                detail=(
                    f"{len(pretool_hooks)} PreToolUse hooks registered. "
                    "Conflicting security rules may cancel each other; each adds interception latency."
                ),
                explainability="Multiple PreToolUse hooks can conflict and each adds latency to every tool call.",
            ))

        for hook in env.hooks:
            hook_path = self._resolve_hook_path(hook)
            if hook_path is None:
                continue

            if not hook_path.exists():
                findings.append(Finding(
                    id=f"broken-hook-{hook_path.stem}",
                    severity=Severity.HIGH,
                    category="security",
                    title=f"Broken hook: {hook_path.name} not found",
                    detail=f"Hook references {hook_path} which does not exist. The hook silently fails.",
                    explainability="Missing hook file means the security rule never enforces.",
                    fix_action=FixAction(
                        action_type="fix-import",
                        target=str(hook_path),
                        settings_path=None,
                        before=str(hook_path),
                        after=None,
                        reversible=False,
                    ),
                ))
                continue

            findings.extend(self._check_imports(hook, hook_path))
            findings.extend(self._check_injection_size(hook, hook_path))
            findings.extend(self._check_shell_execution(hook, hook_path))

        return findings

    def _resolve_hook_path(self, hook: dict) -> Path | None:
        cmd = hook.get("command", "")
        if not cmd:
            return None
        for part in cmd.split():
            if part.endswith(".py"):
                return Path(part)
        return None

    def _check_imports(self, hook: dict, hook_path: Path) -> list[Finding]:
        """Static AST check: verify sys.path inserts resolve to real dirs."""
        findings = []
        try:
            tree = ast.parse(hook_path.read_text())
        except (SyntaxError, OSError):
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            # Detect: sys.path.insert(0, "/some/path")
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "insert"
                and isinstance(func.value, ast.Attribute)
                and func.value.attr == "path"
                and isinstance(func.value.value, ast.Name)
                and func.value.value.id == "sys"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
            ):
                path_str = node.args[1].value
                if isinstance(path_str, str) and not Path(path_str).exists():
                    findings.append(Finding(
                        id=f"broken-import-{hook_path.stem}",
                        severity=Severity.HIGH,
                        category="security",
                        title=f"Broken sys.path in hook: {hook_path.name}",
                        detail=(
                            f"Hook inserts {path_str!r} into sys.path but that directory does not exist. "
                            "Imports from this path will fail silently."
                        ),
                        explainability="Hook imports fail → security rule never enforces.",
                        fix_action=FixAction(
                            action_type="fix-import",
                            target=str(hook_path),
                            settings_path=None,
                            before=path_str,
                            after=None,
                            reversible=False,
                        ),
                    ))
        return findings

    def _check_injection_size(self, hook: dict, hook_path: Path) -> list[Finding]:
        """Flag SessionStart hooks that inject >2000 tokens."""
        if hook.get("event") != "SessionStart":
            return []
        try:
            content = hook_path.read_text()
        except OSError:
            return []
        token_count = tokens.count(content)
        if token_count > 2000:
            return [Finding(
                id=f"large-session-hook-{hook_path.stem}",
                severity=Severity.MEDIUM,
                category="token-waste",
                title=f"Large SessionStart hook: {hook_path.name} ({tokens.display(token_count)} tokens)",
                detail=f"{hook_path.name} injects {tokens.display(token_count)} tokens on every session start.",
                explainability="Large SessionStart hooks inflate per-session fixed cost.",
                tokens_wasted=token_count,
            )]
        return []

    def _check_shell_execution(self, hook: dict, hook_path: Path) -> list[Finding]:
        """AST check: detect risky shell-execution patterns in hook files."""
        try:
            tree = ast.parse(hook_path.read_text())
        except (SyntaxError, OSError):
            return []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            module_name = getattr(func.value, "id", "")
            if module_name not in _RISKY_MODULES:
                continue
            attr = func.attr
            is_risky = (
                (module_name == "subprocess" and attr in _SUBPROCESS_ATTRS)
                or (module_name == "os" and attr in _OS_SHELL_ATTRS)
            )
            if is_risky:
                return [Finding(
                    id=f"shell-exec-hook-{hook_path.stem}",
                    severity=Severity.HIGH,
                    category="security",
                    title=f"Shell execution in hook: {hook_path.name}",
                    detail=(
                        f"{hook_path.name} calls {module_name}.{attr}. "
                        "Hook scripts with shell-execution calls are a command injection surface."
                    ),
                    explainability="Shell execution in hooks can be exploited via tool argument injection.",
                )]
        return []
