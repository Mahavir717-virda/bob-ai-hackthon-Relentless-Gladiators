"""HTTP adapter exposing Kaggle renewable inference on the gateway service port.

This module performs request/contract adaptation only.  It does not train,
modify, or synthesize model outputs.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from .kaggle_service import (
    DEFAULT_ANOMALY_DIR,
    DEFAULT_ROOT_CAUSE_DIR,
    KaggleRenewableServiceError,
    detectAnomalies,
    getRenewableStatus,
)


app = FastAPI(title="GridPilot Kaggle Renewable Service", version="1.0.0")


def _availability_error(error: KaggleRenewableServiceError) -> HTTPException:
    status = 503 if error.code in {
        "MISSING_FORECAST_MODEL",
        "MISSING_ANOMALY_MODEL",
        "CORRUPTED_FORECAST_MODEL",
        "CORRUPTED_ANOMALY_MODEL",
    } else 400
    if error.code == "UNKNOWN_ASSET":
        status = 404
    if error.code == "TIMESTAMP_OUT_OF_RANGE":
        status = 404
    return HTTPException(status_code=status, detail={"code": error.code, "message": str(error)})


def _number(raw: dict[str, Any], key: str) -> float:
    value = raw.get(key)
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "KAGGLE_INFERENCE_UNAVAILABLE",
                "message": f"Kaggle inference did not produce a usable {key} value.",
            },
        )
    if key in {"actual_mw", "expected_mw", "performance_ratio"} and value < 0:
        raise HTTPException(
            status_code=503,
            detail={"code": "KAGGLE_INFERENCE_UNAVAILABLE", "message": f"Kaggle inference produced an invalid {key} value."},
        )
    return float(value)


def to_renewable_status(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a Kaggle aggregate-series result into the shared RenewableStatus shape."""
    anomaly = raw.get("anomaly_flag")
    if not isinstance(anomaly, bool):
        raise HTTPException(
            status_code=503,
            detail={"code": "KAGGLE_INFERENCE_UNAVAILABLE", "message": "Kaggle anomaly inference is unavailable."},
        )
    status: dict[str, Any] = {
        "assetId": str(raw["asset_id"]),
        "assetType": str(raw["energy_type"]),
        "timestamp": str(raw["timestamp"]),
        "expectedMw": _number(raw, "expected_mw"),
        "actualMw": _number(raw, "actual_mw"),
        "performanceRatio": _number(raw, "performance_ratio"),
        "anomaly": anomaly,
    }
    # Isolation Forest decision_function is not a probability, so it must not
    # be exposed through RenewableStatus.anomalyScore (which is constrained 0-1).
    confidence = raw.get("confidence")
    category = raw.get("root_cause")
    if isinstance(confidence, (int, float)) and math.isfinite(confidence) and 0 <= confidence <= 1 and isinstance(category, str):
        status["likelyRootCause"] = {
            "category": category,
            "confidence": float(confidence),
            "evidence": json.dumps(raw.get("evidence", [])),
        }
    return status


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "source": "kaggle_power_system"}


@app.get("/status")
def status(
    assetId: str = Query(..., min_length=1),
    timestamp: str = Query(..., min_length=1),
) -> list[dict[str, Any]]:
    try:
        energy_type = "solar" if "_solar_" in assetId else "wind"
        root_model = Path(DEFAULT_ROOT_CAUSE_DIR) / f"kaggle_root_cause_xgb_{energy_type}.pkl"
        if not root_model.exists():
            raise HTTPException(
                status_code=503,
                detail={"code": "MISSING_ROOT_CAUSE_MODEL", "message": f"Kaggle root-cause artifact unavailable for {energy_type}."},
            )
        return [to_renewable_status(getRenewableStatus(assetId, timestamp))]
    except KaggleRenewableServiceError as error:
        raise _availability_error(error) from error


@app.get("/status/anomalies")
def anomalies(
    start: str = Query(..., min_length=1),
    end: str = Query(..., min_length=1),
    assetId: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    try:
        results = detectAnomalies({"start": start, "end": end, "asset_id": assetId} if assetId else {"start": start, "end": end})
        return [to_renewable_status(result) for result in results]
    except KaggleRenewableServiceError as error:
        raise _availability_error(error) from error
