"""Auditor: security findings — broken imports, dangerous patterns, conflicts.

All detection is via static AST analysis of hook files. No execution, no subprocess.
Sub-project 3 adds: eval/exec detection, shell keyword arg, settings integrity, cross-correlation.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from prowlr_doctor.auditors.base import BaseAuditor
from prowlr_doctor.models import EnvironmentSnapshot, Finding, FixAction, Severity
from prowlr_doctor import tokens

# Builtins that allow arbitrary code execution
_CODE_EXEC_BUILTINS = frozenset(["eval", "exec", "compile", "__import__"])

# settings.json keys that should never appear
_SUSPICIOUS_SETTINGS_KEYS = frozenset([
    "debugMode", "allowArbitraryCode", "disableSandbox",
    "bypassHooks", "skipAuth", "noVerify",
])


class SecurityAuditor(BaseAuditor):
    def audit(self, env: EnvironmentSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._check_duplicate_security_plugins(env))
        findings.extend(self._check_eval_exec_in_hooks(env))
        findings.extend(self._check_unsafe_shell_kwarg(env))
        findings.extend(self._check_settings_integrity(env))
        findings.extend(self._check_cross_correlation(env))
        return findings

    def _check_duplicate_security_plugins(self, env: EnvironmentSnapshot) -> list[Finding]:
        """Flag when two enabled plugins both claim to be security auditors."""
        security_plugins = []
        for plugin_id, plugin_dir in env.installed_plugin_dirs.items():
            if not env.enabled_plugins.get(plugin_id, False):
                continue
            manifest = plugin_dir / "plugin.json"
            if not manifest.exists():
                continue
            try:
                data = json.loads(manifest.read_text())
            except Exception:
                continue
            tags = data.get("tags", [])
            if any(t in ("security", "hookify", "audit") for t in tags):
                security_plugins.append(plugin_id)

        if len(security_plugins) > 1:
            return [Finding(
                id="dup-security-plugins",
                severity=Severity.HIGH,
                category="conflict",
                title=f"Multiple security plugins: {', '.join(security_plugins)}",
                detail=(
                    f"You have {len(security_plugins)} security/hookify plugins enabled. "
                    "Conflicting rules may shadow each other."
                ),
                explainability="Two security plugins with overlapping rules: one likely shadows the other.",
            )]
        return []

    def _check_eval_exec_in_hooks(self, env: EnvironmentSnapshot) -> list[Finding]:
        """AST: detect eval/exec/compile/__import__ calls in hook files."""
        findings = []
        for hook in env.hooks:
            hook_path = self._resolve_hook_path(hook)
            if hook_path is None or not hook_path.exists():
                continue
            try:
                tree = ast.parse(hook_path.read_text())
            except (SyntaxError, OSError):
                continue

            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in _CODE_EXEC_BUILTINS
                ):
                    findings.append(Finding(
                        id=f"code-exec-hook-{hook_path.stem}",
                        severity=Severity.CRITICAL,
                        category="security",
                        title=f"Code execution builtin in hook: {hook_path.name} ({node.func.id})",
                        detail=(
                            f"{hook_path.name} calls {node.func.id}(). "
                            "Dynamic code execution in hooks is a critical injection risk."
                        ),
                        explainability=f"{node.func.id}() in a hook = arbitrary code execution surface.",
                    ))
                    break
        return findings

    def _check_unsafe_shell_kwarg(self, env: EnvironmentSnapshot) -> list[Finding]:
        """AST: detect subprocess calls with the shell keyword argument set to True."""
        findings = []
        for hook in env.hooks:
            hook_path = self._resolve_hook_path(hook)
            if hook_path is None or not hook_path.exists():
                continue
            try:
                tree = ast.parse(hook_path.read_text())
            except (SyntaxError, OSError):
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for kw in node.keywords:
                    if (
                        kw.arg == "shell"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        findings.append(Finding(
                            id=f"unsafe-shell-kwarg-{hook_path.stem}",
                            severity=Severity.CRITICAL,
                            category="security",
                            title=f"Unsafe shell kwarg in hook: {hook_path.name}",
                            detail=(
                                f"{hook_path.name} passes shell=True to a subprocess call. "
                                "Shell metacharacters in arguments can execute arbitrary commands."
                            ),
                            explainability="shell=True + user-controlled tool args = OS command injection.",
                        ))
                        break
        return findings

    def _check_settings_integrity(self, env: EnvironmentSnapshot) -> list[Finding]:
        """Flag suspicious or unexpected keys in settings.json."""
        findings = []
        for key in env.settings:
            if key in _SUSPICIOUS_SETTINGS_KEYS:
                findings.append(Finding(
                    id=f"suspicious-setting-{key}",
                    severity=Severity.CRITICAL,
                    category="security",
                    title=f"Suspicious settings.json key: {key}",
                    detail=(
                        f"settings.json contains '{key}' which is not a standard Claude Code key. "
                        "This may indicate tampering or a misconfigured plugin."
                    ),
                    explainability=f"Non-standard key '{key}' in settings.json — possible tampering.",
                    fix_action=FixAction(
                        action_type="patch",
                        target=key,
                        settings_path=[key],
                        before=env.settings.get(key),
                        after=None,
                        reversible=True,
                        requires_restart=False,
                    ),
                ))
        return findings

    def _check_cross_correlation(self, env: EnvironmentSnapshot) -> list[Finding]:
        """Correlate findings from multiple auditors into higher-severity combined findings."""
        findings = []
        pretool_hooks = [h for h in env.hooks if h.get("event") == "PreToolUse"]
        if len(pretool_hooks) <= 1:
            return findings

        broken_pretool = []
        for hook in pretool_hooks:
            hook_path = self._resolve_hook_path(hook)
            if hook_path is None or not hook_path.exists():
                broken_pretool.append(str(hook_path or "unknown"))
                continue
            try:
                tree = ast.parse(hook_path.read_text())
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "insert"
                        and isinstance(node.func.value, ast.Attribute)
                        and node.func.value.attr == "path"
                        and len(node.args) >= 2
                        and isinstance(node.args[1], ast.Constant)
                    ):
                        path_val = node.args[1].value
                        if isinstance(path_val, str) and not Path(path_val).exists():
                            broken_pretool.append(str(hook_path))
                            break
            except (SyntaxError, OSError):
                pass

        if broken_pretool:
            findings.append(Finding(
                id="broken-security-with-conflict",
                severity=Severity.CRITICAL,
                category="security",
                title=f"Broken + conflicting PreToolUse hooks ({len(pretool_hooks)} registered)",
                detail=(
                    f"{len(pretool_hooks)} PreToolUse hooks are registered and "
                    f"{len(broken_pretool)} have broken import paths. "
                    "Your security rules are simultaneously broken AND conflicting — "
                    "tool interception provides zero protection."
                ),
                explainability="Broken + conflicting PreToolUse hooks = no security enforcement.",
            ))
        return findings

    def _resolve_hook_path(self, hook: dict) -> Path | None:
        cmd = hook.get("command", "")
        if not cmd:
            return None
        for part in cmd.split():
            if part.endswith(".py"):
                return Path(part)
        return None
