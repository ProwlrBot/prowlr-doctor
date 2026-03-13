# Auditor Reference

Each auditor is an independent class that receives an `EnvironmentSnapshot` and returns
a list of `Finding` objects. Auditors use static analysis only — no hooks or plugin code
is ever executed.

---

## PluginsAuditor

**File:** `src/prowlr_doctor/auditors/plugins.py`

### What it checks

- **Duplicate registries** — compares the set of agent IDs each enabled plugin provides.
  If two plugins expose identical agent sets they are considered byte-for-byte duplicates.
- **Large bundles** — flags any enabled plugin that registers 50 or more agents.
  Each agent adds roughly 150 tokens of skill-list overhead to every tool call.

### Findings emitted

| Finding ID pattern | Category | Severity | Trigger |
|---|---|---|---|
| `dup-plugin-<plugin-id>` | `duplicate` | CRITICAL | Two enabled plugins have identical agent sets |
| `large-bundle-<plugin-id>` | `token-waste` | MEDIUM | Plugin has 50+ agents registered |

### When you'd see it

Duplicate findings appear when you have the same plugin registered under two different
registry sources (e.g. `hookify@claude-plugins-official` and `hookify@my-mirror`).
Large-bundle findings appear when you enable a comprehensive agent pack designed for a
different use-case than yours.

---

## HooksAuditor

**File:** `src/prowlr_doctor/auditors/hooks.py`

### What it checks

All analysis is static AST — no hook files are executed.

- **Multiple PreToolUse hooks** — more than one hook registered for the `PreToolUse` event
  creates conflicting interception rules and adds latency to every tool call.
- **Missing hook files** — a hook entry references a `.py` file that does not exist on disk.
  The hook silently does nothing at runtime.
- **Broken `sys.path` inserts** — AST scan for `sys.path.insert(0, "/some/path")` where
  the target directory does not exist. Imports from that path fail silently.
- **Oversized `SessionStart` hooks** — hook scripts attached to `SessionStart` that exceed
  2,000 tokens inflate the per-session fixed cost.
- **Shell execution in hooks** — AST detection of `subprocess` module calls and `os` module
  shell-dispatch calls inside hook files.

### Findings emitted

| Finding ID pattern | Category | Severity | Trigger |
|---|---|---|---|
| `multi-pretooluse-hooks` | `security` | HIGH | More than one `PreToolUse` hook registered |
| `broken-hook-<name>` | `security` | HIGH | Hook `.py` file not found on disk |
| `broken-import-<name>` | `security` | HIGH | `sys.path.insert` references a non-existent directory |
| `large-session-hook-<name>` | `token-waste` | MEDIUM | `SessionStart` hook script > 2,000 tokens |
| `shell-exec-hook-<name>` | `security` | HIGH | Hook calls subprocess or OS shell-dispatch functions |

### When you'd see it

Broken-hook findings appear after a system Python upgrade or a plugin removal that leaves
behind stale hook registrations. Shell-execution findings appear in hook scripts that
shell out to run linters or formatters.

---

## AgentsAuditor

**File:** `src/prowlr_doctor/auditors/agents.py`

### What it checks

Scans the `agents/` subdirectory of every enabled plugin's cache dir.

- **Byte-identical agent files** — reads the raw bytes of every agent `.md` file across
  all enabled plugins. Files with identical content are duplicates; all but the first are
  flagged.
- **Oversized agent files** — agent definition files larger than 10KB are flagged.
  They are injected in full when the agent is invoked.

### Findings emitted

| Finding ID pattern | Category | Severity | Trigger |
|---|---|---|---|
| `dup-agent-<name>` | `duplicate` | HIGH | Agent `.md` file is byte-identical to a file in another plugin |
| `large-agent-<name>` | `token-waste` | MEDIUM | Agent `.md` file exceeds 10KB |

### When you'd see it

Duplicate agent findings appear when two plugins both bundle the same built-in agent
(e.g. a `file-reader` agent shipped by multiple toolkits). Large-agent findings appear
for agents with verbose inline prompts or embedded examples.

---

## McpAuditor

**File:** `src/prowlr_doctor/auditors/mcp.py`

### What it checks

Iterates over every entry in `mcpServers` from `settings.json`.

- **Missing or non-executable binary** — resolves the `command` or first `args` entry and
  checks that the file exists and is executable. A missing binary causes silent connection
  failure on every session start.
- **Duplicate registrations** — two server entries that resolve to the same binary path
  are redundant and waste tool slots.
- **Unknown servers** — server names not in the well-known set (`jcodemunch`, `jdocmunch`,
  `serena`, `context7`, `playwright`, `figma`, `github`, `filesystem`, `memory`, `fetch`,
  `notion`) emit an INFO finding.

