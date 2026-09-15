"""Actual-vs-expected performance and anomaly detection for Kaggle aggregates.

The Kaggle source has no weather, maintenance, or curtailment observations.
This module therefore reports unexplained statistical anomalies only. It does
not assign physical causes and does not modify the existing OpenSTEF pipeline.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from .constants import RANDOM_SEED
from .kaggle_data_loader import DEFAULT_RESOLUTION, discover_kaggle_schema, kaggle_csv_path
from .kaggle_forecasting import (
    CAPACITY_FEATURE_COLUMNS,
    _feature_frame,
    feature_columns_for,
    load_kaggle_forecaster,
)


KAGGLE_ANOMALY_MODEL_VERSION = "1.0.0"
DEFAULT_CONTAMINATION = 0.05
NEAR_ZERO_EXPECTED_MW = 1e-6
ANOMALY_FEATURE_COLUMNS = (
    "actual_mw", "expected_mw", "absolute_deviation_mw", "absolute_error_mw",
    "percentage_deviation", "performance_ratio", "generation_capacity_ratio",
    "expected_capacity_ratio", "rolling_performance_ratio", "hour_sin", "hour_cos",
    "day_of_week_sin", "day_of_week_cos", "month_sin", "month_cos",
)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass
class KaggleAnomalyResult:
    asset_id: str
    energy_type: str
    model_path: str
    metadata_path: str
    observations_evaluated: int
    anomalies_detected: int
    training_period: dict[str, str]
    evaluation_period: dict[str, str]
    feature_columns: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_asset_name(asset_id: str) -> str:
    return _SAFE_NAME.sub("_", asset_id)


def calculate_kaggle_performance(
    actual_mw: pd.Series,
    expected_mw: pd.Series,
    capacity_mw: pd.Series,
) -> pd.DataFrame:
    """Calculate nullable actual-vs-expected and capacity-aware metrics."""
    actual = pd.to_numeric(actual_mw, errors="coerce")
    expected = pd.to_numeric(expected_mw, errors="coerce")
    capacity = pd.to_numeric(capacity_mw, errors="coerce")
    valid_expected = expected.notna() & expected.abs().gt(NEAR_ZERO_EXPECTED_MW)
    valid_capacity = capacity.notna() & capacity.gt(0)
    absolute_deviation = actual - expected
    result = pd.DataFrame(index=actual.index)
    result["actual_mw"] = actual
    result["expected_mw"] = expected
    result["absolute_deviation_mw"] = absolute_deviation
    result["absolute_error_mw"] = absolute_deviation.abs()
    result["percentage_deviation"] = (absolute_deviation / expected * 100).where(valid_expected)
    result["performance_ratio"] = (actual / expected).where(valid_expected)
    result["generation_capacity_ratio"] = (actual / capacity).where(valid_capacity & actual.notna())
    result["expected_capacity_ratio"] = (expected / capacity).where(valid_capacity & expected.notna())
    result["zero_or_missing_expected"] = ~valid_expected
    return result


def _anomaly_features(performance: pd.DataFrame) -> pd.DataFrame:
    """Build only dataset-supported numeric anomaly features."""
    frame = performance.copy()
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    ratio = pd.to_numeric(frame["performance_ratio"], errors="coerce")
    frame["rolling_performance_ratio"] = ratio.shift(1).rolling(24, min_periods=1).mean()
    frame["hour_sin"] = np.sin(2 * np.pi * timestamp.dt.hour / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * timestamp.dt.hour / 24)
    frame["day_of_week_sin"] = np.sin(2 * np.pi * timestamp.dt.dayofweek / 7)
    frame["day_of_week_cos"] = np.cos(2 * np.pi * timestamp.dt.dayofweek / 7)
    frame["month_sin"] = np.sin(2 * np.pi * (timestamp.dt.month - 1) / 12)
    frame["month_cos"] = np.cos(2 * np.pi * (timestamp.dt.month - 1) / 12)
    return frame[list(ANOMALY_FEATURE_COLUMNS)].replace([np.inf, -np.inf], np.nan)


def _impute(features: pd.DataFrame, fit_mask: pd.Series) -> tuple[pd.DataFrame, dict[str, float]]:
    clean = features.replace([np.inf, -np.inf], np.nan)
    medians = clean.loc[fit_mask].median().fillna(0.0).astype(float).to_dict()
    return clean.fillna(medians).fillna(0.0), medians


def _apply_model(
    result: pd.DataFrame,
    model_bundle: dict[str, Any],
    eligible: pd.Series,
) -> pd.DataFrame:
    """Apply a persisted detector and leave unavailable rows explicitly null."""
    features = _anomaly_features(result)
    imputed = features.fillna(model_bundle["medians"]).fillna(0.0)
    scores = pd.Series(np.nan, index=result.index, dtype=float)
    flags = pd.Series(pd.NA, index=result.index, dtype="boolean")
    if eligible.any():
        values = imputed.loc[eligible, model_bundle["feature_columns"]]
        scores.loc[eligible] = model_bundle["model"].decision_function(values)
        flags.loc[eligible] = model_bundle["model"].predict(values) == -1
    result["anomaly_score"] = scores
    result["anomaly_flag"] = flags
    result["confidence"] = None
    return result


def train_kaggle_anomaly_detector(
    source: pd.DataFrame,
    forecast_model_path: str | Path,
    asset_id: str,
    energy_type: str,
    capacity_column: str | None,
    output_dir: str | Path,
    contamination: float = DEFAULT_CONTAMINATION,
    evaluation_fraction: float = 0.20,
    curtailment_column: str | None = None,
) -> tuple[KaggleAnomalyResult | None, pd.DataFrame]:
    """Train one chronological per-series Isolation Forest and evaluate it."""
    if not 0 < contamination <= 0.5:
        raise ValueError("contamination must be greater than 0 and no greater than 0.5")
    if not 0 < evaluation_fraction < 1:
        raise ValueError("evaluation_fraction must be between 0 and 1")
    metadata_path = Path(f"{forecast_model_path}_metadata.json")
    if not metadata_path.exists():
        metadata_path = Path(f"{Path(forecast_model_path).with_suffix('')}_metadata.json")
    forecast_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    forecast_features = tuple(forecast_metadata["features"])
    forecast_model = load_kaggle_forecaster(forecast_model_path)
    frame = _feature_frame(source, asset_id, capacity_column)
    required_forecast_features = [column for column in forecast_features if column not in CAPACITY_FEATURE_COLUMNS]
    forecast_eligible = frame[required_forecast_features].notna().all(axis=1)
    expected = pd.Series(np.nan, index=frame.index, dtype=float)
    expected.loc[forecast_eligible] = forecast_model.predict(frame.loc[forecast_eligible, list(forecast_features)])
    expected = expected.clip(lower=0.0)
    performance = calculate_kaggle_performance(
        frame["target_mw"], expected, frame["capacity_mw"],
    )
    performance.insert(0, "timestamp", frame["timestamp"].to_numpy())
    performance.insert(0, "asset_id", asset_id)
    performance.insert(1, "energy_type", energy_type)
    performance["curtailment_status"] = "unknown"
    if curtailment_column and curtailment_column in source.columns:
        performance["curtailment_status"] = source[curtailment_column].map(
            lambda value: "intentional" if bool(value) else "not_indicated"
        ).to_numpy()
    valid = performance["actual_mw"].notna() & performance["expected_mw"].notna()
    valid_rows = performance.loc[valid].reset_index(drop=True)
    if len(valid_rows) < 30:
        return None, performance
    split = max(2, int(len(valid_rows) * (1 - evaluation_fraction)))
    if split >= len(valid_rows):
        split = len(valid_rows) - 1
    train_rows = valid_rows.iloc[:split]
    evaluation_rows = valid_rows.iloc[split:]
    feature_columns = list(ANOMALY_FEATURE_COLUMNS)
    train_features = _anomaly_features(train_rows)
    eval_features = _anomaly_features(evaluation_rows)
    train_mask = train_rows["actual_mw"].notna() & train_rows["expected_mw"].notna()
    if int(train_mask.sum()) < 10:
        return None, performance
    train_imputed, medians = _impute(train_features, train_mask)
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=RANDOM_SEED,
        n_jobs=1,
    )
    model.fit(train_imputed.loc[train_mask, feature_columns])
    bundle = {"model": model, "feature_columns": feature_columns, "medians": medians}
    evaluated = _apply_model(evaluation_rows.copy(), bundle, evaluation_rows["actual_mw"].notna() & evaluation_rows["expected_mw"].notna())
    if curtailment_column and curtailment_column in source.columns:
        explicit = evaluated["curtailment_status"].eq("intentional")
        evaluated.loc[explicit, "anomaly_flag"] = False
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stem = f"kaggle_isolation_forest_{_safe_asset_name(asset_id)}"
    model_path = output / f"{stem}.pkl"
    detector_metadata_path = output / f"{stem}_metadata.json"
    joblib.dump(bundle, model_path)
    metadata = {
        "model_type": "IsolationForest", "model_version": KAGGLE_ANOMALY_MODEL_VERSION,
        "dataset_source": "kaggle_power_system", "dataset_file": "time_series_60min_singleindex.csv",
        "asset_id": asset_id, "energy_type": energy_type, "feature_columns": feature_columns,
        "random_state": RANDOM_SEED, "n_estimators": 200, "contamination": contamination,
        "training_period": {"start": train_rows.timestamp.iloc[0].isoformat(), "end": train_rows.timestamp.iloc[-1].isoformat()},
        "evaluation_period": {"start": evaluation_rows.timestamp.iloc[0].isoformat(), "end": evaluation_rows.timestamp.iloc[-1].isoformat()},
        "training_rows": len(train_rows), "evaluation_rows": len(evaluation_rows),
        "anomalies_detected": int(evaluated["anomaly_flag"].fillna(False).sum()),
        "weather_features_used": [], "curtailment_status_default": "unknown",
        "score_semantics": "IsolationForest decision_function; lower values are more anomalous and zero is the fitted decision boundary; this is not a probability.",
        "ground_truth_available": False,
    }
    detector_metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    result = KaggleAnomalyResult(
        asset_id, energy_type, str(model_path), str(detector_metadata_path),
        len(evaluated), int(evaluated["anomaly_flag"].fillna(False).sum()),
        metadata["training_period"], metadata["evaluation_period"], feature_columns,
    )
    return result, evaluated


def load_kaggle_anomaly_detector(model_path: str | Path) -> dict[str, Any]:
    """Load a persisted Kaggle Isolation Forest bundle."""
    return joblib.load(model_path)


def detect_kaggle_anomalies(
    performance: pd.DataFrame,
    model_bundle: dict[str, Any],
) -> pd.DataFrame:
    """Score prepared performance rows with a persisted detector."""
    eligible = performance["actual_mw"].notna() & performance["expected_mw"].notna()
    return _apply_model(performance.copy(), model_bundle, eligible)


def train_kaggle_anomaly_detectors(
    dataset_dir: str | Path,
    forecast_artifact_dir: str | Path,
    output_dir: str | Path,
    resolution: str = DEFAULT_RESOLUTION,
    contamination: float = DEFAULT_CONTAMINATION,
) -> dict[str, Any]:
    """Train detectors for every trained forecast series."""
    source_path = kaggle_csv_path(dataset_dir, resolution)
    source = pd.read_csv(source_path)
    schema = discover_kaggle_schema(source_path)
    forecast_dir = Path(forecast_artifact_dir)
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    total_evaluated = 0
    total_anomalies = 0
    for asset_id in schema.generation_columns:
        stem = _safe_asset_name(asset_id)
        forecast_model_path = forecast_dir / f"kaggle_lgbm_{stem}.pkl"
        if not forecast_model_path.exists():
            skipped.append({"asset_id": asset_id, "reason": "forecast artifact unavailable"})
            continue
        energy_type = "solar" if "_solar_" in asset_id else "wind"
        result, evaluated = train_kaggle_anomaly_detector(
            source, forecast_model_path, asset_id, energy_type,
            schema.capacity_by_generation[asset_id], output_dir, contamination,
        )
        if result is None:
            skipped.append({"asset_id": asset_id, "reason": "insufficient valid performance rows"})
            continue
        evaluated_count = int(evaluated["anomaly_flag"].notna().sum())
        anomaly_count = int(evaluated["anomaly_flag"].fillna(False).sum())
        total_evaluated += evaluated_count
        total_anomalies += anomaly_count
        record = result.to_dict()
        record["observations_evaluated"] = evaluated_count
        record["anomalies_detected"] = anomaly_count
        results.append(record)
    manifest = {
        "model_version": KAGGLE_ANOMALY_MODEL_VERSION, "dataset_source": "kaggle_power_system",
        "dataset_file": source_path.name, "resolution": resolution,
        "contamination": contamination, "random_state": RANDOM_SEED,
        "solar_series_evaluated": sum(item["energy_type"] == "solar" for item in results),
        "wind_series_evaluated": sum(item["energy_type"] == "wind" for item in results),
        "observations_evaluated": total_evaluated, "anomalies_detected": total_anomalies,
        "weather_available": False, "curtailment_status_default": "unknown",
        "ground_truth_available": False, "results": results, "skipped": skipped,
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "kaggle_anomaly_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest