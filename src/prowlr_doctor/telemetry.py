"""Opt-in anonymous telemetry client.

Payload contains only aggregate counts — no PII, no file paths, no plugin names.
Opt-in state persists to ~/.claude/doctor-telemetry.json.
All network calls are fire-and-forget with a 3s timeout; never blocks the user.
"""
from __future__ import annotations

import json
import logging
import os
import platform
from pathlib import Path

from prowlr_doctor import __version__
from prowlr_doctor.models import EnvironmentSnapshot, Finding, TokenBudget

logger = logging.getLogger(__name__)

_TELEMETRY_ENDPOINT = "https://doctor.prowlrbot.com/telemetry"
_STATE_FILE = Path.home() / ".claude" / "doctor-telemetry.json"


def _load_state() -> dict:
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_state(state: dict) -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


def is_opted_in() -> bool:
    return _load_state().get("opted_in", False)


def opt_in() -> None:
    state = _load_state()
    state["opted_in"] = True
    _save_state(state)


def opt_out() -> None:
    state = _load_state()
    state["opted_in"] = False
    _save_state(state)


def build_payload(
    env: EnvironmentSnapshot,
    findings: list[Finding],
    budget: TokenBudget,
    profile: str,
) -> dict:
    """Build a telemetry payload. Counts only — no strings that could contain PII."""
    return {
        "schema_version": "1",
        "prowlr_doctor_version": __version__,
        "os": platform.system().lower(),          # "linux", "darwin", "windows"
        "python_minor": f"{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}",
        "profile": profile,
        # Environment counts
        "plugins_total": len(env.enabled_plugins),
        "plugins_enabled": sum(1 for v in env.enabled_plugins.values() if v),
        "hooks_count": len(env.hooks),
        "mcp_servers_count": len(env.mcp_servers),
        "memory_files_count": len(env.memory_files),
        # Token metrics
        "tokens_wasted": budget.wasted,
        "tokens_savings_potential": budget.savings_if_cleaned,
        "session_estimate_20turn": budget.session_estimate_20turn,
        # Finding counts by severity
        "findings_critical": sum(1 for f in findings if f.severity.name == "CRITICAL"),
        "findings_high": sum(1 for f in findings if f.severity.name == "HIGH"),
        "findings_medium": sum(1 for f in findings if f.severity.name == "MEDIUM"),
        "findings_info": sum(1 for f in findings if f.severity.name == "INFO"),
        "findings_fixable": sum(1 for f in findings if f.fix_action is not None),
    }


def send(payload: dict) -> None:
    """Fire-and-forget POST. Silently swallows all errors."""
    try:
        import httpx
        with httpx.Client(timeout=3.0) as client:
            client.post(_TELEMETRY_ENDPOINT, json=payload)
    except Exception as exc:
        logger.debug("Telemetry send failed (non-fatal): %s", exc)


def maybe_send(
    env: EnvironmentSnapshot,
    findings: list[Finding],
    budget: TokenBudget,
    profile: str,
) -> None:
    """Send telemetry if opted in. Never raises, never blocks more than 3s."""
    if not is_opted_in():
        return
    payload = build_payload(env, findings, budget, profile)
    send(payload)
