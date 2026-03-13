# TUI Keyboard Reference

## Launching the TUI

```bash
# Default — opens the interactive TUI (requires Textual)
prowlr-doctor

# Install Textual support if needed
pip install "prowlr-doctor[tui]"

# Skip the TUI and use the Rich terminal report instead
prowlr-doctor --no-tui
```

The TUI launches automatically when Textual is installed. If it is not available,
`prowlr-doctor` falls back to the Rich terminal report without any extra flags.

## Keybindings

| Key | Action |
|---|---|
| `Up` / `Down` | Navigate the findings list |
| `D` | Approve "disable" action for the selected finding |
| `S` | Skip the selected finding (move to next without approving) |
| `V` | View the `settings.json` diff that would result from approved actions |
| `A` | Apply all approved actions immediately |
| `P` | Cycle the active profile: `developer` → `security` → `minimal` → `agent-builder` → `research` |
| `W` | Write the current plan to `~/.claude/doctor-plan.json` |
| `Q` | Quit |

## Profile Cycle Order

Pressing `P` steps through profiles in this order (wraps around):

```
developer  →  security  →  minimal  →  agent-builder  →  research  →  developer  →  ...
```

Changing the profile recomputes recommendations live — the summary bar updates to show
the new finding counts and approved-savings totals.

## Summary Bar

The top bar always shows:

```
Profile: developer  ·  Findings: 5  ·  ● 1 critical  ·  ◆ 2 high  ·  ✓ 3 approved (134k savings)
```

- Red `●` badge = CRITICAL severity
- Yellow `◆` badge = HIGH or MEDIUM severity
- Green `✓` = count and token savings for findings you have approved in this session
