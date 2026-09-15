"""Contract-shaped orchestration for the renewable intelligence pipeline.

The private ``_ASSET_REGISTRY`` is checked first, so API integration and test
overrides take priority. If an entry is absent, the service attempts the real
OpenSTEF data/model pipeline and then its calibrated synthetic counterpart.
Asset entries are supplied through the private ``_ASSET_REGISTRY`` mapping.
Each entry contains an asset type, a DataFrame of timestamped upstream
forecast outputs (``expected_mw``) and observations (``actual_mw``), optional
weather, and optionally a persisted model path. Forecast values are retained
rather than recalculated here, preserving this module's orchestration-only
boundary.

The registry remains a test/integration seam.  Its absence no longer prevents
operation when a supported local model and either downloaded OpenSTEF data or
the matching calibrated synthetic fixture are available.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import logging

from .anomaly_detector import detect_anomalies
from .curtailment import add_curtailment_flag_if_available, classify_deviation
from .constants import W_TO_MW
from .data_loader import (
    generate_synthetic_solar_fixture,
    generate_synthetic_wind_fixture,
    list_solar_assets,
    list_wind_assets,
    load_openstef_load,
    load_openstef_weather,
)
from .performance import calculate_performance
from .root_cause import analyzeRootCause as _root_cause_analysis
from . import root_cause as _root_cause_module
from .solar_model import load_solar_model, predict_solar
from .wind_model import forecast_wind_generation, load_wind_model


logger = logging.getLogger(__name__)


class RenewableDataError(ValueError):
    """Stable integration error with a machine-readable reason code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.reason = code


# Installed by the integration layer.  It is intentionally private: the three
# public functions below are the service API, while data registration belongs
# to the API/data integration layer.
_ASSET_REGISTRY: dict[str, dict[str, Any]] = {}
_MODEL_CACHE: dict[str, Any] = {}
_FALLBACK_RECORD_CACHE: dict[str, dict[str, Any]] = {}
_MIN_CONTEXT_ROWS = 4
# A fixed 48-hour block gives both public entry points the same representative
# fit population. Each block starts at midnight on an odd calendar day.
_ANOMALY_LOOKBACK_ROWS = 192
_ROOT_CAUSE_ARTIFACT_CHECKED = False
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MODEL_DIR = _PROJECT_ROOT / "ml" / "models" / "renewable"
_OPENSTEF_DATASET_DIR = _PROJECT_ROOT / "ml" / "datasets" / "liander2024"
_SYNTHETIC_ASSETS = {"solar_park_synth_01": "solar", "wind_park_synth_01": "wind"}


def _asset(asset_id: str) -> dict[str, Any]:
    record = _ASSET_REGISTRY.get(asset_id) or _fallback_asset(asset_id)
    if record is None:
        raise RenewableDataError("UNKNOWN_ASSET", f"No renewable data is registered or available locally for asset_id={asset_id!r}.")
    asset_type = record.get("asset_type")
    if asset_type == "hydro":
        raise RenewableDataError("UNSUPPORTED_ASSET_TYPE", "Hydro has no supported renewable model pipeline.")
    if asset_type not in {"solar", "wind"}:
        raise RenewableDataError("UNSUPPORTED_ASSET_TYPE", f"Unsupported renewable asset type: {asset_type!r}.")
    if not isinstance(record.get("data"), pd.DataFrame):
        raise RenewableDataError("MISSING_DATA", f"Asset {asset_id!r} has no registered telemetry DataFrame.")
    required = {"timestamp", "expected_mw", "actual_mw"}
    missing = required.difference(record["data"].columns)
    if missing:
        raise RenewableDataError("MISSING_DATA", f"Asset {asset_id!r} data is missing columns: {sorted(missing)}.")
    return record


