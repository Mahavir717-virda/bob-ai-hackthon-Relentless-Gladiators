"""Kaggle Renewable Intelligence service integration.

This service is deliberately separate from ``renewable_service.py`` because
Kaggle records are hourly aggregate series and have no weather features. It
loads persisted Step 3-5 artifacts only; requests never retrain models.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .kaggle_anomaly import (
    calculate_kaggle_performance,
    detect_kaggle_anomalies,
    load_kaggle_anomaly_detector,
)
from .kaggle_data_loader import DEFAULT_RESOLUTION, discover_kaggle_schema, kaggle_csv_path
from .kaggle_forecasting import _feature_frame, load_kaggle_forecaster
from .kaggle_root_cause import explain_kaggle_row, load_kaggle_root_cause_model


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_DIR = PROJECT_ROOT / "ml" / "datasets" / "kaggle_power_system"
DEFAULT_FORECAST_DIR = PROJECT_ROOT / "ml" / "models" / "renewable" / "artifacts" / "kaggle"
DEFAULT_ANOMALY_DIR = PROJECT_ROOT / "ml" / "models" / "renewable" / "artifacts" / "kaggle_anomaly"
DEFAULT_ROOT_CAUSE_DIR = DEFAULT_FORECAST_DIR


class KaggleRenewableServiceError(ValueError):
    """Stable error with a machine-readable code for Kaggle service callers."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.reason = code


_SOURCE_CACHE: dict[Path, pd.DataFrame] = {}
_SCHEMA_CACHE: dict[Path, Any] = {}
_FORECAST_CACHE: dict[Path, Any] = {}
_ANOMALY_CACHE: dict[Path, dict[str, Any]] = {}
_ROOT_CAUSE_CACHE: dict[str, dict[str, Any]] = {}


def clear_kaggle_service_cache() -> None:
    """Clear process-local data/model caches, primarily for tests."""
    _SOURCE_CACHE.clear()
    _SCHEMA_CACHE.clear()
    _FORECAST_CACHE.clear()
    _ANOMALY_CACHE.clear()
    _ROOT_CAUSE_CACHE.clear()


def _source(dataset_dir: Path) -> pd.DataFrame:
    path = kaggle_csv_path(dataset_dir)
    if path not in _SOURCE_CACHE:
        _SOURCE_CACHE[path] = pd.read_csv(path)
    return _SOURCE_CACHE[path]


def _schema(dataset_dir: Path):
    path = kaggle_csv_path(dataset_dir)
    if path not in _SCHEMA_CACHE:
        _SCHEMA_CACHE[path] = discover_kaggle_schema(path)
    return _SCHEMA_CACHE[path]


def _timestamp(value: Any) -> pd.Timestamp:
    try:
        parsed = pd.to_datetime(value, utc=True, errors="raise")
    except (TypeError, ValueError, OverflowError) as exc:
        raise KaggleRenewableServiceError("INVALID_TIMESTAMP", f"Invalid timestamp: {value!r}") from exc
    if isinstance(parsed, pd.DatetimeIndex):
        raise KaggleRenewableServiceError("INVALID_TIMESTAMP", "A single timestamp is required.")
    return parsed


def _asset_info(asset_id: str, dataset_dir: Path) -> tuple[str, str | None]:
    schema = _schema(dataset_dir)
    if asset_id not in schema.generation_columns:
        raise KaggleRenewableServiceError("UNKNOWN_ASSET", f"Unknown Kaggle aggregate series: {asset_id!r}")
    energy_type = "solar" if "_solar_" in asset_id else "wind"
    return energy_type, schema.capacity_by_generation[asset_id]