### Findings emitted

| Finding ID pattern | Category | Severity | Trigger |
|---|---|---|---|
| `dup-mcp-<server-id>` | `duplicate` | MEDIUM | Two entries point to the same binary |
| `missing-mcp-<server-id>` | `security` | HIGH | Binary missing or not executable |
| `unknown-mcp-<server-id>` | `verbosity` | INFO | Server name not in well-known list |

### When you'd see it

Missing-binary findings appear after uninstalling an MCP package without cleaning up
`settings.json`. Duplicate findings appear when a plugin auto-registers a server that
you already registered manually.

---

## ClaudeMdAuditor

**File:** `src/prowlr_doctor/auditors/claude_md.py`

### What it checks

Counts tokens in every `CLAUDE.md` file found — the global `~/.claude/CLAUDE.md` and
any per-project `CLAUDE.md` files in the current working directory tree.

- Files above **2,000 tokens** trigger MEDIUM (verbose)
- Files above **8,000 tokens** trigger HIGH (very large)

### Findings emitted

| Finding ID pattern | Category | Severity | Trigger |
|---|---|---|---|
| `verbose-claude-md-<dir>` | `verbosity` | MEDIUM | CLAUDE.md is 2,000–7,999 tokens |
| `verbose-claude-md-<dir>-extreme` | `verbosity` | HIGH | CLAUDE.md is 8,000+ tokens |

### When you'd see it

These findings appear in projects that have accumulated large instruction files over time —
especially when multiple personas, tool guides, and project notes have all been written
into a single `CLAUDE.md` rather than split into referenced files.

---

## MemoryAuditor

**File:** `src/prowlr_doctor/auditors/memory.py`

### What it checks

Scans all files under `~/.claude/memory/` (or equivalent memory paths).

- **Stale** — last modified more than 30 days ago
- **Large** — more than 5,000 tokens

Files that are both stale and large are HIGH severity; files that meet only one condition
are MEDIUM. Files that meet neither condition are not reported.

### Findings emitted

| Finding ID pattern | Category | Severity | Trigger |
|---|---|---|---|
| `stale-memory-<name>` | `stale` | HIGH | File is both > 30 days old and > 5k tokens |
| `stale-memory-<name>` | `stale` | MEDIUM | File is > 30 days old OR > 5k tokens (not both) |

### When you'd see it

Memory files accumulate silently. You'll see these findings for old project notes,
summaries of finished work, or auto-generated memory dumps that were never pruned.

---

## SecurityAuditor

**File:** `src/prowlr_doctor/auditors/security.py`

All detection is via static AST analysis. No hook or plugin code is executed.

### What it checks

- **Duplicate security plugins** — two or more enabled plugins with `security`, `hookify`,
  or `audit` in their `plugin.json` tags. Overlapping rules can shadow each other.
- **Dynamic code execution in hooks** — AST scan for calls to `eval`, `exec`, `compile`,
  or `__import__` inside any hook file. These are arbitrary code execution surfaces.
- **Unsafe shell invocation in hooks** — AST scan for any subprocess call with
  `shell=True` as a keyword argument. Shell metacharacters in tool arguments can trigger
  unintended OS commands.
- **Suspicious `settings.json` keys** — flags non-standard keys that may indicate tampering
  or a misconfigured plugin: `debugMode`, `allowArbitraryCode`, `disableSandbox`,
  `bypassHooks`, `skipAuth`, `noVerify`.
- **Cross-correlation** — if multiple `PreToolUse` hooks are registered AND one or more
  have broken import paths, a combined CRITICAL finding is emitted because the hooks are
  simultaneously broken and conflicting, providing zero security enforcement.

### Findings emitted

| Finding ID pattern | Category | Severity | Trigger |
|---|---|---|---|
| `dup-security-plugins` | `conflict` | HIGH | 2+ enabled plugins tagged security/hookify/audit |
| `code-exec-hook-<name>` | `security` | CRITICAL | Hook calls `eval`, `exec`, `compile`, or `__import__` |
| `unsafe-shell-kwarg-<name>` | `security` | CRITICAL | Hook passes `shell=True` to a subprocess call |
| `suspicious-setting-<key>` | `security` | CRITICAL | Non-standard key found in `settings.json` |
| `broken-security-with-conflict` | `security` | CRITICAL | Multiple `PreToolUse` hooks + at least one has broken imports |

### When you'd see it

Dynamic-execution findings appear in custom hook scripts that load or evaluate configuration
at runtime. Suspicious-settings findings appear after installing a plugin that injects
non-standard keys into `settings.json`. The cross-correlation finding is raised when the
broken-import condition (from HooksAuditor) and the multiple-hooks condition combine into
a confirmed gap in security coverage.
