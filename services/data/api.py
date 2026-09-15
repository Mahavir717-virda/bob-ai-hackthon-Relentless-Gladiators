"""FastAPI HTTP adapter for Data / Telemetry Service (Port 8001)."""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import FastAPI, Query

app = FastAPI(title="GridPilot Data Telemetry Service", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "data_telemetry"}


@app.get("/api/grid/state")
def get_grid_state(zoneId: str = Query("NL_LIANDER_SUB_01")) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "timestamp": now_iso,
        "substationId": zoneId,
        "activeLoadMw": 85.4,
        "solarGenerationMw": 12.3,
        "windGenerationMw": 8.7,
        "netLoadMw": 64.4,
        "transformerCapacityMw": 100.0,
        "gridStressIndex": 0.42,
        "batterySocPercent": 55.0,
    }
