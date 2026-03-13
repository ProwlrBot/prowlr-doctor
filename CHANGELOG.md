# Changelog

All notable changes to prowlr-doctor are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Fixed
- Plugin path resolution now correctly uses `registry/name/version/` layout instead of `name/registry`.

---

## [0.1.0] — Initial release

### Added
- Sub-project 1: core diagnostic scanner — checks config, providers, MCP servers, skills, and environment health.
- Sub-project 2: Textual TUI for interactive terminal diagnostics with live output.
- Sub-project 3: deeper security checks (shell allowlist, path traversal, JWT config) plus opt-in anonymous telemetry.
- Sub-project 4: community dashboard with telemetry intake API, stats aggregation, and a browser UI.
- `jdocmunch` and `notion` added to the well-known MCP server list so the scanner recognizes them.
- Comprehensive README covering installation, usage, all sub-projects, and contributing guide.

---

[Unreleased]: https://github.com/ProwlrBot/prowlr-doctor/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ProwlrBot/prowlr-doctor/releases/tag/v0.1.0
