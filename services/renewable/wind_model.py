"""
services/renewable/wind_model.py
===================================
LightGBM wind generation forecasting model.

Responsibilities:
- Train a LightGBM regressor on chronologically split wind generation data.
- Evaluate with MAE, RMSE, MAPE on a held-out validation window.
- Exclude calm periods (< 0.05 MW) from MAPE to avoid divide-by-zero distortion.
- Persist the trained model (joblib) and a human-readable metadata JSON.
- Expose load_wind_model, predict_wind, and forecast_wind_generation service interface.

RULE (Rule A): This module ONLY produces predictions. It does NOT make
dispatch decisions, schedule resources, or curtail assets.
"""

from __future__ import annotations

import json
import logging
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .constants import WIND_MODEL_VERSION, RANDOM_SEED, W_TO_MW
from .wind_features import (
    build_wind_features,
    get_wind_feature_names,
    get_wind_target_name,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LGB_WIND_PARAMS: dict[str, Any] = {
    "objective": "regression_l1",       # MAE-optimised
    "metric": ["mae", "rmse"],
    "n_estimators": 1000,
    "learning_rate": 0.05,
    "num_leaves": 63,
    "max_depth": -1,
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "n_jobs": -1,
    "random_state": RANDOM_SEED,
    "verbose": -1,
}

EARLY_STOPPING_ROUNDS: int = 50
VALIDATION_FRACTION: float = 0.2   # last 20 % of timeline = validation
CALM_WIND_MW_THRESHOLD: float = 0.05  # below 50 kW = calm wind for MAPE mask


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_wind_model(
    load_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    asset_name: str,
    output_dir: str | Path,
    wind_speed_source: str = "auto",
    data_source: str = "calibrated_synthetic_fixture",
    lgb_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Train, validate, and save a LightGBM wind forecasting model.

    Parameters
    ----------
    load_df : DataFrame ['timestamp', 'load'] (Watts, UTC, 15-min)
    weather_df : DataFrame ['timestamp', ...] (hourly, UTC)
    asset_name : str - asset identifier
    output_dir : path - destination for model.pkl + metadata.json
    wind_speed_source : 'auto' | 'real' | 'synthetic'
    data_source : str - description of data source ('calibrated_synthetic_fixture' or 'OpenSTEF Liander 2024')
    lgb_params : optional overrides for hyperparameters

    Returns
    -------
    dict with keys: model_path, metadata_path, metrics, feature_importance, model
    """
    params = {**DEFAULT_LGB_WIND_PARAMS, **(lgb_params or {})}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Feature engineering
    logger.info("[wind] Building features for %s (source=%s) ...", asset_name, wind_speed_source)
    df = build_wind_features(
        load_df=load_df,
        weather_df=weather_df,
        asset_name=asset_name,
        wind_speed_source=wind_speed_source,
    )
    feat_cols = get_wind_feature_names()
    target_col = get_wind_target_name()

    X = df[feat_cols]
    y = df[target_col]

    # 2. Chronological train / validation split (no shuffling -- time series)
    n = len(df)
    split_idx = int(n * (1 - VALIDATION_FRACTION))
    X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]
    logger.info("[wind] Train rows: %d | Val rows: %d", len(X_train), len(X_val))

    # 3. Train LightGBM with early stopping on validation
    model = lgb.LGBMRegressor(**params)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[
                lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False),
                lgb.log_evaluation(period=-1),
            ],
        )

    # 4. Evaluate on validation set
    y_pred = model.predict(X_val)
    y_pred = np.maximum(y_pred, 0.0)   # wind power cannot be negative
    metrics = _compute_wind_metrics(y_val.values, y_pred, asset_name)

    # 5. Feature importance
    importance = dict(zip(feat_cols, [int(x) for x in model.feature_importances_]))
    top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]

    # 6. Save model
    safe_name = asset_name.replace("/", "_").replace(" ", "_")
    model_path = output_dir / f"wind_lgbm_{safe_name}.pkl"
    joblib.dump(model, model_path)
    logger.info("[wind] Model saved to %s", model_path)

    # 7. Save metadata
    has_real_wind = "wind_speed_10m" in weather_df.columns and ("synth" not in asset_name.lower()) and (data_source != "calibrated_synthetic_fixture")
    wind_status = "real_openstef" if has_real_wind else "calibrated_synthetic_fixture"

    metadata = {
        "model_type": "LightGBM",
        "task": "wind_generation_forecast",
        "asset_name": asset_name,
        "version": WIND_MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "features": feat_cols,
        "target": target_col,
        "n_train_rows": int(len(X_train)),
        "n_val_rows": int(len(X_val)),
        "train_period": {
            "start": str(X_train.index.min()),
            "end": str(X_train.index.max()),
        },
        "val_period": {
            "start": str(X_val.index.min()),
            "end": str(X_val.index.max()),
        },
        "lgb_params": params,
        "best_iteration": int(model.best_iteration_) if hasattr(model, "best_iteration_") else params["n_estimators"],
        "validation_metrics": metrics,
        "top_10_features_by_importance": top_features,
        "unit": "MW",
        "data_source": data_source,
        "wind_speed_source_status": wind_status,
        "wind_speed_gap_disclosure": (
            "Step 0 Verification: Wind speed (m/s) is absent from the OpenSTEF Liander 2024 "
            "published weather_measurements schema (docs/data/openstef-renewable.md §6.3). "
            f"Active resolution: Option (b) - {wind_status}. "
            "When real OpenSTEF wind park data is downloaded, verify parquet columns and "
            "re-train with wind_speed_source='real' or weather_df containing wind_speed_10m."
        ),
        "notes": (
            "Generation values in Watts converted to MW (x1e-6). "
            "Validation split is strictly chronological (last 20% of timeline). "
            "No shuffle applied to preserve temporal integrity. "
            "Anti-leakage assertion verified before training."
        ),
    }
    metadata_path = output_dir / f"wind_lgbm_{safe_name}_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)
    logger.info("[wind] Metadata saved to %s", metadata_path)

    return {
        "model_path": str(model_path),
        "metadata_path": str(metadata_path),
        "metrics": metrics,
        "feature_importance": importance,
        "top_features": top_features,
        "model": model,
    }


# ---------------------------------------------------------------------------
# Inference & Service Interface
# ---------------------------------------------------------------------------

def load_wind_model(model_path: str | Path) -> lgb.LGBMRegressor:
    """Load a persisted LightGBM wind model from disk."""
    return joblib.load(model_path)


def predict_wind(
    model: lgb.LGBMRegressor,
    load_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    asset_name: str = "unknown",
    wind_speed_source: str = "auto",
) -> pd.Series:
    """
    Generate wind generation forecasts (MW) for the given inputs.

    Returns a Series indexed by timestamp, values in MW, clipped >= 0.
    """
    df = build_wind_features(
        load_df=load_df,
        weather_df=weather_df,
        asset_name=asset_name,
        wind_speed_source=wind_speed_source,
    )
    feat_cols = get_wind_feature_names()
    X = df[feat_cols]
    y_pred = model.predict(X)
    y_pred = np.maximum(y_pred, 0.0)
    return pd.Series(y_pred, index=df.index, name="wind_forecast_mw")


def forecast_wind_generation(
    model: lgb.LGBMRegressor | str | Path,
    load_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    asset_name: str = "unknown",
    wind_speed_source: str = "auto",
) -> pd.Series:
    """
    Service-facing interface for wind generation forecasting.
    Conforms to RenewableStatus.expectedMw contract requirements.

    Parameters
    ----------
    model : Loaded LGBMRegressor or path to persisted .pkl
    load_df : 15-minute load observations
    weather_df : Weather observations or forecasts
    asset_name : Asset identifier
    wind_speed_source : 'auto' | 'real' | 'synthetic'

    Returns
    -------
    pd.Series of forecasted expected generation in MW.
    """
    if not isinstance(model, lgb.LGBMRegressor):
        model = load_wind_model(model)
    return predict_wind(
        model=model,
        load_df=load_df,
        weather_df=weather_df,
        asset_name=asset_name,
        wind_speed_source=wind_speed_source,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _compute_wind_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    asset_name: str,
) -> dict[str, Any]:
    """
    Compute MAE, RMSE, MAPE on the validation set.

    Calm-wind periods (< CALM_WIND_MW_THRESHOLD MW) are excluded from MAPE
    to avoid divide-by-near-zero explosion, matching the solar daytime mask logic.
    """
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))

    active_mask = y_true >= CALM_WIND_MW_THRESHOLD
    if active_mask.sum() > 0:
        mape = float(
            np.mean(
                np.abs((y_true[active_mask] - y_pred[active_mask]) / (y_true[active_mask] + 1e-9))
            ) * 100.0
        )
    else:
        mape = float("nan")

    logger.info(
        "[wind][%s] VAL MAE=%.4f MW | RMSE=%.4f MW | MAPE=%.2f%% (active samples: %d/%d)",
        asset_name, mae, rmse, mape, int(active_mask.sum()), int(len(y_true)),
    )
    return {
        "mae_mw": round(mae, 6),
        "rmse_mw": round(rmse, 6),
        "mape_pct": round(mape, 4) if not np.isnan(mape) else None,
        "n_samples": int(len(y_true)),
        "n_active_samples_for_mape": int(active_mask.sum()),
        "calm_threshold_mw": CALM_WIND_MW_THRESHOLD,
    }
