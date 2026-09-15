"""Uncertainty-first XGBoost/SHAP association analysis for Kaggle aggregates.

The Kaggle data contains no physical fault labels or weather. Models therefore
predict percentage deviation as an association target; SHAP evidence describes
model contribution and never proves a physical root cause.
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
try:
    import shap
except ImportError:
    shap = None
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

from .constants import RANDOM_SEED
from .kaggle_anomaly import calculate_kaggle_performance
from .kaggle_data_loader import DEFAULT_RESOLUTION, discover_kaggle_schema, kaggle_csv_path
from .kaggle_forecasting import CAPACITY_FEATURE_COLUMNS, _feature_frame, load_kaggle_forecaster


KAGGLE_ROOT_CAUSE_VERSION = "1.0.0"
NEGLIGIBLE_DEVIATION_PERCENT = 5.0
MIN_ROOT_CAUSE_EXPECTED_MW = 1e-3
ROOT_FEATURE_COLUMNS = (
    "expected_mw", "capacity_mw", "expected_capacity_ratio",
    "hour_sin", "hour_cos", "day_of_week_sin", "day_of_week_cos",
    "day_of_year_sin", "day_of_year_cos", "month_sin", "month_cos",
    "lag_1", "lag_2", "lag_3", "lag_6", "lag_24", "lag_48", "lag_168",
    "roll_mean_3", "roll_mean_24", "roll_mean_168",
)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass
class KaggleRootCauseResult:
    asset_id: str
    energy_type: str
    model_path: str
    metadata_path: str
    train_rows: int
    validation_rows: int
    test_rows: int
    metrics: dict[str, float | int | None]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_name(value: str) -> str:
    return _SAFE_NAME.sub("_", value)


def _forecast_rows(
    source: pd.DataFrame,
    asset_id: str,
    energy_type: str,
    capacity_column: str | None,
    forecast_model_path: str | Path,
) -> pd.DataFrame:
    """Build target/features using only current forecast and past generation."""
    metadata_path = Path(f"{forecast_model_path}_metadata.json")
    if not metadata_path.exists():
        metadata_path = Path(f"{Path(forecast_model_path).with_suffix('')}_metadata.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    forecast_features = tuple(metadata["features"])
    frame = _feature_frame(source, asset_id, capacity_column)
    required = [column for column in forecast_features if column not in CAPACITY_FEATURE_COLUMNS]
    eligible = frame[required].notna().all(axis=1)
    expected = pd.Series(np.nan, index=frame.index, dtype=float)
    model = load_kaggle_forecaster(forecast_model_path)
    expected.loc[eligible] = model.predict(frame.loc[eligible, list(forecast_features)])
    expected = expected.clip(lower=0.0)
    performance = calculate_kaggle_performance(frame["target_mw"], expected, frame["capacity_mw"])
    rows = frame.copy()
    rows["asset_id"] = asset_id
    rows["energy_type"] = energy_type
    rows["actual_mw"] = rows["target_mw"]
    rows["expected_mw"] = performance["expected_mw"]
    rows["expected_capacity_ratio"] = performance["expected_capacity_ratio"]
    rows["percentage_deviation"] = performance["percentage_deviation"]
    rows.loc[rows["expected_mw"].abs().le(MIN_ROOT_CAUSE_EXPECTED_MW), "percentage_deviation"] = np.nan
    return rows


def _root_frame(rows: pd.DataFrame) -> pd.DataFrame:
    """Select features that cannot directly reveal the current target."""
    return rows.loc[:, list(ROOT_FEATURE_COLUMNS)].replace([np.inf, -np.inf], np.nan)


def _split(rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = rows.sort_values("timestamp").reset_index(drop=True)
    train_end = int(len(rows) * 0.70)
    validation_end = int(len(rows) * 0.85)
    return rows.iloc[:train_end], rows.iloc[train_end:validation_end], rows.iloc[validation_end:]


def _impute(train: pd.DataFrame, other: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    medians = train.median(numeric_only=True).fillna(0.0).astype(float).to_dict()
    return train.fillna(medians).fillna(0.0), other.fillna(medians).fillna(0.0), medians


def train_kaggle_root_cause_model(
    rows: pd.DataFrame,
    energy_type: str,
    output_dir: str | Path,
    min_rows: int = 500,
) -> KaggleRootCauseResult | None:
    """Train one solar or wind deviation-association model."""
    valid = rows.loc[np.isfinite(pd.to_numeric(rows["percentage_deviation"], errors="coerce"))].copy()
    valid["timestamp"] = pd.to_datetime(valid["timestamp"], utc=True)
    valid = valid.sort_values("timestamp").reset_index(drop=True)
    if len(valid) < min_rows:
        return None
    train, validation, test = _split(valid)
    train_x, validation_x, medians = _impute(_root_frame(train), _root_frame(validation))
    _, test_x, _ = _impute(_root_frame(train), _root_frame(test))
    target_train = train["percentage_deviation"].astype(float)
    target_validation = validation["percentage_deviation"].astype(float)
    target_test = test["percentage_deviation"].astype(float)
    model = XGBRegressor(
        objective="reg:squarederror", n_estimators=140, max_depth=3,
        learning_rate=0.05, subsample=0.9, colsample_bytree=0.9,
        random_state=RANDOM_SEED, n_jobs=1, tree_method="hist",
    )
    model.fit(train_x, target_train, eval_set=[(validation_x, target_validation)], verbose=False)
    validation_prediction = model.predict(validation_x)
    test_prediction = model.predict(test_x)
    metrics = {
        "validation_mae_percentage_points": float(mean_absolute_error(target_validation, validation_prediction)),
        "validation_rmse_percentage_points": float(np.sqrt(mean_squared_error(target_validation, validation_prediction))),
        "test_mae_percentage_points": float(mean_absolute_error(target_test, test_prediction)),
        "test_rmse_percentage_points": float(np.sqrt(mean_squared_error(target_test, test_prediction))),
        "train_rows": len(train), "validation_rows": len(validation), "test_rows": len(test),
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stem = f"kaggle_root_cause_xgb_{energy_type}"
    model_path = output / f"{stem}.pkl"
    metadata_path = output / f"{stem}_metadata.json"
    bundle = {"model": model, "feature_columns": list(ROOT_FEATURE_COLUMNS), "medians": medians}
    joblib.dump(bundle, model_path)
    metadata = {
        "model_type": "XGBoostRegressor", "model_version": KAGGLE_ROOT_CAUSE_VERSION,
        "task": "aggregate_percentage_deviation_association", "energy_type": energy_type,
        "dataset_source": "kaggle_power_system", "dataset_file": "time_series_60min_singleindex.csv",
        "features": list(ROOT_FEATURE_COLUMNS), "target": "percentage_deviation",
        "trained_at": datetime.now(timezone.utc).isoformat(), "metrics": metrics,
        "train_period": {"start": train.timestamp.iloc[0].isoformat(), "end": train.timestamp.iloc[-1].isoformat()},
        "validation_period": {"start": validation.timestamp.iloc[0].isoformat(), "end": validation.timestamp.iloc[-1].isoformat()},
        "test_period": {"start": test.timestamp.iloc[0].isoformat(), "end": test.timestamp.iloc[-1].isoformat()},
        "weather_features_used": [], "curtailment_status": "unknown", "physical_labels_available": False,
        "limitation": "SHAP contributions describe model association and do not establish physical causation.",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return KaggleRootCauseResult(f"pooled_{energy_type}", energy_type, str(model_path), str(metadata_path), len(train), len(validation), len(test), metrics)


def train_kaggle_root_cause_models(
    dataset_dir: str | Path,
    forecast_artifact_dir: str | Path,
    output_dir: str | Path,
    resolution: str = DEFAULT_RESOLUTION,
    min_rows: int = 500,
) -> dict[str, Any]:
    """Build pooled solar/wind training frames and persist both models."""
    source_path = kaggle_csv_path(dataset_dir, resolution)
    source = pd.read_csv(source_path)
    schema = discover_kaggle_schema(source_path)
    forecast_dir = Path(forecast_artifact_dir)
    frames = {"solar": [], "wind": []}
    skipped: list[dict[str, str]] = []
    for asset_id in schema.generation_columns:
        stem = _safe_name(asset_id)
        forecast_path = forecast_dir / f"kaggle_lgbm_{stem}.pkl"
        if not forecast_path.exists():
            skipped.append({"asset_id": asset_id, "reason": "forecast artifact unavailable"})
            continue
        energy_type = "solar" if "_solar_" in asset_id else "wind"
        frames[energy_type].append(_forecast_rows(source, asset_id, energy_type, schema.capacity_by_generation[asset_id], forecast_path))
    results: list[dict[str, Any]] = []
    for energy_type, parts in frames.items():
        if not parts:
            skipped.append({"asset_id": energy_type, "reason": "no eligible forecast series"})
            continue
        result = train_kaggle_root_cause_model(pd.concat(parts, ignore_index=True), energy_type, output_dir, min_rows)
        if result is None:
            skipped.append({"asset_id": energy_type, "reason": "insufficient finite deviation rows"})
        else:
            results.append(result.to_dict())
    manifest = {
        "model_version": KAGGLE_ROOT_CAUSE_VERSION, "dataset_source": "kaggle_power_system",
        "dataset_file": source_path.name, "weather_available": False,
        "curtailment_status": "unknown", "physical_labels_available": False,
        "results": results, "skipped": skipped,
        "limitation": "No authoritative physical root-cause labels exist; outputs are deviation associations only.",
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "kaggle_root_cause_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_kaggle_root_cause_model(energy_type: str, artifact_dir: str | Path) -> dict[str, Any]:
    """Load a persisted Kaggle root-cause association bundle."""
    if energy_type not in {"solar", "wind"}:
        raise ValueError("energy_type must be 'solar' or 'wind'")
    return joblib.load(Path(artifact_dir) / f"kaggle_root_cause_xgb_{energy_type}.pkl")


def _insufficient(asset_id: str, timestamp: Any, energy_type: str | None, reason: str, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "asset_id": asset_id, "timestamp": pd.to_datetime(timestamp, utc=True).isoformat(),
        "energy_type": energy_type, "root_cause": "insufficient evidence", "confidence": None,
        "evidence": evidence or [], "curtailment_status": "unknown", "reason": reason,
    }


def explain_kaggle_row(
    row: pd.Series,
    model_bundle: dict[str, Any],
    anomaly_flag: bool | None = True,
) -> dict[str, Any]:
    """Generate a SHAP association explanation for one prepared row."""
    asset_id = str(row.get("asset_id", "unknown"))
    timestamp = row.get("timestamp")
    energy_type = row.get("energy_type")
    required = set(ROOT_FEATURE_COLUMNS) | {"actual_mw", "expected_mw", "percentage_deviation"}
    if timestamp is None or not required.issubset(row.index):
        return _insufficient(asset_id, timestamp or pd.Timestamp.now(tz="UTC"), energy_type, "required evidence is missing")
    if anomaly_flag is not True:
        return _insufficient(asset_id, timestamp, energy_type, "row is not an explicitly evaluated anomaly")
    values = _root_frame(pd.DataFrame([row])).fillna(model_bundle["medians"]).fillna(0.0)
    values = values[model_bundle["feature_columns"]]
    if shap is not None:
        shap_values = np.asarray(shap.TreeExplainer(model_bundle["model"])(values).values).reshape(-1)
    else:
        shap_values = np.asarray(model_bundle["model"].feature_importances_).reshape(-1)
    evidence = [
        {"feature": name, "value": float(values.iloc[0][name]), "shap_contribution": float(value)}
        for name, value in sorted(zip(model_bundle["feature_columns"], shap_values), key=lambda item: abs(item[1]), reverse=True)[:5]
    ]
    deviation = float(row["percentage_deviation"]) if pd.notna(row["percentage_deviation"]) else None
    if deviation is None or not np.isfinite(deviation):
        return _insufficient(asset_id, timestamp, energy_type, "percentage deviation is unavailable", evidence)
    if abs(deviation) < NEGLIGIBLE_DEVIATION_PERCENT:
        category = "expected/normal temporal variation"
    elif deviation < 0:
        category = "unusually low generation relative to expected"
    else:
        category = "unusually high generation relative to expected"
    return {
        "asset_id": asset_id, "timestamp": pd.to_datetime(timestamp, utc=True).isoformat(),
        "energy_type": energy_type, "root_cause": category, "confidence": None,
        "evidence": evidence, "curtailment_status": "unknown",
        "association_disclaimer": "SHAP contributions explain model association; they do not prove physical causation.",
    }