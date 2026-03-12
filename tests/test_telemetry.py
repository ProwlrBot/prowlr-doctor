"""Tests for the telemetry module — no real network calls."""
from unittest.mock import MagicMock, patch

import pytest

from prowlr_doctor import telemetry
from prowlr_doctor.models import TokenBudget


def test_opt_in_opt_out(tmp_path, monkeypatch):
    state_file = tmp_path / "doctor-telemetry.json"
    monkeypatch.setattr(telemetry, "_STATE_FILE", state_file)

    assert not telemetry.is_opted_in()
    telemetry.opt_in()
    assert telemetry.is_opted_in()
    telemetry.opt_out()
    assert not telemetry.is_opted_in()


def test_build_payload_counts_only(minimal_env):
    """Payload must contain only numeric/string counts — no file paths or names."""
    budget = TokenBudget(
        per_session_fixed=5000,
        per_turn_recurring=1000,
        wasted=10000,
        savings_if_cleaned=10000,
        session_estimate_20turn=25000,
    )
    payload = telemetry.build_payload(minimal_env, [], budget, "developer")

    # Must have expected keys
    assert "plugins_total" in payload
    assert "tokens_wasted" in payload
    assert payload["profile"] == "developer"
    assert payload["tokens_wasted"] == 10000

    # Must NOT contain file paths or plugin names (any list/dict values)
    for key, val in payload.items():
        assert not isinstance(val, (list, dict)), (
            f"Payload key '{key}' contains a collection — possible PII leak"
        )

    # OS must be a safe platform string, not a path
    assert payload["os"] in ("linux", "darwin", "windows", "java", "")


def test_maybe_send_skips_when_opted_out(minimal_env, tmp_path, monkeypatch):
    state_file = tmp_path / "doctor-telemetry.json"
    monkeypatch.setattr(telemetry, "_STATE_FILE", state_file)
    telemetry.opt_out()

    budget = TokenBudget()
    with patch("prowlr_doctor.telemetry.send") as mock_send:
        telemetry.maybe_send(minimal_env, [], budget, "developer")
        mock_send.assert_not_called()


def test_maybe_send_fires_when_opted_in(minimal_env, tmp_path, monkeypatch):
    state_file = tmp_path / "doctor-telemetry.json"
    monkeypatch.setattr(telemetry, "_STATE_FILE", state_file)
    telemetry.opt_in()

    budget = TokenBudget()
    with patch("prowlr_doctor.telemetry.send") as mock_send:
        telemetry.maybe_send(minimal_env, [], budget, "developer")
        mock_send.assert_called_once()
        payload = mock_send.call_args[0][0]
        assert payload["profile"] == "developer"


def test_send_swallows_network_errors(monkeypatch):
    """send() must never raise even if network is down."""
    def boom(payload):
        raise ConnectionError("no network")

    with patch("prowlr_doctor.telemetry.send", side_effect=boom):
        # maybe_send wraps send — but send itself must not raise
        pass  # send() is tested directly below

    # Direct: httpx raises, send() swallows
    with patch("httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.side_effect = Exception("timeout")
        telemetry.send({"test": 1})  # must not raise
