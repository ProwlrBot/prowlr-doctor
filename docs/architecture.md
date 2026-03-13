# ProwlrDoctor — Architecture

## End-to-End Flow

```
load_snapshot()
      │
      │  Reads ~/.claude/settings.json
      │  Resolves plugin cache dirs
      │  Collects CLAUDE.md, memory files
      ▼
EnvironmentSnapshot
      │
      ▼
run_audit(env)
      │
      ├──► PluginsAuditor   → duplicate registries, large bundles (50+ agents)
      ├──► HooksAuditor     → broken paths, oversized SessionStart, shell calls
      ├──► AgentsAuditor    → byte-identical agent .md files, files > 10KB
      ├──► McpAuditor       → missing binaries, duplicate registrations
      ├──► ClaudeMdAuditor  → verbosity (>2k = MEDIUM, >8k = HIGH)
      ├──► MemoryAuditor    → stale (>30 days) or large (>5k tokens) memory files
      └──► SecurityAuditor  → eval/exec, shell=True, settings tampering, cross-correlation
                │
                ▼
         list[Finding]  +  TokenBudget
                │
                ▼
        recommend(findings, profile)
                │
                ▼
         Recommendations  (disable / review / keep / condense)
                │
        ┌───────┴───────┐
        ▼               ▼
   build_plan()      render()  (Rich terminal report)
        │
        ▼
   PatchPlan  ──► TUI (EnvDoctorApp)  or  --apply  or  --json
```

## Key Data Models

### `EnvironmentSnapshot`
Parsed state of the Claude Code environment passed to every auditor.

| Field | Type | Description |
|---|---|---|
| `settings_path` | `Path` | Path to `~/.claude/settings.json` |
| `settings` | `dict` | Raw parsed JSON |
| `enabled_plugins` | `dict[str, bool]` | plugin ID → enabled flag |
| `mcp_servers` | `dict[str, dict]` | server ID → config block |
| `hooks` | `list[dict]` | Raw hook entries from settings |
| `plugin_cache_dir` | `Path` | Claude Code plugin cache root |
| `global_claude_md` | `Path \| None` | `~/.claude/CLAUDE.md` |
| `project_claude_md` | `list[Path]` | Per-project `CLAUDE.md` files |
| `memory_files` | `list[Path]` | All `~/.claude/memory/**` files |
| `installed_plugin_dirs` | `dict[str, Path]` | plugin ID → resolved cache dir |

### `Finding`
The unit of output from every auditor.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Stable identifier (e.g. `dup-plugin-hookify`) |
| `severity` | `Severity` | `INFO=1`, `MEDIUM=2`, `HIGH=3`, `CRITICAL=4` |
| `category` | `str` | One of: `security`, `token-waste`, `duplicate`, `conflict`, `stale`, `verbosity` |
| `title` | `str` | Short headline shown in the list |
| `detail` | `str` | Full explanation in the detail panel |
| `explainability` | `str` | One-sentence cost statement |
| `tokens_wasted` | `int` | Estimated tokens wasted per session |
| `fix_action` | `FixAction \| None` | Machine-executable remediation |

### `TokenBudget`

| Field | Description |
|---|---|
| `per_session_fixed` | Tokens from CLAUDE.md + memory files (paid once per session) |
| `per_turn_recurring` | Plugin overhead × 20 turns |
| `wasted` | Sum of `tokens_wasted` across all findings |
| `savings_if_cleaned` | Same as `wasted` — tokens recoverable by applying the plan |
| `session_estimate_20turn` | `per_session_fixed + (per_turn_recurring × 20)` |

## Auditor Summaries

| Auditor | File | What it checks |
|---|---|---|
| `PluginsAuditor` | `auditors/plugins.py` | Plugins whose agent sets are identical; bundles with 50+ agents |
| `HooksAuditor` | `auditors/hooks.py` | Missing hook files; broken `sys.path` inserts; `SessionStart` hooks > 2k tokens; `subprocess`/`os` shell calls |
| `AgentsAuditor` | `auditors/agents.py` | Byte-identical `.md` agent files across plugins; single agent files > 10KB |
| `McpAuditor` | `auditors/mcp.py` | MCP binaries that don't exist or aren't executable; two entries pointing to the same binary; unrecognized server names |
| `ClaudeMdAuditor` | `auditors/claude_md.py` | `CLAUDE.md` files above 2k tokens (MEDIUM) or 8k tokens (HIGH) |
| `MemoryAuditor` | `auditors/memory.py` | Memory files older than 30 days or larger than 5k tokens |
| `SecurityAuditor` | `auditors/security.py` | `eval`/`exec`/`compile` in hooks; `shell=True` in subprocess calls; suspicious `settings.json` keys; cross-correlation of broken + conflicting `PreToolUse` hooks |

## Recommender Profiles

The recommender maps each `Finding.category` to a disposition per profile:

| Category | developer | security | minimal | agent-builder | research |
|---|---|---|---|---|---|
| duplicate | disable | disable | disable | disable | disable |
| token-waste | review | disable | disable | keep | keep |
| security | disable | disable | disable | disable | disable |
| conflict | review | disable | disable | review | review |
| stale | review | disable | disable | review | review |
| verbosity | keep | condense | condense | keep | keep |
