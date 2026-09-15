"""FastAPI HTTP adapter for Data / Telemetry Service (Port 8001)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, Query
import pandas as pd

app = FastAPI(title="GridPilot Data Telemetry Service", version="1.0.0")

_parquet_path = Path("ml/datasets/openstef_demand_clean.parquet")
_cached_df: pd.DataFrame | None = None


def _get_latest_demand(zone_id: str) -> float:
    global _cached_df
    try:
        if _cached_df is None and _parquet_path.exists():
            _cached_df = pd.read_parquet(_parquet_path)
        if _cached_df is not None and not _cached_df.empty:
            matches = _cached_df[_cached_df["asset_id"].str.lower() == zone_id.lower()]
            if not matches.empty:
                val = float(matches.iloc[-1]["demand_mw"])
                if val > 0:
                    return val
    except Exception:
        pass
    return 85.4


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "data_telemetry"}


@app.get("/api/grid/state")
def get_grid_state(zoneId: str = Query("NL_LIANDER_SUB_01")) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    demand = _get_latest_demand(zoneId)
    solar = 12.3
    wind = 8.7
    net_load = round(demand - (solar + wind), 2)
    return {
        "timestamp": now_iso,
        "zoneId": zoneId,
        "substationId": zoneId,
        "demandMw": round(demand, 2),
        "solarGenerationMw": solar,
        "windGenerationMw": wind,
        "netLoadMw": net_load,
        "batterySocPercent": 55.0,
        "batteryPowerMw": 0.0,
        "curtailmentMw": 0.0,
        "gridFrequencyHz": 50.02,
        "gridStressIndex": 0.42,
        "activeAlertsCount": 0,
        "transformerCapacityMw": 100.0,
    }
