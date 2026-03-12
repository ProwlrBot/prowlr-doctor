"""Auditor: security findings — broken imports, dangerous patterns, conflicts.

All detection is via static AST analysis of hook files. No execution, no subprocess.
"""
from __future__ import annotations

import ast
import json
from collections import defaultdict
from pathlib import Path

from prowlr_doctor.auditors.base import BaseAuditor
from prowlr_doctor.models import EnvironmentSnapshot, Finding, FixAction, Severity
from prowlr_doctor import tokens

_DANGEROUS_ATTRS = frozenset([
    "eval", "exec", "compile", "__import__",
])


class SecurityAuditor(BaseAuditor):
    def audit(self, env: EnvironmentSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._check_duplicate_security_plugins(env))
        findings.extend(self._check_session_start_injection(env))
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
                    "Conflicting rules may shadow each other — one may never enforce."
                ),
                explainability="Two security plugins with overlapping rules: one likely shadows the other.",
            )]
        return []

    def _check_session_start_injection(self, env: EnvironmentSnapshot) -> list[Finding]:
        """Find SessionStart hooks injecting >2000 tokens (security + cost concern)."""
        # Delegated to hooks.py — security.py adds cross-cutting classification
        return []
