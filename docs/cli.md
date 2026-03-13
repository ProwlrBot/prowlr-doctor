# CLI Reference

## Command

```
prowlr-doctor [OPTIONS]
```

Audit your Claude Code environment for token waste and security issues.

## Options

| Flag | Default | Description |
|---|---|---|
| `--profile` | `developer` | Recommendation profile. Choices: `developer`, `security`, `minimal`, `agent-builder`, `research` |
| `--json` | off | Print machine-readable JSON to stdout instead of launching the TUI or Rich report |
| `--write-plan` | off | Generate a fix plan and write it to `~/.claude/doctor-plan.json` |
| `--diff` | off | Show a unified diff of the `settings.json` changes in the plan on disk |
| `--apply` | off | Apply the plan at `~/.claude/doctor-plan.json` (creates a timestamped backup first) |
| `--no-tui` | off | Force the Rich terminal report; skip the Textual TUI even if it is installed |
| `--opt-in-telemetry` | off | Opt in to anonymous aggregate telemetry and exit |
| `--opt-out-telemetry` | off | Opt out of telemetry and exit |
| `--version` | — | Print the installed version and exit |

## Profiles

| Profile | Description |
|---|---|
| `developer` | Disables duplicates, keeps most tooling, reviews token-waste and stale files |
| `security` | Disables aggressively across all categories, condenses verbose files |
| `minimal` | Strips to bare minimum — disables everything that is not essential |
| `agent-builder` | Preserves agent bundles and token-heavy tooling, removes obvious clutter |
| `research` | Preserves all knowledge and documentation tooling |

## Workflow Examples

### Default run (interactive TUI)

```bash
prowlr-doctor
```

Opens the Textual TUI. Requires `pip install "prowlr-doctor[tui]"`.
Falls back to the Rich terminal report automatically if Textual is not installed.

### Rich terminal report only

```bash
prowlr-doctor --no-tui
```

Example output:

```
  ProwlrDoctor v0.1 ──────────────────────────────────────────
  Profile: developer  ·  Findings: 3  ·  Auto-fixable: 2

  ● CRITICAL   example-skills registry — ~134k tokens wasted/session
               Byte-identical copy of claude-api. Safe to disable.

  ◆ HIGH       hookify (old) — broken sys.path
               Imports fail silently → security rule never enforces.

  ◆ MEDIUM     CLAUDE.md — ~9k tokens (verbose)

  ──────────────────────────────────────────────────────────────
  20-turn estimate:  ~37k tokens
  Wasted:           ~134k tokens → ~$0.40/session saved
```

### Security-focused audit

```bash
prowlr-doctor --profile security --no-tui
```

### Machine-readable output

```bash
prowlr-doctor --json
```

Prints a JSON document to stdout and also writes it to `~/.claude/doctor-cache.json`
for use by statusline integrations. Top-level keys:

```json
{
  "version": "1",
  "generated_at": "...",
  "profile": "developer",
  "environment": {
    "plugins_enabled": 4,
    "hooks_count": 2,
    "mcp_servers": 6
  },
  "token_budget": {
    "per_session_fixed": 12400,
    "per_turn_recurring": 200,
    "on_demand": 0,
    "wasted": 134000,
    "savings_if_cleaned": 134000,
    "session_estimate_20turn": 16400
  },
  "findings": [ ... ],
  "recommendations": {
    "disable": ["dup-plugin-example-skills"],
    "review": ["stale-memory-notes"],
    "keep": [],
    "condense": []
  }
}
```

### Generate and preview a fix plan

```bash
# Write plan to disk
prowlr-doctor --write-plan

# Preview the exact settings.json changes
prowlr-doctor --diff
```

The plan is saved to `~/.claude/doctor-plan.json`. The `--diff` command renders a
colour-coded unified diff using Rich.

### Apply a fix plan

```bash
prowlr-doctor --apply
```

Reads `~/.claude/doctor-plan.json`, creates a timestamped backup of `settings.json`,
and applies all non-condense actions. Condense actions (for CLAUDE.md and memory files)
are skipped by `--apply` and must be performed manually.

After applying, restart Claude Code to pick up the changes.

### Telemetry

```bash
# Opt in (no PII — counts only)
prowlr-doctor --opt-in-telemetry

# Opt out
prowlr-doctor --opt-out-telemetry
```

Telemetry sends anonymous aggregate counts only. No file paths, no plugin names,
no personal information.
