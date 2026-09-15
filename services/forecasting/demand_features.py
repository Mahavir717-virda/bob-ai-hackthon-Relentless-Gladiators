"""
GridPilot AI — Reusable Demand Feature Builder
==============================================
Provides unified, past-only feature engineering functions used identically
in both model training and live production inference.

Guarantees:
- Strict leakage prevention: all lags and rolling stats evaluated on past observations.
- Shared feature names and column order between training and inference.
- Handling of raw telemetry, history windows, and weather context.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from services.forecasting.features import (
    FEATURE_PIPELINE_VERSION,
    DemandFeaturePipeline,
    FeatureConfig,
)
from services.forecasting.holidays import (
    DUTCH_HOLIDAYS_2024,
    DUTCH_HOLIDAY_DATES_2024,
    get_holiday_name,
    is_dutch_holiday,
)

__all__ = [
    "FEATURE_PIPELINE_VERSION",
    "DemandFeaturePipeline",
    "FeatureConfig",
    "build_demand_features",
    "build_spike_features",
    "is_dutch_holiday",
    "get_holiday_name",
    "DUTCH_HOLIDAYS_2024",
    "DUTCH_HOLIDAY_DATES_2024",
    "DEMAND_FEATURE_NAMES",
    "SPIKE_FEATURE_NAMES",
]

# Standardized feature column ordering
DEMAND_FEATURE_NAMES: List[str] = [
    "temperature_2m",
    "relative_humidity_2m",
    "surface_pressure",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "direct_normal_irradiance",
    "demand_mw_lag_15m",
    "demand_mw_lag_30m",
    "demand_mw_lag_60m",
    "demand_mw_lag_1440m",
    "demand_mw_roll_mean_4",
    "demand_mw_roll_std_4",
    "demand_mw_roll_min_4",
    "demand_mw_roll_max_4",
    "demand_mw_roll_mean_16",
    "demand_mw_roll_std_16",
    "demand_mw_roll_min_16",
    "demand_mw_roll_max_16",
    "demand_mw_roll_mean_96",
    "demand_mw_roll_std_96",
    "demand_mw_roll_min_96",
    "demand_mw_roll_max_96",
    "demand_mw_diff_15m",
    "demand_mw_diff_1h",
    "hour",
    "day_of_week",
    "is_weekend",
    "is_holiday",
    "season",
    "sin_hour",
    "cos_hour",
    "sin_dow",
    "cos_dow",
]

SPIKE_FEATURE_NAMES: List[str] = [
    "current_load",
    "forecast_load",
    "load_growth_pct",
    "historical_peak_24h",
    "temp_c",
    "humidity",
    "cloud_cover",
    "wind_speed",
    "solar_radiation",
    "hour",
    "hour_sin",
    "hour_cos",
    "day_of_week",
    "is_weekend",
]


def build_demand_features(
    telemetry_df: pd.DataFrame,
    weather_df: Optional[pd.DataFrame] = None,
    config: Optional[FeatureConfig] = None,
) -> pd.DataFrame:
    """
    Construct demand forecasting features strictly from past telemetry.

    Parameters
    ----------
    telemetry_df : pd.DataFrame
        DataFrame with 'timestamp' and 'demand_mw' (or 'load' in Watts).
    weather_df : pd.DataFrame, optional
        Historical/aligned weather measurements or forecast.
    config : FeatureConfig, optional
        Custom feature configuration.

    Returns
    -------
    pd.DataFrame
        DataFrame containing computed features with timestamps.
    """
    pipeline = DemandFeaturePipeline(config or FeatureConfig())
    df = telemetry_df.copy()

    # If 'demand_mw' is missing but 'load' is present, convert Watts to MW
    if "demand_mw" not in df.columns and "load" in df.columns:
        df["demand_mw"] = df["load"].astype(float) / 1e6

    feated_df = pipeline.transform(df, weather_df=weather_df)

    # Ensure all expected feature columns exist (fill weather defaults if absent)
    for col in DEMAND_FEATURE_NAMES:
        if col not in feated_df.columns:
            feated_df[col] = 0.0

    return feated_df


def build_spike_features(
    history_df: pd.DataFrame,
    predicted_next_mw: Optional[float] = None,
    latest_feature_row: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Construct spike classification feature row strictly without future leakage.

    Parameters
    ----------
    history_df : pd.DataFrame
        Telemetry history (at least 96 steps recommended for 24h rolling peak).
    predicted_next_mw : float, optional
        Short-term point forecast (e.g. from LightGBM 15m). If None, persistence is used.
    latest_feature_row : pd.DataFrame, optional
        Pre-extracted demand feature row for weather and calendar features.

    Returns
    -------
    pd.DataFrame
        Single-row DataFrame matching SPIKE_FEATURE_NAMES exactly.
    """
    df = history_df.sort_values("timestamp").reset_index(drop=True)
    if "demand_mw" not in df.columns and "load" in df.columns:
        df["demand_mw"] = df["load"].astype(float) / 1e6

    curr_mw = float(df["demand_mw"].iloc[-1])
    fcst_mw = float(predicted_next_mw) if predicted_next_mw is not None else curr_mw

    eps = 0.10
    denom = max(curr_mw, eps)
    growth_pct = ((fcst_mw - curr_mw) / denom) * 100.0

    # Past rolling 24h peak strictly excluding current step (using shift(1) or tail up to -1)
    if len(df) > 1:
        past_window = df["demand_mw"].iloc[:-1].tail(96)
        peak_24h = float(past_window.max()) if len(past_window) > 0 else curr_mw
    else:
        peak_24h = curr_mw

    last_ts = pd.to_datetime(df["timestamp"].iloc[-1], utc=True)
    hour = int(last_ts.hour)
    dow = int(last_ts.weekday())
    is_weekend = int(dow >= 5)

    # Weather extraction
    temp_c = 15.0
    humidity = 70.0
    cloud_cover = 50.0
    wind_speed = 10.0
    solar_radiation = 0.0

    if latest_feature_row is not None and not latest_feature_row.empty:
        feat_dict = latest_feature_row.iloc[0].to_dict()
        temp_c = float(feat_dict.get("temperature_2m", feat_dict.get("temp_c", 15.0)))
        humidity = float(feat_dict.get("relative_humidity_2m", feat_dict.get("humidity", 70.0)))
        cloud_cover = float(feat_dict.get("cloud_cover", 50.0))
        wind_speed = float(feat_dict.get("wind_speed_10m", feat_dict.get("wind_speed", 10.0)))
        solar_radiation = float(feat_dict.get("shortwave_radiation", feat_dict.get("solar_radiation", 0.0)))

    row = {
        "current_load": curr_mw,
        "forecast_load": fcst_mw,
        "load_growth_pct": growth_pct,
        "historical_peak_24h": peak_24h,
        "temp_c": temp_c,
        "humidity": humidity,
        "cloud_cover": cloud_cover,
        "wind_speed": wind_speed,
        "solar_radiation": solar_radiation,
        "hour": hour,
        "hour_sin": float(np.sin(2 * np.pi * hour / 24.0)),
        "hour_cos": float(np.cos(2 * np.pi * hour / 24.0)),
        "day_of_week": dow,
        "is_weekend": is_weekend,
    }

    return pd.DataFrame([row])[SPIKE_FEATURE_NAMES]
