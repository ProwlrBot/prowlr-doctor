"""Auditor: MCP server binary presence, duplicate registrations."""
from __future__ import annotations

import os
from pathlib import Path

from prowlr_doctor.auditors.base import BaseAuditor
from prowlr_doctor.models import EnvironmentSnapshot, Finding, Severity

_WELL_KNOWN = {
    "jcodemunch", "serena", "context7", "playwright", "figma",
    "github", "filesystem", "memory", "fetch",
}


class McpAuditor(BaseAuditor):
    def audit(self, env: EnvironmentSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        seen_binaries: dict[str, str] = {}  # resolved binary → first server_id

        for server_id, config in env.mcp_servers.items():
            binary = self._extract_binary(config)
            if binary:
                resolved = str(Path(binary).resolve())
                if resolved in seen_binaries:
                    findings.append(Finding(
                        id=f"dup-mcp-{server_id}",
                        severity=Severity.MEDIUM,
                        category="duplicate",
                        title=f"Duplicate MCP server: {server_id}",
                        detail=(
                            f"{server_id} and {seen_binaries[resolved]} point to the same binary "
                            f"({binary}). One registration is redundant."
                        ),
                        explainability="Two MCP entries for the same binary waste startup time and tool slots.",
                    ))
                else:
                    seen_binaries[resolved] = server_id

                if not Path(binary).exists() or not os.access(binary, os.X_OK):
                    findings.append(Finding(
                        id=f"missing-mcp-{server_id}",
                        severity=Severity.HIGH,
                        category="security",
                        title=f"MCP server binary missing: {server_id}",
                        detail=(
                            f"{binary} does not exist or is not executable. "
                            f"{server_id} is listed but will never respond."
                        ),
                        explainability="Missing MCP binary causes silent connection failure on every session.",
                    ))

            # Unknown server → info finding
            name = server_id.split("@")[0].split("/")[-1].lower()
            if not any(k in name for k in _WELL_KNOWN):
                findings.append(Finding(
                    id=f"unknown-mcp-{server_id}",
                    severity=Severity.INFO,
                    category="verbosity",
                    title=f"Unknown MCP server: {server_id}",
                    detail=f"{server_id} is not in the well-known server list. Verify it's still needed.",
                    explainability="Unrecognized MCP server — may be unused or misconfigured.",
                ))

        return findings

    def _extract_binary(self, config: dict) -> str | None:
        cmd = config.get("command", "")
        if cmd:
            return cmd.split()[0]
        args = config.get("args", [])
        if args:
            return args[0]
        return None
