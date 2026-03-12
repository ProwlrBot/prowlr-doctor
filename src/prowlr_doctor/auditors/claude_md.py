"""Auditor: CLAUDE.md verbosity."""
from __future__ import annotations

from prowlr_doctor.auditors.base import BaseAuditor
from prowlr_doctor.models import EnvironmentSnapshot, Finding, Severity
from prowlr_doctor import tokens

_VERBOSE_THRESHOLD = 2000   # tokens
_EXTREME_THRESHOLD = 8000   # tokens


class ClaudeMdAuditor(BaseAuditor):
    def audit(self, env: EnvironmentSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        all_files = []
        if env.global_claude_md:
            all_files.append(("global", env.global_claude_md))
        for p in env.project_claude_md:
            all_files.append(("project", p))

        for kind, path in all_files:
            token_count = tokens.count_file(path)
            if token_count >= _EXTREME_THRESHOLD:
                findings.append(Finding(
                    id=f"verbose-claude-md-{path.parent.name}-extreme",
                    severity=Severity.HIGH,
                    category="verbosity",
                    title=f"Very large CLAUDE.md: {path} ({tokens.display(token_count)} tokens)",
                    detail=(
                        f"This {kind} CLAUDE.md is {tokens.display(token_count)} tokens — "
                        "injected on every session start. Consider splitting into focused sections "
                        "or removing redundant instructions."
                    ),
                    explainability=f"CLAUDE.md adds {tokens.display(token_count)} tokens to every session.",
                    tokens_wasted=token_count,
                ))
            elif token_count >= _VERBOSE_THRESHOLD:
                findings.append(Finding(
                    id=f"verbose-claude-md-{path.parent.name}",
                    severity=Severity.MEDIUM,
                    category="verbosity",
                    title=f"Large CLAUDE.md: {path} ({tokens.display(token_count)} tokens)",
                    detail=(
                        f"This {kind} CLAUDE.md is {tokens.display(token_count)} tokens. "
                        "Review for redundant or outdated instructions."
                    ),
                    explainability=f"CLAUDE.md injects {tokens.display(token_count)} tokens on every session.",
                    tokens_wasted=token_count,
                ))
        return findings
