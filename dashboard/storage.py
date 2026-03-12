"""SQLite-backed storage for telemetry events and aggregate stats."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

_DB_PATH = Path(__file__).parent / "telemetry.db"
_local = threading.local()

# Sonnet 4.6 pricing: $3 per 1M input tokens
_COST_PER_TOKEN = 3.0 / 1_000_000


def _conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


def init_db(db_path: Path | None = None) -> None:
    """Create tables if they don't exist. Call once at startup."""
    global _DB_PATH
    if db_path:
        _DB_PATH = db_path
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT    NOT NULL DEFAULT (datetime('now')),
            schema_ver  TEXT    NOT NULL DEFAULT '1',
            os          TEXT    NOT NULL DEFAULT '',
            profile     TEXT    NOT NULL DEFAULT '',
            py_minor    TEXT    NOT NULL DEFAULT '',
            dr_version  TEXT    NOT NULL DEFAULT '',
            plugins_enabled     INTEGER NOT NULL DEFAULT 0,
            hooks_count         INTEGER NOT NULL DEFAULT 0,
            mcp_servers_count   INTEGER NOT NULL DEFAULT 0,
            memory_files_count  INTEGER NOT NULL DEFAULT 0,
            tokens_wasted       INTEGER NOT NULL DEFAULT 0,
            tokens_saved        INTEGER NOT NULL DEFAULT 0,
            session_est_20turn  INTEGER NOT NULL DEFAULT 0,
            findings_critical   INTEGER NOT NULL DEFAULT 0,
            findings_high       INTEGER NOT NULL DEFAULT 0,
            findings_medium     INTEGER NOT NULL DEFAULT 0,
            findings_info       INTEGER NOT NULL DEFAULT 0,
            findings_fixable    INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_events_received ON events(received_at);

        CREATE TABLE IF NOT EXISTS daily_stats (
            day             TEXT PRIMARY KEY,
            audits          INTEGER NOT NULL DEFAULT 0,
            tokens_wasted   INTEGER NOT NULL DEFAULT 0,
            tokens_saved    INTEGER NOT NULL DEFAULT 0
        );
    """)
    conn.commit()


def insert_event(payload: dict) -> None:
    conn = _conn()
    conn.execute(
        """
        INSERT INTO events (
            schema_ver, os, profile, py_minor, dr_version,
            plugins_enabled, hooks_count, mcp_servers_count, memory_files_count,
            tokens_wasted, tokens_saved, session_est_20turn,
            findings_critical, findings_high, findings_medium, findings_info, findings_fixable
        ) VALUES (
            :schema_version, :os, :profile, :python_minor, :prowlr_doctor_version,
            :plugins_enabled, :hooks_count, :mcp_servers_count, :memory_files_count,
            :tokens_wasted, :tokens_savings_potential, :session_estimate_20turn,
            :findings_critical, :findings_high, :findings_medium, :findings_info, :findings_fixable
        )
        """,
        {k: payload.get(k, 0) if k not in ("schema_version", "os", "profile", "python_minor", "prowlr_doctor_version") else payload.get(k, "") for k in [
            "schema_version", "os", "profile", "python_minor", "prowlr_doctor_version",
            "plugins_enabled", "hooks_count", "mcp_servers_count", "memory_files_count",
            "tokens_wasted", "tokens_savings_potential", "session_estimate_20turn",
            "findings_critical", "findings_high", "findings_medium", "findings_info", "findings_fixable",
        ]},
    )
    conn.commit()


def get_global_stats() -> dict:
    conn = _conn()
    row = conn.execute("""
        SELECT
            COUNT(*)                    AS total_audits,
            SUM(tokens_wasted)          AS total_tokens_wasted,
            SUM(tokens_saved)           AS total_tokens_saved,
            AVG(tokens_wasted)          AS avg_tokens_wasted,
            AVG(plugins_enabled)        AS avg_plugins_enabled,
            SUM(findings_critical)      AS total_critical,
            SUM(findings_high)          AS total_high
        FROM events
    """).fetchone()

    total_saved = row["total_tokens_saved"] or 0
    money_saved = round(total_saved * _COST_PER_TOKEN, 2)

    return {
        "total_audits": row["total_audits"] or 0,
        "total_tokens_wasted": row["total_tokens_wasted"] or 0,
        "total_tokens_saved": total_saved,
        "money_saved_usd": money_saved,
        "avg_tokens_wasted_per_audit": int(row["avg_tokens_wasted"] or 0),
        "avg_plugins_per_user": round(row["avg_plugins_enabled"] or 0, 1),
        "total_critical_findings": row["total_critical"] or 0,
        "total_high_findings": row["total_high"] or 0,
    }


def get_profile_breakdown() -> list[dict]:
    conn = _conn()
    rows = conn.execute("""
        SELECT profile, COUNT(*) AS count, SUM(tokens_saved) AS tokens_saved
        FROM events
        GROUP BY profile
        ORDER BY count DESC
    """).fetchall()
    return [dict(r) for r in rows]


def get_os_breakdown() -> list[dict]:
    conn = _conn()
    rows = conn.execute("""
        SELECT os, COUNT(*) AS count
        FROM events
        WHERE os != ''
        GROUP BY os
        ORDER BY count DESC
    """).fetchall()
    return [dict(r) for r in rows]


def get_daily_trend(days: int = 30) -> list[dict]:
    conn = _conn()
    rows = conn.execute("""
        SELECT
            date(received_at) AS day,
            COUNT(*) AS audits,
            SUM(tokens_saved) AS tokens_saved
        FROM events
        WHERE received_at >= date('now', :offset)
        GROUP BY day
        ORDER BY day ASC
    """, {"offset": f"-{days} days"}).fetchall()
    return [dict(r) for r in rows]
