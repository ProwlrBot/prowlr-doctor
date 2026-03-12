"""Claude Code path constants and environment discovery."""
from __future__ import annotations

import os
from pathlib import Path


def claude_dir() -> Path:
    return Path(os.environ.get("CLAUDE_DIR", Path.home() / ".claude"))


def settings_path() -> Path:
    return claude_dir() / "settings.json"


def plugin_cache_dir() -> Path:
    return claude_dir() / "plugins" / "cache"


def global_claude_md() -> Path | None:
    p = claude_dir() / "CLAUDE.md"
    return p if p.exists() else None


def project_claude_md_files(cwd: Path | None = None) -> list[Path]:
    """All CLAUDE.md files from cwd up to fs root."""
    root = (cwd or Path.cwd()).resolve()
    found = []
    current = root
    while True:
        candidate = current / "CLAUDE.md"
        if candidate.exists():
            found.append(candidate)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return found


def memory_files() -> list[Path]:
    """All memory markdown files under ~/.claude/projects/*/memory/."""
    base = claude_dir() / "projects"
    if not base.exists():
        return []
    return sorted(base.glob("*/memory/*.md"))


def doctor_cache_path() -> Path:
    return claude_dir() / "doctor-cache.json"


def doctor_plan_path() -> Path:
    return claude_dir() / "doctor-plan.json"