def _forecast_artifacts(asset_id: str, forecast_dir: Path) -> tuple[Any, dict[str, Any]]:
    stem = asset_id.replace("/", "_").replace(" ", "_")
    model_path = forecast_dir / f"kaggle_lgbm_{stem}.pkl"
    metadata_path = forecast_dir / f"kaggle_lgbm_{stem}_metadata.json"
    if not model_path.exists() or not metadata_path.exists():
        raise KaggleRenewableServiceError("MISSING_FORECAST_MODEL", f"Forecast artifact unavailable for {asset_id!r}.")
    if model_path not in _FORECAST_CACHE:
        try:
            _FORECAST_CACHE[model_path] = (load_kaggle_forecaster(model_path), json.loads(metadata_path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            raise KaggleRenewableServiceError("CORRUPTED_FORECAST_MODEL", f"Could not load forecast artifact for {asset_id!r}.") from exc
    return _FORECAST_CACHE[model_path]


def _build_asset_frame(asset_id: str, dataset_dir: Path, forecast_dir: Path) -> pd.DataFrame:
    source = _source(dataset_dir)
    energy_type, capacity_column = _asset_info(asset_id, dataset_dir)
    model, metadata = _forecast_artifacts(asset_id, forecast_dir)
    frame = _feature_frame(source, asset_id, capacity_column)
    forecast_features = list(metadata["features"])
    required = [column for column in forecast_features if column not in {"capacity_mw", "capacity_available", "lagged_generation_ratio"}]
    eligible = frame[required].notna().all(axis=1)
    expected = pd.Series(np.nan, index=frame.index, dtype=float)
    if eligible.any():
        expected.loc[eligible] = np.maximum(model.predict(frame.loc[eligible, forecast_features]), 0.0)
    capacity = frame["capacity_mw"]
    performance = calculate_kaggle_performance(frame["target_mw"], expected, capacity)
    result = pd.DataFrame({
        "timestamp": frame["timestamp"], "asset_id": asset_id, "energy_type": energy_type,
        "actual_mw": performance["actual_mw"], "expected_mw": performance["expected_mw"],
        "absolute_deviation_mw": performance["absolute_deviation_mw"],
        "absolute_error_mw": performance["absolute_error_mw"],
        "percentage_deviation": performance["percentage_deviation"],
        "performance_ratio": performance["performance_ratio"],
        "capacity_mw": capacity,
        "capacity_ratio": performance["generation_capacity_ratio"],
        "generation_capacity_ratio": performance["generation_capacity_ratio"],
        "expected_capacity_ratio": performance["expected_capacity_ratio"],
        "zero_or_missing_expected": performance["zero_or_missing_expected"],
        "curtailment_status": "unknown",
    })
    return result


def _asset_frame(asset_id: str, dataset_dir: Path, forecast_dir: Path) -> pd.DataFrame:
    key = (dataset_dir / f"{asset_id}::{forecast_dir}")
    if key not in _SOURCE_CACHE:
        _SOURCE_CACHE[key] = _build_asset_frame(asset_id, dataset_dir, forecast_dir)
    return _SOURCE_CACHE[key]


def _anomaly_row(row: pd.Series, anomaly_dir: Path) -> pd.Series:
    stem = str(row["asset_id"]).replace("/", "_").replace(" ", "_")
    path = anomaly_dir / f"kaggle_isolation_forest_{stem}.pkl"
    if not path.exists():
        raise KaggleRenewableServiceError("MISSING_ANOMALY_MODEL", f"Anomaly artifact unavailable for {row['asset_id']!r}.")
    if path not in _ANOMALY_CACHE:
        try:
            _ANOMALY_CACHE[path] = load_kaggle_anomaly_detector(path)
        except Exception as exc:  # noqa: BLE001
            raise KaggleRenewableServiceError("CORRUPTED_ANOMALY_MODEL", f"Could not load anomaly artifact for {row['asset_id']!r}.") from exc
    performance = row.to_frame().T
    detected = detect_kaggle_anomalies(performance, _ANOMALY_CACHE[path])
    return detected.iloc[0]


def _root_cause(row: pd.Series, anomaly_flag: Any, root_cause_dir: Path) -> dict[str, Any]:
    energy_type = str(row["energy_type"])
    model_path = root_cause_dir / f"kaggle_root_cause_xgb_{energy_type}.pkl"
    if not model_path.exists():
        return {
            "root_cause": "insufficient evidence", "confidence": None, "evidence": [],
            "curtailment_status": "unknown", "reason": "root-cause artifact unavailable",
        }
    if energy_type not in _ROOT_CAUSE_CACHE:
        try:
            _ROOT_CAUSE_CACHE[energy_type] = load_kaggle_root_cause_model(energy_type, root_cause_dir)
        except Exception:
            return {
                "root_cause": "insufficient evidence", "confidence": None, "evidence": [],
                "curtailment_status": "unknown", "reason": "root-cause artifact could not be loaded",
            }
    # Root-cause features are the persisted model's prepared association inputs.
    prepared = row.copy()
    from .kaggle_root_cause import ROOT_FEATURE_COLUMNS
    for column in ROOT_FEATURE_COLUMNS:
        if column not in prepared.index:
            prepared[column] = np.nan
    return explain_kaggle_row(prepared, _ROOT_CAUSE_CACHE[energy_type], bool(anomaly_flag) if not pd.isna(anomaly_flag) else None)


def _status(row: pd.Series, anomaly_row: pd.Series, root: dict[str, Any]) -> dict[str, Any]:
    def nullable(value: Any) -> float | None:
        return None if pd.isna(value) else float(value)

    return {
        "asset_id": str(row["asset_id"]), "timestamp": row["timestamp"].isoformat(),
        "energy_type": str(row["energy_type"]), "actual_mw": nullable(row["actual_mw"]),
        "expected_mw": nullable(row["expected_mw"]),
        "absolute_deviation_mw": nullable(row["absolute_deviation_mw"]),
        "percentage_deviation": nullable(row["percentage_deviation"]),
        "performance_ratio": nullable(row["performance_ratio"]),
        "capacity_mw": nullable(row["capacity_mw"]), "capacity_ratio": nullable(row["capacity_ratio"]),
        "anomaly_flag": None if pd.isna(anomaly_row["anomaly_flag"]) else bool(anomaly_row["anomaly_flag"]),
        "anomaly_score": nullable(anomaly_row["anomaly_score"]),
        "curtailment_status": "unknown", "root_cause": root.get("root_cause", "insufficient evidence"),
        "confidence": root.get("confidence"), "evidence": root.get("evidence", []),
        "uncertainty": root.get("reason") or root.get("association_disclaimer"),
        "weather_available": False,
    }


def getRenewableStatus(
    assetId: str,
    timestamp: Any,
    dataset_dir: str | Path = DEFAULT_DATASET_DIR,
    forecast_dir: str | Path = DEFAULT_FORECAST_DIR,
    anomaly_dir: str | Path = DEFAULT_ANOMALY_DIR,
    root_cause_dir: str | Path = DEFAULT_ROOT_CAUSE_DIR,
) -> dict[str, Any]:
    """Return one consolidated Kaggle RenewableStatus-like result."""
    if not isinstance(assetId, str) or not assetId.strip():
        raise KaggleRenewableServiceError("INVALID_ASSET_ID", "assetId must be a non-empty string.")
    requested = _timestamp(timestamp)
    frame = _asset_frame(assetId, Path(dataset_dir), Path(forecast_dir))
    matches = frame.loc[frame["timestamp"].eq(requested)]
    if matches.empty:
        raise KaggleRenewableServiceError("TIMESTAMP_OUT_OF_RANGE", f"No observation exists at {requested.isoformat()} for {assetId!r}.")
    row = matches.iloc[0]
    anomaly_row = _anomaly_row(row, Path(anomaly_dir))
    anomaly_flag = None if pd.isna(anomaly_row["anomaly_flag"]) else bool(anomaly_row["anomaly_flag"])
    root = _root_cause(row, anomaly_flag, Path(root_cause_dir)) if anomaly_flag is True else {
        "root_cause": "insufficient evidence", "confidence": None, "evidence": [],
        "curtailment_status": "unknown", "reason": "row is not an evaluated anomaly",
    }
    return _status(row, anomaly_row, root)


def detectAnomalies(
    timeRange: dict[str, Any],
    dataset_dir: str | Path = DEFAULT_DATASET_DIR,
    forecast_dir: str | Path = DEFAULT_FORECAST_DIR,
    anomaly_dir: str | Path = DEFAULT_ANOMALY_DIR,
    root_cause_dir: str | Path = DEFAULT_ROOT_CAUSE_DIR,
) -> list[dict[str, Any]]:
    """Return consolidated anomalous statuses in a validated time range."""
    if not isinstance(timeRange, dict) or "start" not in timeRange or "end" not in timeRange:
        raise KaggleRenewableServiceError("INVALID_TIME_RANGE", "timeRange must contain start and end.")
    start, end = _timestamp(timeRange["start"]), _timestamp(timeRange["end"])
    if start > end:
        raise KaggleRenewableServiceError("INVALID_TIME_RANGE", "timeRange start must not exceed end.")
    schema = _schema(Path(dataset_dir))
    asset_ids = [timeRange["asset_id"]] if timeRange.get("asset_id") else list(schema.generation_columns)
    statuses: list[dict[str, Any]] = []
    for asset_id in asset_ids:
        frame = _asset_frame(asset_id, Path(dataset_dir), Path(forecast_dir))
        selected = frame.loc[frame["timestamp"].between(start, end)]
        for _, row in selected.iterrows():
            anomaly_row = _anomaly_row(row, Path(anomaly_dir))
            if pd.isna(anomaly_row["anomaly_flag"]) or not bool(anomaly_row["anomaly_flag"]):
                continue
            root = _root_cause(row, True, Path(root_cause_dir))
            statuses.append(_status(row, anomaly_row, root))
    return statuses


def analyzeRootCause(
    assetId: str,
    timestamp: Any,
    dataset_dir: str | Path = DEFAULT_DATASET_DIR,
    forecast_dir: str | Path = DEFAULT_FORECAST_DIR,
    anomaly_dir: str | Path = DEFAULT_ANOMALY_DIR,
    root_cause_dir: str | Path = DEFAULT_ROOT_CAUSE_DIR,
) -> dict[str, Any]:
    """Return persisted Kaggle SHAP association evidence for one timestamp."""
    status = getRenewableStatus(assetId, timestamp, dataset_dir, forecast_dir, anomaly_dir, root_cause_dir)
    return {
        "asset_id": status["asset_id"], "timestamp": status["timestamp"],
        "energy_type": status["energy_type"], "root_cause": status["root_cause"],
        "confidence": status["confidence"], "evidence": status["evidence"],
        "curtailment_status": status["curtailment_status"], "uncertainty": status["uncertainty"],
    }