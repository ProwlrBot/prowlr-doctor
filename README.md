# ProwlrDoctor 🩺

**Security-aware Claude Code environment auditor with token cost intelligence.**

Reads your Claude Code environment — plugins, hooks, MCP servers, CLAUDE.md, memory files — and tells you exactly what each component costs per session, what's broken, and how to fix it.

```
prowlr-doctor
```

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

## Install

```bash
pip install prowlr-doctor

# With Textual TUI:
pip install "prowlr-doctor[tui]"
```

Or via prowlrbot:
```bash
pip install prowlrbot
prowlr doctor
```

## Usage

```bash
prowlr-doctor                          # interactive TUI (default)
prowlr-doctor --no-tui                 # Rich terminal report
prowlr-doctor --profile security       # security-focused recommendations
prowlr-doctor --profile minimal        # strip to minimum
prowlr-doctor --json                   # machine-readable output
prowlr-doctor --write-plan             # write fix plan to ~/.claude/doctor-plan.json
prowlr-doctor --diff                   # preview exact settings.json changes
prowlr-doctor --apply                  # apply plan (creates timestamped backup first)
prowlr-doctor --opt-in-telemetry       # contribute anonymous aggregate stats
```

## What It Checks

| Auditor | What it catches |
|---|---|
| **Plugins** | Duplicate registries, large agent bundles (50+ agents) |
| **Hooks** | Broken import paths, multiple PreToolUse, oversized SessionStart |
| **Agents** | Byte-identical agent definitions across plugins |
| **MCP servers** | Missing binaries, duplicate registrations |
| **CLAUDE.md** | Verbosity (>2k tokens = medium, >8k = high) |
| **Memory** | Stale files (>30 days or >5k tokens) |
| **Security** | `eval`/`exec` in hooks, `shell=True`, settings tampering, conflicting security plugins, cross-auditor correlation |

## TUI Keybindings

| Key | Action |
|---|---|
| `↑↓` | Navigate findings |
| `D` | Approve disable for selected finding |
| `S` | Skip |
| `V` | View settings.json diff |
| `A` | Apply all approved actions |
| `P` | Cycle profiles (developer → security → minimal → agent-builder → research) |
| `W` | Write plan to disk |
| `Q` | Quit |

## Profiles

- **developer** — disables duplicates, keeps most tooling
- **security** — disables aggressively, condenses verbose files
- **minimal** — strips to bare minimum
- **agent-builder** — preserves agent bundles, removes clutter
- **research** — preserves all knowledge/doc tooling

## Community Dashboard

Run the dashboard server locally:

```bash
pip install "prowlr-doctor[dashboard]"
python -m dashboard
# → http://localhost:8042
```

Opt in to contribute anonymous aggregate stats:

```bash
prowlr-doctor --opt-in-telemetry
```

No PII. No file paths. No plugin names. Counts only.

## Build Order

| Sub-project | Status |
|---|---|
| 1 — Core auditors + CLI + Rich reporter | ✅ |
| 2 — Textual TUI | ✅ |
| 3 — Deep security checks + telemetry | ✅ |
| 4 — Community dashboard | ✅ |

## License

MIT — [ProwlrBot](https://github.com/ProwlrBot)