def _cached_model(record: dict[str, Any]) -> Any | None:
    """Load a configured persisted model once per asset type.

    Forecast points in the registry are generated upstream by that model.  The
    cached object supports model lifecycle validation without reloading on
    every status request.
    """
    path = record.get("model_path")
    asset_type = record["asset_type"]
    if path is None:
        return None
    if asset_type not in _MODEL_CACHE:
        _MODEL_CACHE[asset_type] = load_solar_model(path) if asset_type == "solar" else load_wind_model(path)
    return _MODEL_CACHE[asset_type]


def _model_path(asset_type: str, asset_id: str) -> Path:
    safe_name = asset_id.replace("/", "_").replace(" ", "_")
    prefix = "solar_lgbm" if asset_type == "solar" else "wind_lgbm"
    return _MODEL_DIR / f"{prefix}_{safe_name}.pkl"


def _real_solar_coordinates(asset_id: str) -> tuple[float, float] | None:
    """Read an OpenSTEF target's coordinates when its local metadata exists."""
    path = _OPENSTEF_DATASET_DIR / "liander2024_targets.yaml"
    try:
        import yaml
        with path.open(encoding="utf-8") as stream:
            targets = yaml.safe_load(stream)
        target = next(item for item in targets if item.get("name") == asset_id)
        return float(target["latitude"]), float(target["longitude"])
    except (FileNotFoundError, KeyError, StopIteration, TypeError, ValueError, OSError):
        return None


def _fallback_asset(asset_id: str) -> dict[str, Any] | None:
    """Build an in-memory record from local OpenSTEF or synthetic inputs.

    An asset-matched persisted model is required.  The generated record is
    cached separately from registry overrides, so an override always wins.
    """
    if asset_id in _FALLBACK_RECORD_CACHE:
        return _FALLBACK_RECORD_CACHE[asset_id]
    asset_type: str | None = None
    load_df: pd.DataFrame
    weather_df: pd.DataFrame
    lat, lon = 52.3, 4.9  # calibrated synthetic fixture coordinates
    try:
        if _OPENSTEF_DATASET_DIR.exists():
            solar_assets = set(list_solar_assets(_OPENSTEF_DATASET_DIR))
            wind_assets = set(list_wind_assets(_OPENSTEF_DATASET_DIR))
            if asset_id in solar_assets | wind_assets:
                asset_type = "solar" if asset_id in solar_assets else "wind"
                load_df = load_openstef_load(_OPENSTEF_DATASET_DIR, asset_id)
                weather_df = load_openstef_weather(_OPENSTEF_DATASET_DIR, asset_id)
                if asset_type == "solar":
                    coordinates = _real_solar_coordinates(asset_id)
                    if coordinates is None:
                        return None
                    lat, lon = coordinates
            else:
                return None
        elif asset_id in _SYNTHETIC_ASSETS:
            asset_type = _SYNTHETIC_ASSETS[asset_id]
            if asset_type == "solar":
                load_df, weather_df = generate_synthetic_solar_fixture()
            else:
                load_df, weather_df = generate_synthetic_wind_fixture()
        else:
            return None
    except (FileNotFoundError, OSError, ValueError):
        return None

    path = _model_path(asset_type, asset_id)
    if not path.exists():
        return None
    record = {"asset_type": asset_type, "weather_df": weather_df, "model_path": path}
    try:
        model = _cached_model(record)
        if asset_type == "solar":
            expected = predict_solar(model, load_df, weather_df, lat, lon, asset_id)
        else:
            expected = forecast_wind_generation(model, load_df, weather_df, asset_id, wind_speed_source="auto")
    except (FileNotFoundError, OSError, ValueError):
        return None

    actual = load_df.copy()
    actual["timestamp"] = pd.to_datetime(actual["timestamp"], utc=True)
    actual = actual.set_index("timestamp")["load"].mul(W_TO_MW).rename("actual_mw")
    data = pd.concat([expected.rename("expected_mw"), actual], axis=1, join="inner").reset_index()
    if data.empty:
        return None
    record["data"] = data
    _FALLBACK_RECORD_CACHE[asset_id] = record
    return record


