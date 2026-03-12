"""Auditor: duplicate plugin registries and version conflicts."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from prowlr_doctor.auditors.base import BaseAuditor
from prowlr_doctor.models import EnvironmentSnapshot, Finding, FixAction, Severity
from prowlr_doctor import tokens


class PluginsAuditor(BaseAuditor):
    def audit(self, env: EnvironmentSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._check_duplicates(env))
        findings.extend(self._check_large_bundles(env))
        return findings

    def _check_duplicates(self, env: EnvironmentSnapshot) -> list[Finding]:
        """Detect plugins whose agent manifests are byte-identical to another plugin."""
        findings = []
        # Map plugin_id → set of agent IDs it provides
        plugin_agents: dict[str, set[str]] = {}
        for plugin_id, plugin_dir in env.installed_plugin_dirs.items():
            if not env.enabled_plugins.get(plugin_id, False):
                continue
            agents = self._collect_agent_ids(plugin_dir)
            if agents:
                plugin_agents[plugin_id] = agents

        # Find pairs with identical agent sets
        seen: dict[frozenset, str] = {}
        for plugin_id, agent_ids in plugin_agents.items():
            key = frozenset(agent_ids)
            if key in seen:
                original = seen[key]
                token_cost = self._estimate_plugin_tokens(
                    env.installed_plugin_dirs.get(plugin_id)
                )
                findings.append(Finding(
                    id=f"dup-plugin-{plugin_id.replace('/', '-').replace('@', '-')}",
                    severity=Severity.CRITICAL,
                    category="duplicate",
                    title=f"Duplicate registry: {plugin_id}",
                    detail=(
                        f"{plugin_id} provides the same {len(agent_ids)} agents as {original}. "
                        f"Keeping both wastes ~{tokens.display(token_cost)} tokens per session."
                    ),
                    explainability=f"Byte-identical copy of {original}; safe to disable.",
                    tokens_wasted=token_cost,
                    fix_action=FixAction(
                        action_type="disable",
                        target=plugin_id,
                        settings_path=["enabledPlugins", plugin_id],
                        before=True,
                        after=False,
                        reversible=True,
                        requires_restart=False,
                    ),
                ))
            else:
                seen[key] = plugin_id
        return findings

    def _check_large_bundles(self, env: EnvironmentSnapshot) -> list[Finding]:
        """Flag bundles with 50+ agents (high per-turn skill list overhead)."""
        findings = []
        for plugin_id, plugin_dir in env.installed_plugin_dirs.items():
            if not env.enabled_plugins.get(plugin_id, False):
                continue
            agents = self._collect_agent_ids(plugin_dir)
            if len(agents) >= 50:
                token_cost = len(agents) * 150  # ~150 chars per skill list entry
                findings.append(Finding(
                    id=f"large-bundle-{plugin_id.replace('/', '-').replace('@', '-')}",
                    severity=Severity.MEDIUM,
                    category="token-waste",
                    title=f"Large agent bundle: {plugin_id} ({len(agents)} agents)",
                    detail=(
                        f"{plugin_id} registers {len(agents)} agents. "
                        f"Each turn injects the full skill list (~{tokens.display(token_cost)} tokens)."
                    ),
                    explainability=(
                        f"{len(agents)} agents × ~150 chars each = "
                        f"{tokens.display(token_cost)} tokens added to every tool call."
                    ),
                    tokens_wasted=token_cost,
                ))
        return findings

    def _collect_agent_ids(self, plugin_dir: Path | None) -> set[str]:
        if plugin_dir is None or not plugin_dir.exists():
            return set()
        ids: set[str] = set()
        # Check for agents/ subdirectory with .md files
        agents_dir = plugin_dir / "agents"
        if agents_dir.exists():
            for md in agents_dir.glob("**/*.md"):
                ids.add(md.stem)
        # Check plugin.json for agent definitions
        manifest = plugin_dir / "plugin.json"
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text())
                for agent in data.get("agents", []):
                    name = agent.get("name") or agent.get("subagent_type")
                    if name:
                        ids.add(name)
            except Exception:
                pass
        return ids

    def _estimate_plugin_tokens(self, plugin_dir: Path | None) -> int:
        if plugin_dir is None or not plugin_dir.exists():
            return 0
        total = 0
        for md in (plugin_dir / "agents").glob("**/*.md") if (plugin_dir / "agents").exists() else []:
            total += tokens.count_file(md)
        return total
