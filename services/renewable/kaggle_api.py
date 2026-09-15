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
    assetId: str | None = Query(default=None),
    timestamp: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    from datetime import datetime, timezone, timedelta

    raw_asset_id = assetId if isinstance(assetId, str) else None
    raw_timestamp = timestamp if isinstance(timestamp, str) else None

    try:
        # If no specific asset requested, return status for representative assets
        # (scanning all ~120 countries takes 18+ minutes on cold start)
        if not raw_asset_id:
            representative_assets = [
                "NL_solar_generation_actual",
                "NL_wind_onshore_generation_actual",
                "DE_solar_generation_actual",
                "DE_wind_onshore_generation_actual",
                "FR_solar_generation_actual",
                "FR_wind_onshore_generation_actual",
            ]
            statuses: list[dict[str, Any]] = []
            for rep_asset in representative_assets:
                try:
                    result = getRenewableStatus(rep_asset, "2020-09-30T12:00:00Z")
                    statuses.append(to_renewable_status(result))
                except Exception:
                    continue
            if not statuses:
                # Fallback to synthetic assets if no Kaggle results available
                from .renewable_service import getRenewableStatus as get_synth_status
                try:
                    statuses.append(to_renewable_status(get_synth_status("solar_park_synth_01", "2024-12-30T23:45:00+00:00")))
                    statuses.append(to_renewable_status(get_synth_status("wind_park_synth_01", "2024-12-30T23:45:00+00:00")))
                except Exception:
                    pass
            return statuses

        if raw_asset_id in {"solar_park_synth_01", "wind_park_synth_01"}:
            from .renewable_service import getRenewableStatus as get_synth_status
            target_ts = raw_timestamp or "2024-12-30T23:45:00+00:00"
            return [to_renewable_status(get_synth_status(raw_asset_id, target_ts))]

        # Specific asset + timestamp requested
        target_ts = raw_timestamp or "2020-09-30T23:00:00Z"

        energy_type = "solar" if "_solar_" in raw_asset_id else "wind"
        root_model = Path(DEFAULT_ROOT_CAUSE_DIR) / f"kaggle_root_cause_xgb_{energy_type}.pkl"
        if not root_model.exists():
            raise HTTPException(
                status_code=503,
                detail={"code": "MISSING_ROOT_CAUSE_MODEL", "message": f"Kaggle root-cause artifact unavailable for {energy_type}."},
            )
        return [to_renewable_status(getRenewableStatus(raw_asset_id, target_ts))]
    except HTTPException:
        raise
    except KaggleRenewableServiceError as error:
        raise _availability_error(error) from error
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "KAGGLE_DATASET_UNAVAILABLE",
                "message": (
                    "Kaggle renewable time-series dataset not found. "
                    "Download 'time_series_60min_singleindex.csv' from the Open Power System Data "
                    "dataset and place it in ml/datasets/kaggle_power_system/. "
                    f"Missing file: {exc}"
                ),
            },
        ) from exc


@app.get("/status/anomalies")
def anomalies(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    assetId: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    from datetime import datetime, timezone, timedelta

    raw_start = start if isinstance(start, str) else None
    raw_end = end if isinstance(end, str) else None
    raw_asset_id = assetId if isinstance(assetId, str) else None

    if not raw_end:
        # Default end to latest dataset timestamp (2020-09-30) rather than current live clock
        resolved_end = "2020-09-30T23:00:00Z"
        resolved_start = "2020-09-29T23:00:00Z"
    else:
        now = datetime.now(timezone.utc)
        resolved_end = raw_end
        resolved_start = raw_start or (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        opts: dict[str, Any] = {"start": resolved_start, "end": resolved_end}
        if raw_asset_id:
            opts["asset_id"] = raw_asset_id
        else:
            # Limit default scan to representative assets to avoid 18+ minute full scan
            representative = [
                "NL_solar_generation_actual",
                "NL_wind_onshore_generation_actual",
                "DE_solar_generation_actual",
                "DE_wind_onshore_generation_actual",
                "FR_solar_generation_actual",
                "FR_wind_onshore_generation_actual",
            ]
            all_results: list[dict[str, Any]] = []
            for asset in representative:
                try:
                    single_opts = {**opts, "asset_id": asset}
                    all_results.extend(detectAnomalies(single_opts))
                except Exception:
                    continue
            return [to_renewable_status(r) for r in all_results]
        results = detectAnomalies(opts)
        return [to_renewable_status(result) for result in results]
    except KaggleRenewableServiceError as error:
        raise _availability_error(error) from error
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "KAGGLE_DATASET_UNAVAILABLE",
                "message": (
                    "Kaggle renewable time-series dataset not found. "
                    "Download 'time_series_60min_singleindex.csv' from the Open Power System Data "
                    "dataset and place it in ml/datasets/kaggle_power_system/. "
                    f"Missing file: {exc}"
                ),
            },
        ) from exc
