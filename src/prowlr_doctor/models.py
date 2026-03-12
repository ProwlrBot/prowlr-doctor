"""Core data types for prowlr-doctor."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Literal


class Severity(IntEnum):
    INFO = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


ActionType = Literal["disable", "enable", "patch", "condense", "fix-import"]


@dataclass
class EnvironmentSnapshot:
    """Parsed Claude Code environment — passed to every auditor."""
    settings_path: Any                         # Path
    settings: dict
    enabled_plugins: dict[str, bool]           # plugin_id → enabled
    mcp_servers: dict[str, dict]               # server_id → config
    hooks: list[dict]                          # raw hook entries
    plugin_cache_dir: Any                      # Path
    global_claude_md: Any | None               # Path | None
    project_claude_md: list                    # list[Path]
    memory_files: list                         # list[Path]
    installed_plugin_dirs: dict[str, Any]      # plugin_id → resolved cache dir


@dataclass
class FixAction:
    action_type: ActionType
    target: str                                # plugin ID, hook name, file path, etc.
    settings_path: list[str] | None            # JSON path for settings.json; None for condense
    before: Any
    after: Any
    reversible: bool = True
    requires_restart: bool = False


@dataclass
class Finding:
    id: str                                    # stable ID e.g. "dup-example-skills"
    severity: Severity
    category: Literal[
        "security", "token-waste", "duplicate", "conflict", "stale", "verbosity"
    ]
    title: str
    detail: str                                # human explanation shown in detail panel
    explainability: str                        # one-sentence "why this costs you"
    tokens_wasted: int = 0
    fix_action: FixAction | None = None


@dataclass
class Recommendations:
    profile: str
    disable: list[Finding] = field(default_factory=list)
    review: list[Finding] = field(default_factory=list)
    keep: list[Finding] = field(default_factory=list)
    condense: list[Finding] = field(default_factory=list)


@dataclass
class TokenBudget:
    per_session_fixed: int = 0
    per_turn_recurring: int = 0
    on_demand: int = 0
    wasted: int = 0
    savings_if_cleaned: int = 0
    session_estimate_20turn: int = 0

    def compute_session_estimate(self) -> int:
        return self.per_session_fixed + (self.per_turn_recurring * 20)


@dataclass
class PatchPlan:
    version: str
    generated_at: str
    profile: str
    findings_count: int
    actions: list[FixAction]
    estimated_savings: int
    settings_diff: dict
    plan_path: Any                             # Path

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "profile": self.profile,
            "findings_count": self.findings_count,
            "actions": [
                {
                    "action_type": a.action_type,
                    "target": a.target,
                    "settings_path": a.settings_path,
                    "before": a.before,
                    "after": a.after,
                    "reversible": a.reversible,
                    "requires_restart": a.requires_restart,
                }
                for a in self.actions
            ],
            "estimated_savings": self.estimated_savings,
            "settings_diff": self.settings_diff,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
