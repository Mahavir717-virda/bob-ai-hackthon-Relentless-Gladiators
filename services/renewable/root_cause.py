"""Deviation-association analysis using separate solar and wind XGBoost models.

Models predict percentage deviation, not unobserved labels.  SHAP values show
which supplied signals are most strongly associated with a row's predicted
deviation.  They are not proof of physical causation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
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

logger = logging.getLogger(__name__)

ROOT_CAUSE_MODEL_VERSION = "1.0.0"

# Default model directory: ml/models/renewable/ relative to this package
_DEFAULT_MODEL_DIR: Path = Path(__file__).resolve().parents[2] / "ml" / "models" / "renewable"
VALIDATION_FRACTION = 0.20
NEGLIGIBLE_DEVIATION_PERCENT = 5.0

# Every selected engineered feature has an explicit human-readable category.
FEATURE_CATEGORY_LOOKUP: dict[str, str] = {
    "cloud_cover": "weather_cloud_cover",
    "solar_elevation_deg": "solar_position",
    "cos_solar_zenith": "solar_position",
    "temperature_2m": "weather_temperature",
    "relative_humidity_2m": "weather_humidity",
    "surface_pressure": "weather_pressure",
    "wind_speed_10m": "weather_wind_speed",
    "wind_speed_cubed": "weather_wind_speed",
    "wind_speed_roll_mean_4": "weather_wind_speed",
    "wind_speed_roll_mean_96": "weather_wind_speed",
    "wind_direction_10m": "weather_wind_direction",
    "wind_dir_sin": "weather_wind_direction",
    "wind_dir_cos": "weather_wind_direction",
    "air_density_proxy": "weather_air_density",
    "hour_of_day": "time_pattern",
    "minute_of_day": "time_pattern",
    "day_of_year": "time_pattern",
    "month": "time_pattern",
    "day_of_week": "time_pattern",
    "is_weekend": "time_pattern",
    "season": "time_pattern",
    "lag_1": "persistent_pattern",
    "lag_2": "persistent_pattern",
    "lag_4": "persistent_pattern",
    "lag_8": "persistent_pattern",
    "lag_96": "persistent_pattern",
    "lag_192": "persistent_pattern",
    "lag_672": "persistent_pattern",
    "roll_mean_4": "persistent_pattern",
    "roll_mean_96": "persistent_pattern",
    "roll_std_96": "persistent_pattern",
    "anomaly": "unexplained_anomaly",
    "diagnostic_category_weather_driven_reduction": "weather_cloud_cover",
    "diagnostic_category_possible_physical_fault": "persistent_pattern",
    "diagnostic_category_data_quality_issue": "data_quality_signal",
    "diagnostic_category_intentional_curtailment": "curtailment_signal",
    "diagnostic_category_uncertain": "other_factor",
    "diagnostic_category_normal_production": "normal_operation",
}

_COMMON_FEATURES = (
    "cloud_cover", "temperature_2m", "relative_humidity_2m", "surface_pressure",
    "hour_of_day", "minute_of_day", "day_of_year", "month", "day_of_week", "is_weekend", "season",
    "lag_1", "lag_2", "lag_4", "lag_8", "lag_96", "lag_192", "lag_672",
    "roll_mean_4", "roll_mean_96", "roll_std_96", "anomaly",
)
_ASSET_FEATURES = {
    "solar": ("solar_elevation_deg", "cos_solar_zenith"),
    "wind": ("wind_speed_10m", "wind_speed_cubed", "wind_direction_10m", "wind_dir_sin", "wind_dir_cos", "air_density_proxy", "wind_speed_roll_mean_4", "wind_speed_roll_mean_96"),
}


@dataclass
class _ModelBundle:
    model: XGBRegressor
    explainer: shap.TreeExplainer
    feature_columns: list[str]
    rows: pd.DataFrame
    metrics: dict[str, float]


_BUNDLES: dict[str, _ModelBundle] = {}


def _model_frame(df: pd.DataFrame, asset_type: str, columns: list[str] | None = None) -> pd.DataFrame:
    """Select existing engineered features; no feature values are recomputed."""
    selected = [name for name in _COMMON_FEATURES + _ASSET_FEATURES[asset_type] if name in df.columns]
    numeric = df[selected].apply(pd.to_numeric, errors="coerce") if selected else pd.DataFrame(index=df.index)
    diagnostic = pd.get_dummies(df.get("diagnostic_category", pd.Series("uncertain", index=df.index)), prefix="diagnostic_category", dtype=float)
    features = pd.concat([numeric, diagnostic], axis=1).replace([np.inf, -np.inf], np.nan)
    features = features.fillna(features.median()).fillna(0.0)
    return features.reindex(columns=columns, fill_value=0.0) if columns else features


def train_root_cause_model(
    analysis_df: pd.DataFrame,
    asset_type: str,
    output_dir: str | Path | None = _DEFAULT_MODEL_DIR,
) -> dict[str, Any]:
    """Chronologically train and register one deviation-association model.

    ``analysis_df`` is the anomaly-detector output augmented with already-built
    solar or wind engineered columns.  Percentage deviation is used because it
    is scale-comparable across assets, unlike MW deviation.

    The trained model, metadata JSON, and the training rows parquet are saved to
    ``output_dir`` (default: ml/models/renewable/) so that a fresh process can
    restore the full bundle via ``load_root_cause_model()`` without retraining.
    Pass ``output_dir=None`` to suppress all disk writes (tests only).
    """
    if asset_type not in _ASSET_FEATURES:
        raise ValueError("asset_type must be 'solar' or 'wind'")
    required = {"asset_id", "asset_type", "timestamp", "percentage_deviation", "diagnostic_category", "anomaly"}
    missing = required.difference(analysis_df.columns)
    if missing:
        raise ValueError(f"analysis_df is missing required columns: {sorted(missing)}")
    rows = analysis_df.loc[analysis_df["asset_type"].eq(asset_type)].copy()
    rows["timestamp"] = pd.to_datetime(rows["timestamp"], utc=True)
    rows = rows.sort_values("timestamp").reset_index(drop=True)
    target = pd.to_numeric(rows["percentage_deviation"], errors="coerce")
    valid = np.isfinite(target)
    rows, target = rows.loc[valid].reset_index(drop=True), target.loc[valid].reset_index(drop=True)
    if len(rows) < 10:
        raise ValueError("At least 10 finite historical rows are required for association analysis")

    features = _model_frame(rows, asset_type)
    split = max(1, int(len(rows) * (1 - VALIDATION_FRACTION)))
    if split >= len(rows):
        split = len(rows) - 1
    model_params = {
        "objective": "reg:squarederror", "n_estimators": 160, "max_depth": 3,
        "learning_rate": 0.05, "subsample": 0.9, "colsample_bytree": 0.9,
        "random_state": RANDOM_SEED, "n_jobs": 1,
    }
    model = XGBRegressor(**model_params)
    model.fit(features.iloc[:split], target.iloc[:split])
    predictions = model.predict(features.iloc[split:])
    metrics = {
        "mae_percentage_points": float(mean_absolute_error(target.iloc[split:], predictions)),
        "rmse_percentage_points": float(np.sqrt(mean_squared_error(target.iloc[split:], predictions))),
    }
    bundle = _ModelBundle(model, shap.TreeExplainer(model), list(features.columns), rows, metrics)
    _BUNDLES[asset_type] = bundle

    metadata = {
        "model_name": f"root_cause_xgb_{asset_type}",
        "model_type": "XGBoostRegressor", "algorithm": "XGBoost",
        "task": "percentage_deviation_association",
        "asset_type": asset_type, "version": ROOT_CAUSE_MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(), "features": bundle.feature_columns,
        "target": "percentage_deviation", "n_train_rows": split, "n_val_rows": len(rows) - split,
        "training_rows": split, "validation_rows": len(rows) - split,
        "hyperparameters": model_params,
        "train_period": {"start": str(rows.iloc[0].timestamp), "end": str(rows.iloc[split - 1].timestamp)},
        "val_period": {"start": str(rows.iloc[split].timestamp), "end": str(rows.iloc[-1].timestamp)},
        "validation_metrics": metrics,
        "notes": "SHAP identifies associations in deviation predictions; it does not establish physical causation.",
    }
    result: dict[str, Any] = {"model": model, "metrics": metrics, "metadata": metadata}
    if output_dir is not None:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        model_path = directory / f"root_cause_xgb_{asset_type}.pkl"
        metadata_path = directory / f"root_cause_xgb_{asset_type}_metadata.json"
        rows_path = directory / f"root_cause_xgb_{asset_type}_rows.parquet"
        metadata.update({"artifact_path": str(model_path), "artifact_format": "joblib/pickle"})
        joblib.dump(model, model_path)
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        # Save the training rows so load_root_cause_model() can fully restore the bundle
        # without re-training. Timestamps are stored as UTC strings for cross-platform safety.
        rows_to_save = rows.copy()
        rows_to_save["timestamp"] = rows_to_save["timestamp"].astype(str)
        rows_to_save.to_parquet(rows_path, index=False)
        result.update(
            model_path=str(model_path),
            metadata_path=str(metadata_path),
            rows_path=str(rows_path),
        )
        logger.info(
            "[root_cause][%s] Saved: model=%s  metadata=%s  rows=%s",
            asset_type, model_path, metadata_path, rows_path,
        )
    return result


def load_root_cause_model(
    asset_type: str,
    model_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Load a persisted root-cause bundle from disk and register it in ``_BUNDLES``.

    Call this once per process (or rely on the auto-load at module import) so
    that ``analyzeRootCause`` can return real categories without re-training.

    Parameters
    ----------
    asset_type : 'solar' or 'wind'
    model_dir  : directory containing root_cause_xgb_{asset_type}.pkl,
                 _metadata.json, and _rows.parquet.  Defaults to
                 ml/models/renewable/ relative to this package.

    Returns
    -------
    dict with keys: model, metrics, feature_columns, n_rows.

    Raises
    ------
    FileNotFoundError  if any required artifact is missing.
    ValueError         if asset_type is unsupported.
    """
    if asset_type not in _ASSET_FEATURES:
        raise ValueError("asset_type must be 'solar' or 'wind'")
    directory = Path(model_dir) if model_dir is not None else _DEFAULT_MODEL_DIR
    model_path = directory / f"root_cause_xgb_{asset_type}.pkl"
    rows_path = directory / f"root_cause_xgb_{asset_type}_rows.parquet"
    metadata_path = directory / f"root_cause_xgb_{asset_type}_metadata.json"
    for path in (model_path, rows_path, metadata_path):
        if not path.exists():
            raise FileNotFoundError(
                f"Root-cause artifact missing: {path}. "
                "Run train_root_cause_model() with a populated analysis_df first."
            )
    model: XGBRegressor = joblib.load(model_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    feature_columns: list[str] = metadata["features"]
    rows = pd.read_parquet(rows_path)
    rows["timestamp"] = pd.to_datetime(rows["timestamp"], utc=True)
    explainer = shap.TreeExplainer(model)
    metrics = metadata.get("validation_metrics", {})
    bundle = _ModelBundle(model, explainer, feature_columns, rows, metrics)
    _BUNDLES[asset_type] = bundle
    logger.info(
        "[root_cause][%s] Loaded persisted bundle: %d rows, features=%d",
        asset_type, len(rows), len(feature_columns),
    )
    return {
        "model": model,
        "metrics": metrics,
        "feature_columns": feature_columns,
        "n_rows": len(rows),
    }


def _auto_load_bundles(model_dir: Path | None = None) -> None:
    """Silently load any persisted root-cause bundles found on disk at import time.

    This is called once when the module is imported so that a fresh process
    picking up this file immediately has usable bundles registered in
    ``_BUNDLES`` — matching what ``renewable_service.py`` expects.
    If an artifact is missing or corrupt the error is logged at WARNING level
    and the bundle is skipped (graceful degradation to 'uncertain').
    """
    directory = model_dir or _DEFAULT_MODEL_DIR
    for atype in _ASSET_FEATURES:
        pkl = directory / f"root_cause_xgb_{atype}.pkl"
        if not pkl.exists():
            continue
        try:
            load_root_cause_model(atype, directory)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[root_cause] Could not auto-load '%s' bundle from %s: %s",
                atype, directory, exc,
            )


