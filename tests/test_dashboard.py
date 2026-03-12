"""Tests for dashboard server — telemetry intake and stats API."""
import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi", reason="fastapi not installed")

from dashboard.storage import init_db, insert_event, get_global_stats
from dashboard.server import app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Each test gets an isolated in-memory SQLite database."""
    import dashboard.storage as storage_mod
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(storage_mod, "_DB_PATH", db_path)
    # Reset thread-local connection so it picks up the new path
    import threading
    storage_mod._local = threading.local()
    init_db(db_path)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ── Telemetry intake ──────────────────────────────────────────────────────────

def test_telemetry_accepts_valid_payload(client):
    payload = {
        "schema_version": "1",
        "os": "linux",
        "profile": "developer",
        "python_minor": "3.11",
        "prowlr_doctor_version": "0.1.0",
        "plugins_enabled": 30,
        "hooks_count": 8,
        "mcp_servers_count": 2,
        "memory_files_count": 5,
        "tokens_wasted": 133533,
        "tokens_savings_potential": 133533,
        "session_estimate_20turn": 114400,
        "findings_critical": 1,
        "findings_high": 2,
        "findings_medium": 3,
        "findings_info": 0,
        "findings_fixable": 3,
    }
    resp = client.post("/telemetry", json=payload)
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"


def test_telemetry_strips_unknown_keys(client):
    """Unknown keys (possible PII) must be silently dropped."""
    payload = {
        "schema_version": "1",
        "os": "linux",
        "profile": "developer",
        "secret_key": "should-be-dropped",
        "username": "should-be-dropped",
        "tokens_wasted": 1000,
    }
    resp = client.post("/telemetry", json=payload)
    assert resp.status_code == 202
    # Verify nothing leaked into storage
    stats = get_global_stats()
    assert stats["total_audits"] == 1


def test_telemetry_rejects_bad_json(client):
    resp = client.post("/telemetry", content=b"not json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 400


def test_telemetry_clamps_implausible_values(client):
    """Token counts above the sanity cap are clamped to 0, not rejected."""
    payload = {
        "schema_version": "1",
        "os": "linux",
        "profile": "developer",
        "tokens_wasted": 999_999_999_999,  # implausible
    }
    resp = client.post("/telemetry", json=payload)
    assert resp.status_code == 202


# ── Stats API ─────────────────────────────────────────────────────────────────

def test_stats_empty_db(client):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["global"]["total_audits"] == 0
    assert data["global"]["total_tokens_saved"] == 0
    assert "by_profile" in data
    assert "by_os" in data
    assert "trend_30d" in data


def test_stats_accumulates(client):
    for _ in range(3):
        client.post("/telemetry", json={
            "schema_version": "1", "os": "linux", "profile": "developer",
            "tokens_wasted": 10000, "tokens_savings_potential": 5000,
        })
    resp = client.get("/api/stats/global")
    assert resp.status_code == 200
    g = resp.json()
    assert g["total_audits"] == 3
    assert g["total_tokens_saved"] == 15000


def test_stats_profile_breakdown(client):
    client.post("/telemetry", json={"schema_version": "1", "os": "linux",
                                    "profile": "developer", "tokens_wasted": 0})
    client.post("/telemetry", json={"schema_version": "1", "os": "linux",
                                    "profile": "security", "tokens_wasted": 0})
    client.post("/telemetry", json={"schema_version": "1", "os": "linux",
                                    "profile": "developer", "tokens_wasted": 0})
    data = client.get("/api/stats").json()
    profiles = {r["profile"]: r["count"] for r in data["by_profile"]}
    assert profiles["developer"] == 2
    assert profiles["security"] == 1


def test_dashboard_html_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"ProwlrDoctor" in resp.content
    assert b"Community Dashboard" in resp.content


def test_money_saved_calculation(client):
    """Verify money_saved_usd uses $3/1M tokens pricing."""
    client.post("/telemetry", json={
        "schema_version": "1", "os": "linux", "profile": "developer",
        "tokens_savings_potential": 1_000_000,
    })
    g = client.get("/api/stats/global").json()
    assert abs(g["money_saved_usd"] - 3.0) < 0.01
