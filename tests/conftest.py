"""Shared fixtures: minimal / typical / bloated synthetic environments."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prowlr_doctor.models import EnvironmentSnapshot


def _make_snapshot(
    tmp_path: Path,
    plugin_dirs: dict[str, Path],
    settings: dict | None = None,
    hooks: list[dict] | None = None,
    memory_files: list[Path] | None = None,
    global_claude_md: Path | None = None,
) -> EnvironmentSnapshot:
    sp = tmp_path / "settings.json"
    s = settings or {}
    sp.write_text(json.dumps(s))
    return EnvironmentSnapshot(
        settings_path=sp,
        settings=s,
        enabled_plugins={pid: True for pid in plugin_dirs},
        mcp_servers=s.get("mcpServers", {}),
        hooks=hooks or [],
        plugin_cache_dir=tmp_path / "cache",
        global_claude_md=global_claude_md,
        project_claude_md=[],
        memory_files=memory_files or [],
        installed_plugin_dirs=plugin_dirs,
    )


def _make_plugin_dir(base: Path, plugin_id: str, agent_names: list[str]) -> Path:
    plugin_dir = base / plugin_id.replace("@", "/")
    agents_dir = plugin_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for name in agent_names:
        (agents_dir / f"{name}.md").write_text(f"# {name}\n\nAgent: {name}\n")
    return plugin_dir


@pytest.fixture
def minimal_env(tmp_path):
    """5 plugins, no duplicates, no issues."""
    plugin_dirs = {}
    for i in range(5):
        pid = f"plugin-{i}@test"
        plugin_dirs[pid] = _make_plugin_dir(tmp_path, pid, [f"agent-{i}-a", f"agent-{i}-b"])
    return _make_snapshot(tmp_path, plugin_dirs)


@pytest.fixture
def typical_env(tmp_path):
    """30 plugins, one duplicate pair."""
    plugin_dirs = {}
    base_agents = [f"agent-base-{i}" for i in range(10)]
    # First plugin
    pid_a = "claude-api@anthropic-agent-skills"
    plugin_dirs[pid_a] = _make_plugin_dir(tmp_path, pid_a, base_agents)
    # Duplicate — same agent names (identical content)
    pid_b = "example-skills@anthropic-agent-skills"
    dup_dir = tmp_path / "example-skills" / "anthropic-agent-skills"
    agents_dir = dup_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    # Copy identical content from pid_a
    for name in base_agents:
        src = tmp_path / "claude-api" / "anthropic-agent-skills" / "agents" / f"{name}.md"
        (agents_dir / f"{name}.md").write_bytes(src.read_bytes())
    plugin_dirs[pid_b] = dup_dir
    # Fill out with more unique plugins
    for i in range(28):
        pid = f"plugin-{i}@test"
        plugin_dirs[pid] = _make_plugin_dir(tmp_path, pid, [f"agent-{i}"])
    return _make_snapshot(tmp_path, plugin_dirs)


@pytest.fixture
def bloated_env(tmp_path):
    """55 plugins, 3 duplicates, stale memory, verbose CLAUDE.md, broken hook."""
    plugin_dirs = {}

    # Large agent bundle (60 agents)
    big_pid = "voltagent-all@voltagent"
    big_agents = [f"voltagent-agent-{i}" for i in range(60)]
    plugin_dirs[big_pid] = _make_plugin_dir(tmp_path, big_pid, big_agents)

    # Duplicate pair
    base_agents = [f"dup-agent-{i}" for i in range(20)]
    pid_orig = "original-skills@test"
    plugin_dirs[pid_orig] = _make_plugin_dir(tmp_path, pid_orig, base_agents)
    pid_dup = "duplicate-skills@test"
    dup_dir = tmp_path / "duplicate-skills" / "test"
    agents_dir2 = dup_dir / "agents"
    agents_dir2.mkdir(parents=True, exist_ok=True)
    for name in base_agents:
        src = tmp_path / "original-skills" / "test" / "agents" / f"{name}.md"
        (agents_dir2 / f"{name}.md").write_bytes(src.read_bytes())
    plugin_dirs[pid_dup] = dup_dir

    # Remaining plugins
    for i in range(53):
        pid = f"bloat-plugin-{i}@test"
        plugin_dirs[pid] = _make_plugin_dir(tmp_path, pid, [f"bloat-{i}"])

    # Stale memory file
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    stale_mem = mem_dir / "old_context.md"
    stale_mem.write_text("# Old context\n\n" + ("word " * 3000))
    import time
    old_time = time.time() - (40 * 86400)  # 40 days ago
    import os
    os.utime(stale_mem, (old_time, old_time))

    # Verbose CLAUDE.md
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Instructions\n\n" + ("instruction " * 2500))

    # Broken hook
    broken_hook = tmp_path / "broken_hook.py"
    broken_hook.write_text(
        "import sys\nsys.path.insert(0, '/nonexistent/path')\nfrom my_module import run\n"
    )

    hooks = [
        {"event": "PreToolUse", "command": f"python {broken_hook}"},
        {"event": "PreToolUse", "command": "python /another/hook.py"},
    ]

    return _make_snapshot(
        tmp_path, plugin_dirs,
        hooks=hooks,
        memory_files=[stale_mem],
        global_claude_md=claude_md,
    )