def _rows_until(asset_id: str, timestamp: Any) -> tuple[dict[str, Any], pd.DataFrame, pd.Timestamp]:
    record = _asset(asset_id)
    requested = pd.to_datetime(timestamp, utc=True)
    data = record["data"].copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)
    data = data.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    if not data["timestamp"].eq(requested).any():
        raise RenewableDataError("TIMESTAMP_OUT_OF_RANGE", f"No observation exists for asset_id={asset_id!r} at {requested.isoformat()}.")
    context = _analysis_window(data, requested)
    if len(context) < _MIN_CONTEXT_ROWS:
        raise RenewableDataError("INSUFFICIENT_HISTORY", f"At least {_MIN_CONTEXT_ROWS} observations are required before {requested.isoformat()}.")
    return record, context, requested


def _root_cause_artifact_status() -> None:
    """Check root-cause artifacts once and make missing persistence visible."""
    global _ROOT_CAUSE_ARTIFACT_CHECKED
    if _ROOT_CAUSE_ARTIFACT_CHECKED or _root_cause_module._BUNDLES:
        return
    _ROOT_CAUSE_ARTIFACT_CHECKED = True
    candidates = [
        _MODEL_DIR / "root_cause_xgb_solar.pkl",
        _MODEL_DIR / "root_cause_xgb_wind.pkl",
    ]
    present = [path for path in candidates if path.exists()]
    if present:
        logger.warning(
            "Root-cause model artifact(s) found at %s, but root_cause.py has no "
            "persisted-bundle loader; its in-memory training rows are unavailable. "
            "Root-cause analysis remains uncertain until a bundle is registered.",
            ", ".join(str(path) for path in present),
        )
    else:
        logger.warning(
            "Root-cause model artifacts are unavailable (%s). "
            "analyzeRootCause will return category='uncertain', confidence=0.0 "
            "until a root-cause bundle is trained and registered.",
            ", ".join(str(path) for path in candidates),
        )


def _trailing_context(data: pd.DataFrame, timestamp: pd.Timestamp) -> pd.DataFrame:
    context = _analysis_window(data, timestamp)
    if len(context) < _MIN_CONTEXT_ROWS:
        return pd.DataFrame()
    return context


def _analysis_window(data: pd.DataFrame, timestamp: pd.Timestamp) -> pd.DataFrame:
    day_start = timestamp.normalize()
    if day_start.day % 2 == 0:
        day_start -= pd.Timedelta(days=1)
    window_end = day_start + pd.Timedelta(days=2) - pd.Timedelta(minutes=15)
    return data.loc[data["timestamp"].between(day_start, window_end)].tail(_ANOMALY_LOOKBACK_ROWS).copy()


def _pipeline(asset_id: str, record: dict[str, Any], rows: pd.DataFrame) -> pd.DataFrame:
    _cached_model(record)
    performance = calculate_performance(
        asset_id, record["asset_type"], rows["timestamp"], rows["expected_mw"], rows["actual_mw"]
    )
    weather = record.get("weather_df")
    diagnostic = classify_deviation(performance, weather)
    curtailment_column = record.get("curtailment_column")
    if curtailment_column is None:
        curtailment_column = next(
            (column for column in ("curtailment_flag", "curtailed", "curtailment") if column in rows.columns),
            None,
        )
    if curtailment_column is not None:
        diagnostic[curtailment_column] = rows[curtailment_column].to_numpy()
        diagnostic = add_curtailment_flag_if_available(diagnostic, curtailment_column)
    return detect_anomalies(performance, diagnostic, weather)


