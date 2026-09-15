"""
services/renewable/solar_model.py
====================================
LightGBM solar generation forecasting model.

Responsibilities:
- Train a LightGBM regressor on chronologically split data.
- Evaluate with MAE, RMSE, MAPE on a held-out validation window.
- Persist the trained model (joblib) and a human-readable metadata JSON.
- Load a saved model for inference.
- Provide a predict() interface that returns MW values.

RULE (Rule A): This module ONLY produces predictions.  It does NOT make
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

from .constants import SOLAR_MODEL_VERSION, RANDOM_SEED
from .solar_features import build_solar_features, get_feature_names, get_target_name

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LGB_PARAMS: dict[str, Any] = {
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

# Early stopping to prevent overfitting (requires val set)
EARLY_STOPPING_ROUNDS: int = 50
VALIDATION_FRACTION: float = 0.2   # last 20 % of timeline = validation


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_solar_model(
    load_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    lat: float,
    lon: float,
    asset_name: str,
    output_dir: str | Path,
    lgb_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Train, validate, and save a LightGBM solar forecasting model.

    Parameters
    ----------
    load_df : DataFrame ['timestamp', 'load']  (Watts, UTC, 15-min)
    weather_df : DataFrame ['timestamp', weather cols]  (hourly, UTC)
    lat, lon : float  – asset coordinates
    asset_name : str  – used for file naming and metadata
    output_dir : path  – directory where model.pkl + metadata.json are saved
    lgb_params : optional overrides for LightGBM hyperparameters

    Returns
    -------
    dict with keys: model_path, metadata_path, metrics, feature_importance
    """
    params = {**DEFAULT_LGB_PARAMS, **(lgb_params or {})}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Feature engineering
    logger.info("[solar] Building features for %s …", asset_name)
    df = build_solar_features(load_df, weather_df, lat, lon, asset_name)
    feat_cols = get_feature_names()
    target_col = get_target_name()

    X = df[feat_cols]
    y = df[target_col]

    # 2. Chronological train / validation split (no shuffling — time series)
    n = len(df)
    split_idx = int(n * (1 - VALIDATION_FRACTION))
    X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]
    logger.info(
        "[solar] Train rows: %d | Val rows: %d", len(X_train), len(X_val)
    )

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
    y_pred = np.maximum(y_pred, 0.0)   # generation cannot be negative
    metrics = _compute_metrics(y_val.values, y_pred, asset_name)

    # 5. Feature importance
    importance = dict(zip(feat_cols, model.feature_importances_.tolist()))
    top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]

    # 6. Save model
    safe_name = asset_name.replace("/", "_").replace(" ", "_")
    model_path = output_dir / f"solar_lgbm_{safe_name}.pkl"
    joblib.dump(model, model_path)
    logger.info("[solar] Model saved to %s", model_path)

    # 7. Save metadata
    metadata = {
        "model_name": f"solar_lgbm_{safe_name}",
        "model_type": "LightGBM",
        "algorithm": "LightGBM",
        "task": "solar_generation_forecast",
        "asset_name": asset_name,
        "version": SOLAR_MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "features": feat_cols,
        "target": target_col,
        "prediction_interval": "15min",
        "n_train_rows": int(len(X_train)),
        "n_val_rows": int(len(X_val)),
        "training_rows": int(len(X_train)),
        "validation_rows": int(len(X_val)),
        "train_period": {
            "start": str(X_train.index.min()),
            "end":   str(X_train.index.max()),
        },
        "val_period": {
            "start": str(X_val.index.min()),
            "end":   str(X_val.index.max()),
        },
        "lgb_params": params,
        "hyperparameters": params,
        "artifact_path": str(model_path),
        "artifact_format": "joblib/pickle",
        "best_iteration": int(model.best_iteration_) if hasattr(model, "best_iteration_") else params["n_estimators"],
        "validation_metrics": metrics,
        "top_10_features_by_importance": top_features,
        "unit": "MW",
        "data_source": "OpenSTEF Liander 2024 (synthetic fixture in absence of downloaded data)",
        "notes": (
            "Generation values in Watts converted to MW (x1e-6). "
            "Night-time zeros are genuine, not imputed. "
            "Validation split is strictly chronological (last 20% of timeline). "
            "No shuffle applied to preserve temporal integrity."
        ),
    }
    metadata_path = output_dir / f"solar_lgbm_{safe_name}_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)
    logger.info("[solar] Metadata saved to %s", metadata_path)

    return {
        "model_path": str(model_path),
        "metadata_path": str(metadata_path),
        "metrics": metrics,
        "feature_importance": importance,
        "model": model,
    }


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def load_solar_model(model_path: str | Path) -> lgb.LGBMRegressor:
    """Load a persisted LightGBM solar model from disk."""
    return joblib.load(model_path)


def predict_solar(
    model: lgb.LGBMRegressor,
    load_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    lat: float,
    lon: float,
    asset_name: str = "unknown",
) -> pd.Series:
    """
    Generate solar generation forecasts (MW) for the given inputs.

    Returns a Series indexed by timestamp, values in MW, clipped >= 0.
    """
    df = build_solar_features(load_df, weather_df, lat, lon, asset_name)
    feat_cols = get_feature_names()
    X = df[feat_cols]
    y_pred = model.predict(X)
    y_pred = np.maximum(y_pred, 0.0)
    return pd.Series(y_pred, index=df.index, name="solar_forecast_mw")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    asset_name: str,
) -> dict[str, float]:
    """
    Compute MAE, RMSE, MAPE on the validation set.

    MAPE denominator uses (|y_true| + epsilon) to avoid divide-by-zero
    on night-time zero-generation intervals.
    """
    mae  = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))

    # Masked MAPE: exclude intervals where true generation < 0.001 MW
    # (night-time zeros would inflate MAPE to meaningless values)
    day_mask = y_true >= 0.001
    if day_mask.sum() > 0:
        mape = float(
            np.mean(
                np.abs((y_true[day_mask] - y_pred[day_mask]) / (y_true[day_mask] + 1e-9))
            ) * 100
        )
    else:
        mape = float("nan")

    logger.info(
        "[solar][%s] VAL  MAE=%.4f MW | RMSE=%.4f MW | MAPE=%.2f%%",
        asset_name, mae, rmse, mape,
    )
    return {
        "mae_mw":  round(mae,  6),
        "rmse_mw": round(rmse, 6),
        "mape_pct": round(mape, 4) if not np.isnan(mape) else None,
        "n_samples": int(len(y_true)),
        "n_daytime_samples_for_mape": int(day_mask.sum()),
    }