# ── Auto-load any already-trained bundles so a fresh process is immediately
# ready to serve real root-cause categories. This has zero cost when no
# artifacts exist yet (bundles are empty and _auto_load_bundles returns silently).
_auto_load_bundles()


def _uncertain(reason: str) -> dict[str, Any]:
    return {"category": "uncertain", "confidence": 0.0, "evidence": {"reason": reason, "top_features": [], "model_version": ROOT_CAUSE_MODEL_VERSION}}


def analyzeRootCause(asset_id: str, timestamp: Any) -> dict[str, Any]:
    """Explain the strongest model association for a registered asset-time row.

    The API layer forwards only category and confidence to RenewableStatus;
    evidence remains internal for audit and troubleshooting.
    """
    requested_time = pd.to_datetime(timestamp, utc=True)
    for asset_type, bundle in _BUNDLES.items():
        match = bundle.rows.loc[(bundle.rows["asset_id"].eq(asset_id)) & (bundle.rows["timestamp"].eq(requested_time))]
        if match.empty:
            continue
        row = match.iloc[[0]]
        if abs(float(row.iloc[0]["percentage_deviation"])) < NEGLIGIBLE_DEVIATION_PERCENT and not bool(row.iloc[0]["anomaly"]):
            return _uncertain("Deviation is negligible and the row is not flagged as anomalous.")
        feature_row = _model_frame(row, asset_type, bundle.feature_columns)
        values = np.asarray(bundle.explainer.shap_values(feature_row)).reshape(-1)
        ranked = sorted(zip(bundle.feature_columns, values), key=lambda pair: abs(pair[1]), reverse=True)[:3]
        magnitude = sum(abs(float(value)) for value in values)
        top_feature, top_value = ranked[0]
        confidence = 0.0 if magnitude == 0 else float(abs(top_value) / magnitude)
        category = FEATURE_CATEGORY_LOOKUP.get(top_feature, "other_factor")
        return {
            "category": category,
            "confidence": max(0.0, min(1.0, confidence)),
            "evidence": {
                "top_features": [{"feature": name, "shap_value": float(value)} for name, value in ranked],
                "model_version": ROOT_CAUSE_MODEL_VERSION,
            },
        }
    return _uncertain("No registered model history contains the requested asset and timestamp.")
