"""FastAPI server — telemetry intake + stats API + static dashboard."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from dashboard.storage import (
    get_daily_trend,
    get_global_stats,
    get_os_breakdown,
    get_profile_breakdown,
    init_db,
    insert_event,
)

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Dashboard DB initialized.")
    yield


app = FastAPI(
    title="ProwlrDoctor Dashboard",
    description="Community aggregate stats for prowlr-doctor audits.",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Telemetry intake ─────────────────────────────────────────────────────────

_REQUIRED_INT_FIELDS = {
    "plugins_enabled", "hooks_count", "mcp_servers_count", "memory_files_count",
    "tokens_wasted", "tokens_savings_potential", "session_estimate_20turn",
    "findings_critical", "findings_high", "findings_medium", "findings_info", "findings_fixable",
}
_ALLOWED_FIELDS = _REQUIRED_INT_FIELDS | {
    "schema_version", "os", "profile", "python_minor", "prowlr_doctor_version",
    "plugins_total",
}
_MAX_TOKENS = 10_000_000  # sanity cap — reject implausible payloads


@app.post("/telemetry", status_code=202)
async def receive_telemetry(request: Request) -> dict:
    """Accept an opt-in telemetry payload and store aggregate counts."""
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Strip any keys not in the allowlist — no PII can sneak in
    cleaned = {k: v for k, v in payload.items() if k in _ALLOWED_FIELDS}

    # Validate integer fields are actually integers and within sane bounds
    for field in _REQUIRED_INT_FIELDS:
        val = cleaned.get(field, 0)
        if not isinstance(val, int) or val < 0 or val > _MAX_TOKENS:
            cleaned[field] = 0

    # Validate string fields are short strings (not paths or names)
    for field in ("os", "profile", "python_minor", "prowlr_doctor_version", "schema_version"):
        val = cleaned.get(field, "")
        if not isinstance(val, str) or len(val) > 32:
            cleaned[field] = ""

    try:
        insert_event(cleaned)
    except Exception as exc:
        logger.error("Failed to insert telemetry event: %s", exc)
        # Still return 202 — don't punish clients for server errors
        return {"status": "accepted"}

    return {"status": "accepted"}


# ── Stats API ─────────────────────────────────────────────────────────────────


@app.get("/api/stats")
async def global_stats() -> dict:
    """Aggregate stats for the dashboard."""
    return {
        "global": get_global_stats(),
        "by_profile": get_profile_breakdown(),
        "by_os": get_os_breakdown(),
        "trend_30d": get_daily_trend(30),
    }


@app.get("/api/stats/global")
async def global_stats_only() -> dict:
    return get_global_stats()


# ── Dashboard UI ──────────────────────────────────────────────────────────────


@app.get("/")
async def dashboard() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
