"""Integration tests: run full audit pipeline against fixture environments."""
import json
from pathlib import Path

import pytest

from prowlr_doctor.scanner import load_snapshot, run_audit
from prowlr_doctor.recommender import recommend


def test_minimal_env_runs_cleanly(minimal_env):
    findings, budget = run_audit(minimal_env)
    # May have no findings or only info-level
    assert isinstance(findings, list)
    assert budget.per_session_fixed >= 0


def test_typical_env_finds_duplicate(typical_env):
    findings, budget = run_audit(typical_env)
    dup_findings = [f for f in findings if f.category == "duplicate"]
    assert len(dup_findings) >= 1
    assert budget.wasted > 0


def test_bloated_env_finds_multiple_issues(bloated_env):
    findings, budget = run_audit(bloated_env)
    categories = {f.category for f in findings}
    # Should find security (multi-pretooluse), stale, verbosity, duplicate
    assert len(findings) >= 3
    assert budget.wasted > 0


def test_recommender_developer_profile(typical_env):
    findings, budget = run_audit(typical_env)
    rec = recommend(findings, "developer")
    assert rec.profile == "developer"
    # Duplicates → disable in developer profile
    assert any(f.category == "duplicate" for f in rec.disable)


def test_recommender_minimal_profile(bloated_env):
    findings, budget = run_audit(bloated_env)
    rec = recommend(findings, "minimal")
    # Minimal profile should disable more than developer
    developer_rec = recommend(findings, "developer")
    assert len(rec.disable) >= len(developer_rec.disable)


# ---------------------------------------------------------------------------
# load_snapshot(): plugin directory discovery tests
# ---------------------------------------------------------------------------

def _make_versioned_plugin(cache: Path, registry: str, name: str, version: str) -> Path:
    """Create a versioned plugin dir: cache/registry/name/version/agents/*.md"""
    plugin_root = cache / registry / name / version
    agents_dir = plugin_root / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "my-agent.md").write_text("# my-agent\n")
    return plugin_root


def _make_settings(tmp_path: Path, cache: Path, plugin_ids: list[str]) -> Path:
    settings = {
        "enabledPlugins": {pid: True for pid in plugin_ids},
    }
    sp = tmp_path / "settings.json"
    sp.write_text(json.dumps(settings))
    return sp


def test_load_snapshot_resolves_registry_name_version(tmp_path, monkeypatch):
    """load_snapshot must resolve cache/registry/name/version/ correctly.

    Plugin IDs are `name@registry`. The cache layout is registry/name/version/.
    A previous bug did `replace("@", "/")` → name/registry (wrong order).
    """
    cache = tmp_path / "cache"
    # Create: cache/claude-plugins-official/superpowers/5.0.2/agents/
    version_dir = _make_versioned_plugin(cache, "claude-plugins-official", "superpowers", "5.0.2")

    plugin_id = "superpowers@claude-plugins-official"
    sp = _make_settings(tmp_path, cache, [plugin_id])

    # Patch paths module so load_snapshot reads our synthetic settings
    import prowlr_doctor.paths as paths_mod
    monkeypatch.setattr(paths_mod, "settings_path", lambda: sp)
    monkeypatch.setattr(paths_mod, "plugin_cache_dir", lambda: cache)
    monkeypatch.setattr(paths_mod, "global_claude_md", lambda: tmp_path / "CLAUDE.md")
    monkeypatch.setattr(paths_mod, "project_claude_md_files", lambda cwd=None: [])
    monkeypatch.setattr(paths_mod, "memory_files", lambda: [])

    from prowlr_doctor.scanner import load_snapshot
    env = load_snapshot()

    assert plugin_id in env.installed_plugin_dirs, (
        f"Plugin {plugin_id!r} not resolved — path order bug likely returned"
    )
    resolved = env.installed_plugin_dirs[plugin_id]
    assert resolved == version_dir, f"Expected {version_dir}, got {resolved}"
    assert (resolved / "agents" / "my-agent.md").exists()


def test_load_snapshot_picks_latest_version(tmp_path, monkeypatch):
    """When multiple version dirs exist, load_snapshot picks the highest semver."""
    cache = tmp_path / "cache"
    _make_versioned_plugin(cache, "test-registry", "myplugin", "1.0.0")
    _make_versioned_plugin(cache, "test-registry", "myplugin", "2.3.1")
    _make_versioned_plugin(cache, "test-registry", "myplugin", "1.9.9")

    plugin_id = "myplugin@test-registry"
    sp = _make_settings(tmp_path, cache, [plugin_id])

    import prowlr_doctor.paths as paths_mod
    monkeypatch.setattr(paths_mod, "settings_path", lambda: sp)
    monkeypatch.setattr(paths_mod, "plugin_cache_dir", lambda: cache)
    monkeypatch.setattr(paths_mod, "global_claude_md", lambda: tmp_path / "CLAUDE.md")
    monkeypatch.setattr(paths_mod, "project_claude_md_files", lambda cwd=None: [])
    monkeypatch.setattr(paths_mod, "memory_files", lambda: [])

    from prowlr_doctor.scanner import load_snapshot
    env = load_snapshot()

    resolved = env.installed_plugin_dirs[plugin_id]
    assert resolved.name == "2.3.1", f"Expected latest version 2.3.1, got {resolved.name}"


def test_load_snapshot_flat_fallback(tmp_path, monkeypatch):
    """Plugins without @registry in their ID fall back to cache/name/."""
    cache = tmp_path / "cache"
    flat_dir = cache / "myplugin" / "agents"
    flat_dir.mkdir(parents=True)
    (flat_dir / "agent.md").write_text("# agent\n")

    plugin_id = "myplugin"
    sp = _make_settings(tmp_path, cache, [plugin_id])

    import prowlr_doctor.paths as paths_mod
    monkeypatch.setattr(paths_mod, "settings_path", lambda: sp)
    monkeypatch.setattr(paths_mod, "plugin_cache_dir", lambda: cache)
    monkeypatch.setattr(paths_mod, "global_claude_md", lambda: tmp_path / "CLAUDE.md")
    monkeypatch.setattr(paths_mod, "project_claude_md_files", lambda cwd=None: [])
    monkeypatch.setattr(paths_mod, "memory_files", lambda: [])

    from prowlr_doctor.scanner import load_snapshot
    env = load_snapshot()

    assert plugin_id in env.installed_plugin_dirs