def _status_from_row(row: pd.Series, root_result: dict[str, Any] | None = None) -> dict[str, Any]:
    raw_ratio = float(row["performance_ratio"])
    if not np.isfinite(raw_ratio):
        if not bool(row.get("zero_expected_edge_case", False)):
            raise RenewableDataError("DATA_QUALITY", "Performance ratio is not finite; a contract-shaped numeric status is unavailable.")
        ratio = None
    else:
        ratio = raw_ratio
    if bool(row.get("zero_expected_edge_case", False)):
        root_result = None
    if ratio is None and not bool(row.get("anomaly", False)):
        raise RenewableDataError("DATA_QUALITY", "Performance ratio is not finite; a contract-shaped numeric status is unavailable.")
    result = {
        "assetId": str(row["asset_id"]), "assetType": str(row["asset_type"]),
        "timestamp": row["timestamp"].isoformat(), "expectedMw": float(row["expected_mw"]),
        "actualMw": float(row["actual_mw"]), "performanceRatio": ratio,
        "anomaly": bool(row["anomaly"]),
    }
    if root_result and root_result.get("category") != "uncertain" and root_result.get("confidence", 0.0) > 0.0:
        result["likelyRootCause"] = {
            "category": str(root_result["category"]), "confidence": float(root_result["confidence"]),
        }
    return result


def getRenewableStatus(asset_id: str, timestamp: Any) -> dict:
    """Return one RenewableStatus mapping; omit optional likelyRootCause when uncertain."""
    record, context, requested = _rows_until(asset_id, timestamp)
    detected = _pipeline(asset_id, record, context)
    row = detected.loc[detected["timestamp"].eq(requested)].iloc[-1]
    _root_cause_artifact_status()
    root_result = (
        _root_cause_analysis(asset_id, requested)
        if bool(row["anomaly"]) and not bool(row.get("zero_expected_edge_case", False))
        else None
    )
    return _status_from_row(row, root_result)


def detectAnomalies(time_range: dict) -> list[dict]:
    """Return only anomalous RenewableStatus mappings in the requested range."""
    if not isinstance(time_range, dict) or "start" not in time_range or "end" not in time_range:
        raise RenewableDataError("INVALID_TIME_RANGE", "time_range must contain start and end timestamps.")
    start, end = pd.to_datetime(time_range["start"], utc=True), pd.to_datetime(time_range["end"], utc=True)
    if start > end:
        raise RenewableDataError("INVALID_TIME_RANGE", "time_range start must not be after end.")
    asset_ids = [time_range["asset_id"]] if time_range.get("asset_id") else list(dict.fromkeys([*_ASSET_REGISTRY, *_SYNTHETIC_ASSETS]))
    statuses: list[dict] = []
    for asset_id in asset_ids:
        record = _asset(asset_id)
        data = record["data"].copy()
        data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)
        rows = data.loc[data["timestamp"].between(start, end)].sort_values("timestamp")
        if rows.empty:
            continue
        if len(rows) < _MIN_CONTEXT_ROWS:
            raise RenewableDataError("INSUFFICIENT_HISTORY", f"At least {_MIN_CONTEXT_ROWS} observations are required in the requested time range.")
        _root_cause_artifact_status()
        windows: dict[pd.Timestamp, pd.DataFrame] = {}
        for timestamp in rows["timestamp"]:
            window_start = timestamp.normalize()
            if window_start.day % 2 == 0:
                window_start -= pd.Timedelta(days=1)
            windows.setdefault(window_start, _analysis_window(data, timestamp))
        for window in windows.values():
            if len(window) < _MIN_CONTEXT_ROWS:
                continue
            detected = _pipeline(asset_id, record, window)
            targets = detected.loc[detected["timestamp"].between(start, end)]
            for _, row in targets.loc[targets["anomaly"]].iterrows():
                root_result = (
                    _root_cause_analysis(asset_id, row["timestamp"])
                    if not bool(row.get("zero_expected_edge_case", False))
                    else None
                )
                statuses.append(_status_from_row(row, root_result))
    return statuses


def analyzeRootCause(asset_id: str, timestamp: Any) -> dict:
    """Return only the public category/confidence subset of internal analysis."""
    _rows_until(asset_id, timestamp)
    _root_cause_artifact_status()
    result = _root_cause_analysis(asset_id, pd.to_datetime(timestamp, utc=True))
    return {"category": str(result["category"]), "confidence": float(result["confidence"])}
