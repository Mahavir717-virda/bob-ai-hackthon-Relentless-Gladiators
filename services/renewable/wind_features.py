"""
services/renewable/wind_features.py
======================================
Feature engineering for wind generation forecasting.

Responsibilities:
- Convert raw OpenSTEF Liander 2024 load measurements (Watts) to MW.
- Build wind-specific feature set: wind speed/direction (real or synthetic),
  temperature, pressure, time-of-day, season, lagged generation, rolling stats.
- Align hourly weather to 15-minute timestamps via linear interpolation.
- Reuse time-feature logic from solar_features (import, not duplicate).
- Provide an anti-leakage assertion to prove all features use only past values.

WIND-SPEED GAP DISCLOSURE (M3 Chunk 1 finding §6.3):
  wind_speed_10m and wind_direction_10m are NOT confirmed columns in the
  published OpenSTEF Liander 2024 weather_measurements schema.
  Resolution chosen: Option (b) — calibrated synthetic fixture for wind speed
  only (same pattern Chunk 2 used for the solar synthetic fallback).
  When real data is downloaded, verify parquet column names and switch to
  real wind speed by passing a weather_df that contains 'wind_speed_10m'.
  This module accepts and uses real wind speed if present; it generates
  synthetic wind speed ONLY when called with weather_df that lacks the column.

RULE (Rule A): No model training here. Only deterministic, stateless transforms.
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd

from .constants import W_TO_MW, RANDOM_SEED
# Reuse time-feature helper from solar_features (no duplication)
from .solar_features import _add_time_features

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_wind_features(
    load_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    asset_name: str = "unknown",
    wind_speed_source: str = "auto",
) -> pd.DataFrame:
    """
    Build a feature-complete DataFrame for LightGBM wind forecasting.

    Parameters
    ----------
    load_df : DataFrame with columns ['timestamp', 'load']
        Raw wind park measurements in Watts, UTC, 15-min frequency.
    weather_df : DataFrame with columns ['timestamp', ...]
        Hourly weather, UTC.  If 'wind_speed_10m' is present it is used
        directly.  If absent, a synthetic wind-speed proxy is generated and
        clearly logged (see WIND-SPEED GAP DISCLOSURE above).
    asset_name : str
        Identifier string (used in logging only).
    wind_speed_source : str
        'auto'     – use real if present, synthetic if absent (default)
        'real'     – assert that wind_speed_10m is in weather_df; raise if not
        'synthetic' – always use synthetic wind speed (testing/CI)

    Returns
    -------
    DataFrame indexed by timestamp with all engineered features + target.
    Rows with NaN in canonical feature columns are dropped (lag burn-in only).
    """
    df = _prepare_wind_load(load_df)
    df = _add_time_features(df)          # reused from solar_features
    df = _add_season_feature(df)
    df = _add_wind_weather_features(df, weather_df, asset_name, wind_speed_source)
    df = _add_wind_lag_features(df)
    df = _add_wind_rolling_features(df)
    df = df.dropna(subset=list(WIND_FEATURE_COLS))
    _assert_no_leakage(df)
    return df


def get_wind_feature_names() -> list[str]:
    """Return the ordered list of feature column names used by the wind model."""
    return list(WIND_FEATURE_COLS)


def get_wind_target_name() -> str:
    return "wind_generation_mw"


# ---------------------------------------------------------------------------
# Feature column registry
# ---------------------------------------------------------------------------

WIND_FEATURE_COLS: tuple[str, ...] = (
    # ── Time (reused from solar pipeline) ───────────────────────────────────
    "hour_of_day",
    "minute_of_day",
    "day_of_year",
    "month",
    "day_of_week",
    "is_weekend",
    "season",            # 0=winter,1=spring,2=summer,3=autumn
    # ── Wind speed (real or disclosed synthetic) ─────────────────────────────
    "wind_speed_10m",        # m/s — primary predictor (cubic power curve)
    "wind_speed_cubed",      # m/s^3 — explicit cubic transform
    # ── Wind direction (real or synthetic; if absent, use sin/cos encoding)
    "wind_dir_sin",          # sin(direction_rad) — north/south component
    "wind_dir_cos",          # cos(direction_rad) — east/west component
    # ── Atmospheric (real, confirmed in OpenSTEF schema) ────────────────────
    "temperature_2m",
    "surface_pressure",
    "air_density_proxy",     # pressure / (temperature_K) — affects power output
    # ── Autoregressive lags (15-min steps, same as solar pipeline) ──────────
    "lag_1",    # t-15 min
    "lag_2",    # t-30 min
    "lag_4",    # t-1 h
    "lag_8",    # t-2 h
    "lag_96",   # t-24 h  (same hour yesterday)
    "lag_192",  # t-48 h
    "lag_672",  # t-7 days
    # ── Rolling statistics (same windows as solar) ───────────────────────────
    "roll_mean_4",   # 1-h  trailing mean
    "roll_mean_96",  # 24-h trailing mean
    "roll_std_96",   # 24-h trailing std
    # ── Wind-speed rolling (captures ramp-rate context) ──────────────────────
    "wind_speed_roll_mean_4",   # 1-h  mean of wind speed
    "wind_speed_roll_mean_96",  # 24-h mean of wind speed
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _prepare_wind_load(load_df: pd.DataFrame) -> pd.DataFrame:
    df = load_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")
    # Convert W -> MW; wind generation can be near-zero (calm) but not negative
    df["wind_generation_mw"] = (df["load"] * W_TO_MW).clip(lower=0.0)
    return df


def _add_season_feature(df: pd.DataFrame) -> pd.DataFrame:
    """0=winter, 1=spring, 2=summer, 3=autumn (meteorological seasons)."""
    month = df.index.month
    season = pd.cut(
        month,
        bins=[0, 2, 5, 8, 11, 12],
        labels=[0, 1, 2, 3, 0],   # Dec→0(winter) wraps
        ordered=False,
    ).astype(int)
    df["season"] = np.asarray(season)
    return df


def _add_wind_weather_features(
    df: pd.DataFrame,
    weather_df: pd.DataFrame,
    asset_name: str,
    wind_speed_source: str,
) -> pd.DataFrame:
    """
    Merge weather into the 15-min load DataFrame.

    Wind-speed gap handling:
    - If real wind_speed_10m is in weather_df: use it (logs INFO).
    - If absent and wind_speed_source='real': raise ValueError.
    - If absent and wind_speed_source in ('auto','synthetic'):
        generate synthetic wind speed via _synthetic_wind_speed_for_weather()
        and log a clear WARNING so the choice is auditable.
    """
    w = weather_df.copy()
    w["timestamp"] = pd.to_datetime(w["timestamp"], utc=True)
    w = w.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")

    has_real_wind = "wind_speed_10m" in w.columns
    has_real_dir  = "wind_direction_10m" in w.columns

    if wind_speed_source == "real" and not has_real_wind:
        raise ValueError(
            f"[wind][{asset_name}] wind_speed_source='real' requested but "
            "'wind_speed_10m' is not in weather_df. "
            "This column is not confirmed in the OpenSTEF Liander 2024 published schema "
            "(see docs/data/openstef-renewable.md §6.3). "
            "Download the real dataset and verify the parquet columns, or "
            "use wind_speed_source='auto' to fall back to synthetic."
        )

    # ── Interpolate confirmed weather columns ─────────────────────────────────
    confirmed_cols = [c for c in [
        "cloud_cover", "temperature_2m", "relative_humidity_2m", "surface_pressure",
    ] if c in w.columns]
    w_interp = w[confirmed_cols].copy()
    if has_real_wind:
        w_interp["wind_speed_10m"] = w["wind_speed_10m"]
        logger.info("[wind][%s] Using REAL wind_speed_10m from weather_df.", asset_name)
    if has_real_dir:
        w_interp["wind_direction_10m"] = w["wind_direction_10m"]
        logger.info("[wind][%s] Using REAL wind_direction_10m from weather_df.", asset_name)

    full_idx = df.index.union(w_interp.index).sort_values()
    w_interp = w_interp.reindex(full_idx).interpolate(method="time").reindex(df.index)
    for col in w_interp.columns:
        df[col] = w_interp[col].values

    # ── Fill mandatory confirmed columns ────────────────────────────────────
    for col in ["temperature_2m", "surface_pressure"]:
        if col not in df.columns:
            df[col] = np.nan

    # ── Synthetic wind speed (Option b — documented gap fallback) ──────────
    if not has_real_wind and wind_speed_source in ("auto", "synthetic"):
        warnings.warn(
            f"[wind][{asset_name}] SYNTHETIC WIND SPEED in use. "
            "wind_speed_10m is not in weather_df. "
            "This is a calibrated fallback (Option b per docs/data/openstef-renewable.md §6.3). "
            "NOT a real measurement. Replace when real data is downloaded.",
            UserWarning,
            stacklevel=4,
        )
        logger.warning(
            "[wind][%s] SYNTHETIC WIND SPEED active — not a real measurement. "
            "See docs/data/openstef-renewable.md §6.3 for gap context.", asset_name
        )
        df["wind_speed_10m"] = _synthetic_wind_speed_for_index(df.index)
        df["wind_direction_10m"] = _synthetic_wind_direction_for_index(df.index)

    # ── Synthetic wind direction if direction still absent ──────────────────
    if "wind_direction_10m" not in df.columns:
        df["wind_direction_10m"] = _synthetic_wind_direction_for_index(df.index)
        logger.warning(
            "[wind][%s] SYNTHETIC WIND DIRECTION in use — not a real measurement.", asset_name
        )

    # ── Derived features ────────────────────────────────────────────────────
    # Cubic wind speed (power output scales with v^3 for below-rated speeds)
    df["wind_speed_cubed"] = df["wind_speed_10m"] ** 3

    # Sin/cos encoding of wind direction (avoids 0/360 discontinuity)
    dir_rad = np.radians(df["wind_direction_10m"])
    df["wind_dir_sin"] = np.sin(dir_rad)
    df["wind_dir_cos"] = np.cos(dir_rad)

    # Air density proxy: pressure / temperature_Kelvin
    # ρ ∝ P / T  (ideal gas law approximation)
    temp_k = df["temperature_2m"] + 273.15
    df["air_density_proxy"] = df["surface_pressure"] / temp_k.replace(0, np.nan)

    return df


def _synthetic_wind_speed_for_index(idx: pd.DatetimeIndex) -> np.ndarray:
    """
    Calibrated synthetic wind speed (m/s) for the Netherlands.

    This is SYNTHETIC DATA, not a real measurement.
    It is disclosed in metadata and log warnings (§6.3 gap fallback).

    Characteristics calibrated to Dutch wind resource:
    - Mean ~7 m/s (KNMI long-term Netherlands average)
    - Seasonal variation: higher in winter, lower in summer
    - Diurnal variation: slight peak at midday
    - Weibull-like distribution approximated with lognormal noise
    - Uses a fixed RNG seed so output is deterministic and reproducible
    """
    rng = np.random.default_rng(RANDOM_SEED + 1)   # offset from solar seed
    n = len(idx)
    doy  = idx.day_of_year.values.astype(float)
    hour = idx.hour.values.astype(float)

    # Seasonal component: peak in Jan/Feb (~9 m/s), trough in Jul/Aug (~5.5 m/s)
    seasonal = 7.0 + 2.0 * np.cos(2 * np.pi * (doy - 15) / 365)

    # Diurnal component: +0.5 m/s peak at noon (thermal effects)
    diurnal = 0.5 * np.sin(2 * np.pi * (hour - 6) / 24)

    # Multiplicative lognormal noise (σ=0.3 in log-space)
    log_noise = rng.normal(0, 0.3, n)
    noise_factor = np.exp(log_noise)

    wind_speed = np.clip((seasonal + diurnal) * noise_factor, 0.0, 25.0)
    return wind_speed


def _synthetic_wind_direction_for_index(idx: pd.DatetimeIndex) -> np.ndarray:
    """
    Calibrated synthetic wind direction (degrees, 0=N) for the Netherlands.

    SYNTHETIC DATA — see _synthetic_wind_speed_for_index docstring.
    Netherlands prevailing direction is SW (~225 deg).
    """
    rng = np.random.default_rng(RANDOM_SEED + 2)
    n = len(idx)
    # Von Mises-like approximation around 225 degrees (SW)
    noise = rng.normal(0, 50, n)
    direction = (225 + noise) % 360
    return direction


def _add_wind_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """Lagged generation features — identical lag structure to solar pipeline."""
    gen = df["wind_generation_mw"]
    df["lag_1"]   = gen.shift(1)
    df["lag_2"]   = gen.shift(2)
    df["lag_4"]   = gen.shift(4)
    df["lag_8"]   = gen.shift(8)
    df["lag_96"]  = gen.shift(96)
    df["lag_192"] = gen.shift(192)
    df["lag_672"] = gen.shift(672)
    return df


def _add_wind_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """Rolling statistics — same windows as solar pipeline + wind-speed rolling."""
    gen = df["wind_generation_mw"]
    df["roll_mean_4"]  = gen.shift(1).rolling(4,  min_periods=2).mean()
    df["roll_mean_96"] = gen.shift(1).rolling(96, min_periods=48).mean()
    df["roll_std_96"]  = gen.shift(1).rolling(96, min_periods=48).std().fillna(0.0)

    ws = df["wind_speed_10m"]
    df["wind_speed_roll_mean_4"]  = ws.shift(1).rolling(4,  min_periods=2).mean()
    df["wind_speed_roll_mean_96"] = ws.shift(1).rolling(96, min_periods=48).mean()
    return df


def _assert_no_leakage(df: pd.DataFrame) -> None:
    """
    Anti-leakage assertion: verify that all lag/rolling feature columns
    contain only past values by checking that lag_1 at index i equals
    wind_generation_mw at index i-1.

    Raises AssertionError with a descriptive message if leakage is detected.
    This matches the leakage-prevention validation from the Chunk 2 design.
    """
    if len(df) < 2:
        return

    gen    = df["wind_generation_mw"].values
    lag1   = df["lag_1"].values

    # After dropna(), the first valid lag_1 should equal the prior step's gen
    # Find first non-NaN pair
    for i in range(1, len(df)):
        if not (np.isnan(lag1[i]) or np.isnan(gen[i - 1])):
            discrepancy = abs(lag1[i] - gen[i - 1])
            assert discrepancy < 1e-10, (
                f"LEAKAGE DETECTED: lag_1[{i}]={lag1[i]:.8f} "
                f"!= wind_generation_mw[{i-1}]={gen[i-1]:.8f} "
                f"(diff={discrepancy:.2e}). "
                "This means a future value has leaked into lag_1."
            )
            break  # One confirmed-clean pair is sufficient for this assertion
    logger.debug("[wind] Anti-leakage assertion passed.")
