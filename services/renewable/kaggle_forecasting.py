"""Forecast aggregate Kaggle renewable generation in MW.

This module is intentionally separate from the OpenSTEF solar/wind models:
the Kaggle source is hourly aggregate data and has no weather observations.
Features use only timestamps, historical generation, and capacity when the
source supplies it. No anomaly or root-cause logic belongs here.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .kaggle_data_loader import DEFAULT_RESOLUTION, discover_kaggle_schema, kaggle_csv_path


KAGGLE_MODEL_VERSION = "1.0.0"
FEATURE_COLUMNS = (
    "hour_sin", "hour_cos", "day_of_week_sin", "day_of_week_cos",
    "day_of_year_sin", "day_of_year_cos", "month_sin", "month_cos",
    "lag_1", "lag_2", "lag_3", "lag_6", "lag_24", "lag_48", "lag_168",
    "roll_mean_3", "roll_mean_24", "roll_mean_168",
    "capacity_mw", "capacity_available", "lagged_generation_ratio",
)
CAPACITY_FEATURE_COLUMNS = ("capacity_mw", "capacity_available", "lagged_generation_ratio")
LAGS = (1, 2, 3, 6, 24, 48, 168)
ROLLING_WINDOWS = (3, 24, 168)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class KaggleSplit:
    """Chronological split boundaries and row counts."""

    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    test_start: str
    test_end: str
    train_rows: int
    validation_rows: int
    test_rows: int


@dataclass
class KaggleForecastResult:
    """Training result persisted in the aggregate model manifest."""

    asset_id: str
    energy_type: str
    model_path: str
    metadata_path: str
    feature_columns: list[str]
    split: KaggleSplit
    metrics: dict[str, float | int | None]
    valid_observations: int

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["split"] = asdict(self.split)
        return result


def _safe_asset_name(asset_id: str) -> str:
    return _SAFE_NAME.sub("_", asset_id)


def feature_columns_for(capacity_column: str | None) -> tuple[str, ...]:
    """Return capacity features only when the source has a matching field."""
    if capacity_column is None:
        return tuple(column for column in FEATURE_COLUMNS if column not in CAPACITY_FEATURE_COLUMNS)
    return FEATURE_COLUMNS


def _feature_frame(source: pd.DataFrame, generation_column: str, capacity_column: str | None) -> pd.DataFrame:
    """Build features from past observations and known calendar/capacity data."""
    frame = source[["utc_timestamp", generation_column] + ([capacity_column] if capacity_column else [])].copy()
    frame["timestamp"] = pd.to_datetime(frame.pop("utc_timestamp"), utc=True)
    frame = frame.rename(columns={generation_column: "target_mw"}).sort_values("timestamp")
    frame["target_mw"] = pd.to_numeric(frame["target_mw"], errors="coerce")
    frame["capacity_mw"] = (
        pd.to_numeric(frame.pop(capacity_column), errors="coerce")
        if capacity_column
        else np.nan
    )
    frame["capacity_available"] = frame["capacity_mw"].gt(0).astype(float)
    timestamp = frame["timestamp"]
    frame["hour_sin"] = np.sin(2 * np.pi * timestamp.dt.hour / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * timestamp.dt.hour / 24)
    frame["day_of_week_sin"] = np.sin(2 * np.pi * timestamp.dt.dayofweek / 7)
    frame["day_of_week_cos"] = np.cos(2 * np.pi * timestamp.dt.dayofweek / 7)
    frame["day_of_year_sin"] = np.sin(2 * np.pi * timestamp.dt.dayofyear / 366)
    frame["day_of_year_cos"] = np.cos(2 * np.pi * timestamp.dt.dayofyear / 366)
    frame["month_sin"] = np.sin(2 * np.pi * (timestamp.dt.month - 1) / 12)
    frame["month_cos"] = np.cos(2 * np.pi * (timestamp.dt.month - 1) / 12)
    for lag in LAGS:
        frame[f"lag_{lag}"] = frame["target_mw"].shift(lag)
    for window in ROLLING_WINDOWS:
        frame[f"roll_mean_{window}"] = frame["target_mw"].shift(1).rolling(window, min_periods=window).mean()
    safe_capacity = frame["capacity_mw"].where(frame["capacity_mw"].gt(0))
    frame["lagged_generation_ratio"] = frame["lag_1"] / safe_capacity
    return frame


def chronological_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, KaggleSplit]:
    """Split rows 70/15/15 in timestamp order without shuffling."""
    usable = frame.loc[frame["target_mw"].notna()].reset_index(drop=True)
    if len(usable) < 30:
        raise ValueError(f"At least 30 valid observations are required, got {len(usable)}")
    train_end = int(len(usable) * 0.70)
    validation_end = int(len(usable) * 0.85)
    train, validation, test = usable.iloc[:train_end], usable.iloc[train_end:validation_end], usable.iloc[validation_end:]
    split = KaggleSplit(
        train_start=train.timestamp.iloc[0].isoformat(), train_end=train.timestamp.iloc[-1].isoformat(),
        validation_start=validation.timestamp.iloc[0].isoformat(), validation_end=validation.timestamp.iloc[-1].isoformat(),
        test_start=test.timestamp.iloc[0].isoformat(), test_end=test.timestamp.iloc[-1].isoformat(),
        train_rows=len(train), validation_rows=len(validation), test_rows=len(test),
    )
    return train, validation, test, split


def _safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    """Calculate MAPE only where actual generation is meaningfully positive."""
    mask = np.isfinite(y_true) & np.isfinite(y_pred) & (np.abs(y_true) > 1e-6)
    if not mask.any():
        return None
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def _metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float | int | None]:
    actual = y_true.to_numpy(dtype=float)
    predicted = np.maximum(np.asarray(y_pred, dtype=float), 0.0)
    return {
        "mae_mw": float(mean_absolute_error(actual, predicted)),
        "rmse_mw": float(np.sqrt(mean_squared_error(actual, predicted))),
        "mape_pct": _safe_mape(actual, predicted),
        "n_samples": int(len(actual)),
        "n_positive_actual_for_mape": int((np.abs(actual) > 1e-6).sum()),
    }


def train_kaggle_series(
    source: pd.DataFrame,
    asset_id: str,
    energy_type: str,
    capacity_column: str | None,
    output_dir: str | Path,
    min_valid_observations: int = 500,
    lgb_params: dict[str, Any] | None = None,
) -> KaggleForecastResult | None:
    """Train and persist one aggregate-series LightGBM model."""
    if asset_id not in source.columns:
        raise KeyError(f"Generation column not found: {asset_id}")
    valid_count = int(source[asset_id].notna().sum())
    if valid_count < min_valid_observations:
        return None
    frame = _feature_frame(source, asset_id, capacity_column)
    feature_columns = feature_columns_for(capacity_column)
    train, validation, test, split = chronological_split(frame)
    required_features = [column for column in feature_columns if column not in CAPACITY_FEATURE_COLUMNS]
    train = train.dropna(subset=required_features)
    validation = validation.dropna(subset=required_features)
    test = test.dropna(subset=required_features)
    if min(len(train), len(validation), len(test)) == 0:
        return None
    params: dict[str, Any] = {
        "objective": "regression_l1", "n_estimators": 350, "learning_rate": 0.05,
        "num_leaves": 31, "min_child_samples": 20, "subsample": 0.9,
        "subsample_freq": 1, "colsample_bytree": 0.9, "random_state": 42,
        "n_jobs": 1, "verbosity": -1,
    }
    params.update(lgb_params or {})
    model = lgb.LGBMRegressor(**params)
    model.fit(
        train[list(feature_columns)], train["target_mw"],
        eval_set=[(validation[list(feature_columns)], validation["target_mw"])],
        callbacks=[lgb.early_stopping(40, verbose=False), lgb.log_evaluation(period=-1)],
    )
    validation_predictions = np.maximum(model.predict(validation[list(feature_columns)]), 0.0)
    test_predictions = np.maximum(model.predict(test[list(feature_columns)]), 0.0)
    metrics = {
        "validation_mae_mw": _metrics(validation["target_mw"], validation_predictions)["mae_mw"],
        "validation_rmse_mw": _metrics(validation["target_mw"], validation_predictions)["rmse_mw"],
        "validation_mape_pct": _metrics(validation["target_mw"], validation_predictions)["mape_pct"],
        "validation_samples": len(validation),
        "test_mae_mw": _metrics(test["target_mw"], test_predictions)["mae_mw"],
        "test_rmse_mw": _metrics(test["target_mw"], test_predictions)["rmse_mw"],
        "test_mape_pct": _metrics(test["target_mw"], test_predictions)["mape_pct"],
        "test_samples": len(test),
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stem = f"kaggle_lgbm_{_safe_asset_name(asset_id)}"
    model_path = output / f"{stem}.pkl"
    metadata_path = output / f"{stem}_metadata.json"
    joblib.dump(model, model_path)
    metadata = {
        "model_type": "LightGBM", "model_version": KAGGLE_MODEL_VERSION,
        "dataset_source": "kaggle_power_system", "dataset_file": "time_series_60min_singleindex.csv",
        "asset_id": asset_id, "energy_type": energy_type, "target": "actual_mw", "unit": "MW",
        "features": list(feature_columns), "capacity_column": capacity_column,
        "trained_at": datetime.now(timezone.utc).isoformat(), "split": asdict(split),
        "metrics": metrics, "valid_observations": valid_count,
        "weather_features_used": [], "curtailment_features_used": [],
        "aggregate_series_disclaimer": "This forecasting model predicts aggregate renewable generation and does not represent an individual physical renewable asset.",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return KaggleForecastResult(asset_id, energy_type, str(model_path), str(metadata_path), list(feature_columns), split, metrics, valid_count)


def train_kaggle_forecasters(
    dataset_dir: str | Path,
    output_dir: str | Path,
    resolution: str = DEFAULT_RESOLUTION,
    min_valid_observations: int = 500,
    lgb_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Train all sufficiently populated discovered solar and wind series."""
    path = kaggle_csv_path(dataset_dir, resolution)
    schema = discover_kaggle_schema(path)
    source = pd.read_csv(path)
    results: list[KaggleForecastResult] = []
    skipped: list[dict[str, Any]] = []
    for generation_column in schema.generation_columns:
        valid_count = int(source[generation_column].notna().sum())
        match = re.search(r"_(solar|wind)(?:_|$)", generation_column)
        energy_type = match.group(1) if match else "unknown"
        result = train_kaggle_series(
            source, generation_column, energy_type, schema.capacity_by_generation[generation_column],
            output_dir, min_valid_observations, lgb_params,
        )
        if result is None:
            skipped.append({"asset_id": generation_column, "reason": "insufficient usable observations", "valid_observations": valid_count})
        else:
            results.append(result)
    manifest = {
        "model_version": KAGGLE_MODEL_VERSION, "dataset_source": "kaggle_power_system",
        "dataset_file": path.name, "resolution": resolution, "weather_available": False,
        "curtailment_available": False, "solar_series_discovered": len(schema.solar_columns),
        "wind_series_discovered": len(schema.wind_columns),
        "solar_series_trained": sum(result.energy_type == "solar" for result in results),
        "wind_series_trained": sum(result.energy_type == "wind" for result in results),
        "results": [result.to_dict() for result in results], "skipped": skipped,
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "kaggle_forecasting_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_kaggle_forecaster(model_path: str | Path) -> lgb.LGBMRegressor:
    """Load one persisted Kaggle aggregate-series model in a fresh process."""
    return joblib.load(model_path)


def predict_kaggle_series(
    model: lgb.LGBMRegressor,
    feature_rows: pd.DataFrame,
    feature_columns: tuple[str, ...] | list[str] = FEATURE_COLUMNS,
) -> pd.Series:
    """Predict non-negative aggregate generation in MW from prepared features."""
    missing = set(feature_columns).difference(feature_rows.columns)
    if missing:
        raise ValueError(f"Prepared feature rows are missing columns: {sorted(missing)}")
    values = np.maximum(model.predict(feature_rows[list(feature_columns)]), 0.0)
    return pd.Series(values, index=feature_rows.index, name="expected_generation_mw")