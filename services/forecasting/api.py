"""FastAPI HTTP adapter for Demand Forecasting Service (Port 8002)."""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query

from services.forecasting.service import DemandForecastService
from services.forecasting.errors import ForecastServiceError

app = FastAPI(title="GridPilot Forecasting Service", version="1.0.0")

_service = None


def get_service() -> DemandForecastService:
    global _service
    if _service is None:
        _service = DemandForecastService()
    return _service


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "demand_forecasting"}


@app.get("/forecast/demand")
def forecast_demand(
    zoneId: str = Query("NL_LIANDER_SUB_01"),
    horizon: int = Query(15),
) -> dict:
    try:
        service = get_service()
        now_iso = datetime.now(timezone.utc).isoformat()
        return service.forecast_demand(
            zone_id=zoneId,
            start_time=now_iso,
            horizon=horizon,
        )
    except ForecastServiceError as err:
        raise HTTPException(
            status_code=503 if err.error_code == "MODEL_UNAVAILABLE" else 400,
            detail={"code": err.error_code, "message": str(err)},
        ) from err
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "FORECAST_INFERENCE_ERROR", "message": str(exc)},
        ) from exc
