"""Auditor: agent bundle sizes, byte-identical duplicates, oversized agent files."""
from __future__ import annotations

from pathlib import Path

from prowlr_doctor.auditors.base import BaseAuditor
from prowlr_doctor.models import EnvironmentSnapshot, Finding, Severity
from prowlr_doctor import tokens

_LARGE_FILE_BYTES = 10 * 1024  # 10KB


class AgentsAuditor(BaseAuditor):
    def audit(self, env: EnvironmentSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._check_identical_files(env))
        findings.extend(self._check_oversized_files(env))
        return findings

    def _all_agent_files(self, env: EnvironmentSnapshot) -> list[Path]:
        files = []
        for plugin_id, plugin_dir in env.installed_plugin_dirs.items():
            if not env.enabled_plugins.get(plugin_id, False):
                continue
            agents_dir = plugin_dir / "agents"
            if agents_dir.exists():
                files.extend(agents_dir.glob("**/*.md"))
        return files

    def _check_identical_files(self, env: EnvironmentSnapshot) -> list[Finding]:
        """Flag agent .md files that are byte-identical across plugins."""
        content_map: dict[bytes, list[Path]] = {}
        for f in self._all_agent_files(env):
            try:
                data = f.read_bytes()
            except OSError:
                continue
            content_map.setdefault(data, []).append(f)

        findings = []
        for paths in content_map.values():
            if len(paths) < 2:
                continue
            token_cost = tokens.count(paths[0].read_text(errors="replace"))
            # Report duplicates beyond the first
            for dup in paths[1:]:
                findings.append(Finding(
                    id=f"dup-agent-{dup.stem}",
                    severity=Severity.HIGH,
                    category="duplicate",
                    title=f"Duplicate agent definition: {dup.name}",
                    detail=(
                        f"{dup} is byte-identical to {paths[0]}. "
                        f"Wastes {tokens.display(token_cost)} tokens per occurrence."
                    ),
                    explainability=f"Identical copy of {paths[0].name}; one can be removed.",
                    tokens_wasted=token_cost,
                ))
        return findings

    def _check_oversized_files(self, env: EnvironmentSnapshot) -> list[Finding]:
        """Flag agent definition files over 10KB."""
        findings = []
        for f in self._all_agent_files(env):
            try:
                size = f.stat().st_size
            except OSError:
                continue
            if size > _LARGE_FILE_BYTES:
                token_cost = tokens.count_file(f)
                findings.append(Finding(
                    id=f"large-agent-{f.stem}",
                    severity=Severity.MEDIUM,
                    category="token-waste",
                    title=f"Large agent definition: {f.name} ({size // 1024}KB)",
                    detail=(
                        f"{f} is {size // 1024}KB ({tokens.display(token_cost)} tokens). "
                        "Large agent definitions are injected in full when the agent is invoked."
                    ),
                    explainability=f"Agent file {f.name} adds {tokens.display(token_cost)} tokens on-demand.",
                    tokens_wasted=token_cost,
                ))
        return findings
