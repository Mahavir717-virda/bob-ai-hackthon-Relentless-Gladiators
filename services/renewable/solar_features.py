"""
services/renewable/solar_features.py
======================================
Feature engineering for solar generation forecasting.

Responsibilities:
- Convert raw OpenSTEF Liander 2024 load measurements (Watts) to MW.
- Compute astronomical solar position (elevation/azimuth) from lat/lon + UTC
  timestamp — used as a clear-sky GHI proxy when irradiance is absent.
- Build lagged autoregressive features from historical generation.
- Align hourly weather to 15-minute timestamps via linear interpolation.

RULE: No model training here. Only deterministic, stateless transforms.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .constants import W_TO_MW

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_solar_features(
    load_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    lat: float,
    lon: float,
    asset_name: str = "unknown",
) -> pd.DataFrame:
    """
    Build a feature-complete DataFrame for LightGBM solar forecasting.

    Parameters
    ----------
    load_df : DataFrame with columns ['timestamp', 'load']
        Raw measurements in Watts, UTC, 15-min frequency.
    weather_df : DataFrame with columns ['timestamp', 'cloud_cover',
        'temperature_2m', 'relative_humidity_2m', 'surface_pressure']
        Hourly weather, UTC.  Extra columns (e.g. wind_speed_10m) are
        included automatically if present.
    lat, lon : float
        Geographic coordinates of the solar asset.
    asset_name : str
        Identifier string (used in logging only).

    Returns
    -------
    DataFrame indexed by timestamp.  Rows with any NaN in the canonical
    feature columns are dropped (only the head of the series is affected
    due to lag burn-in).
    """
    df = _prepare_load(load_df)
    df = _add_time_features(df)
    df = _add_solar_position(df, lat, lon)
    df = _add_weather_features(df, weather_df)
    df = _add_lag_features(df)
    df = _add_rolling_features(df)
    df = df.dropna(subset=list(FEATURE_COLS))
    return df


def get_feature_names() -> list[str]:
    """Return the ordered list of feature column names used by the model."""
    return list(FEATURE_COLS)


def get_target_name() -> str:
    return "solar_generation_mw"


# ---------------------------------------------------------------------------
# Feature column registry
# ---------------------------------------------------------------------------

FEATURE_COLS: tuple[str, ...] = (
    # ── Time ────────────────────────────────────────────────────────────────
    "hour_of_day",
    "minute_of_day",
    "day_of_year",
    "month",
    "day_of_week",
    "is_weekend",
    # ── Astronomical (irradiance proxy) ─────────────────────────────────────
    "solar_elevation_deg",
    "solar_azimuth_deg",
    "cos_solar_zenith",      # sin(elevation); proportional to clear-sky GHI
    # ── Weather ─────────────────────────────────────────────────────────────
    "cloud_cover",
    "temperature_2m",
    "relative_humidity_2m",
    "surface_pressure",
    # ── Autoregressive lags (15-min steps) ──────────────────────────────────
    "lag_1",    # t-15 min
    "lag_2",    # t-30 min
    "lag_4",    # t-1 h
    "lag_8",    # t-2 h
    "lag_96",   # t-24 h  (same hour yesterday)
    "lag_192",  # t-48 h
    "lag_672",  # t-7 days (same weekday + hour)
    # ── Rolling statistics ───────────────────────────────────────────────────
    "roll_mean_4",   # 1-h  trailing mean
    "roll_mean_96",  # 24-h trailing mean
    "roll_std_96",   # 24-h trailing std
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _prepare_load(load_df: pd.DataFrame) -> pd.DataFrame:
    df = load_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")
    # Convert W -> MW; night-time zeros are genuine, not missing
    df["solar_generation_mw"] = (df["load"] * W_TO_MW).clip(lower=0.0)
    return df


def _add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    df["hour_of_day"]   = idx.hour
    df["minute_of_day"] = idx.hour * 60 + idx.minute
    df["day_of_year"]   = idx.day_of_year
    df["month"]         = idx.month
    df["day_of_week"]   = idx.day_of_week       # Mon=0, Sun=6
    df["is_weekend"]    = (df["day_of_week"] >= 5).astype(int)
    return df


def _add_solar_position(df: pd.DataFrame, lat: float, lon: float) -> pd.DataFrame:
    """
    Compute solar elevation and azimuth using Spencer (1971) declination.
    Accuracy ~0.5 deg -- sufficient for cloud-era irradiance proxying.
    """
    lat_r = math.radians(lat)
    elevations, azimuths = [], []

    for ts in df.index:
        doy = ts.day_of_year
        # Spencer declination (radians)
        B = math.radians((360 / 365) * (doy - 81))
        decl = math.radians(23.45 * math.sin(B))
        # Equation of time (minutes)
        eot = 9.87 * math.sin(2 * B) - 7.53 * math.cos(B) - 1.5 * math.sin(B)
        # Local solar time (minutes)
        solar_time_min = (ts.hour * 60 + ts.minute) + (lon / 15 * 60) + eot
        hour_angle = math.radians((solar_time_min / 4) - 180)
        # Elevation
        sin_elev = (
            math.sin(lat_r) * math.sin(decl)
            + math.cos(lat_r) * math.cos(decl) * math.cos(hour_angle)
        )
        elevation = math.degrees(math.asin(max(-1.0, min(1.0, sin_elev))))
        # Azimuth (north-clockwise)
        cos_az = (
            (math.sin(decl) - math.sin(math.radians(elevation)) * math.sin(lat_r))
            / (math.cos(math.radians(elevation)) * math.cos(lat_r) + 1e-10)
        )
        azimuth = math.degrees(math.acos(max(-1.0, min(1.0, cos_az))))
        if hour_angle > 0:
            azimuth = 360 - azimuth
        elevations.append(elevation)
        azimuths.append(azimuth)

    df["solar_elevation_deg"] = elevations
    df["solar_azimuth_deg"]   = azimuths
    df["cos_solar_zenith"]    = np.sin(np.radians(df["solar_elevation_deg"])).clip(0.0)
    return df


def _add_weather_features(df: pd.DataFrame, weather_df: pd.DataFrame) -> pd.DataFrame:
    """Interpolate hourly weather to 15-min index and merge."""
    w = weather_df.copy()
    w["timestamp"] = pd.to_datetime(w["timestamp"], utc=True)
    w = w.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")

    # Accept confirmed + optional columns
    keep = [c for c in [
        "cloud_cover", "temperature_2m", "relative_humidity_2m", "surface_pressure",
        "wind_speed_10m", "wind_direction_10m",
    ] if c in w.columns]
    w = w[keep]

    # Reindex to 15-min and time-interpolate
    full_idx = df.index.union(w.index).sort_values()
    w = w.reindex(full_idx).interpolate(method="time").reindex(df.index)
    for col in keep:
        df[col] = w[col].values

    # Ensure mandatory columns exist (filled NaN if truly absent)
    for col in ["cloud_cover", "temperature_2m", "relative_humidity_2m", "surface_pressure"]:
        if col not in df.columns:
            df[col] = np.nan
    return df


def _add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    gen = df["solar_generation_mw"]
    df["lag_1"]   = gen.shift(1)
    df["lag_2"]   = gen.shift(2)
    df["lag_4"]   = gen.shift(4)
    df["lag_8"]   = gen.shift(8)
    df["lag_96"]  = gen.shift(96)
    df["lag_192"] = gen.shift(192)
    df["lag_672"] = gen.shift(672)
    return df


def _add_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    gen = df["solar_generation_mw"]
    df["roll_mean_4"]  = gen.shift(1).rolling(4,  min_periods=2).mean()
    df["roll_mean_96"] = gen.shift(1).rolling(96, min_periods=48).mean()
    df["roll_std_96"]  = gen.shift(1).rolling(96, min_periods=48).std().fillna(0.0)
    return df
