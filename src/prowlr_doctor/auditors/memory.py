"""Auditor: stale memory files (>30 days old or >5k tokens)."""
from __future__ import annotations

import time
from pathlib import Path

from prowlr_doctor.auditors.base import BaseAuditor
from prowlr_doctor.models import EnvironmentSnapshot, Finding, FixAction, Severity
from prowlr_doctor import tokens

_STALE_DAYS = 30
_LARGE_TOKENS = 5000


class MemoryAuditor(BaseAuditor):
    def audit(self, env: EnvironmentSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        now = time.time()
        stale_cutoff = now - (_STALE_DAYS * 86400)

        for mem_file in env.memory_files:
            try:
                mtime = mem_file.stat().st_mtime
            except OSError:
                continue

            token_count = tokens.count_file(mem_file)
            age_days = int((now - mtime) / 86400)
            is_stale = mtime < stale_cutoff
            is_large = token_count >= _LARGE_TOKENS

            if is_stale and is_large:
                severity = Severity.HIGH
            elif is_stale or is_large:
                severity = Severity.MEDIUM
            else:
                continue

            reason_parts = []
            if is_stale:
                reason_parts.append(f"{age_days} days old")
            if is_large:
                reason_parts.append(f"{tokens.display(token_count)} tokens")

            findings.append(Finding(
                id=f"stale-memory-{mem_file.stem}",
                severity=severity,
                category="stale",
                title=f"Stale memory file: {mem_file.name} ({', '.join(reason_parts)})",
                detail=(
                    f"{mem_file} is {age_days} days old and {tokens.display(token_count)} tokens. "
                    "Memory files are injected every session. Stale entries waste context."
                ),
                explainability=f"Memory file adds {tokens.display(token_count)} tokens per session; may be outdated.",
                tokens_wasted=token_count,
                fix_action=FixAction(
                    action_type="condense",
                    target=str(mem_file),
                    settings_path=None,
                    before=str(mem_file),
                    after=None,
                    reversible=True,
                ),
            ))
        return findings
