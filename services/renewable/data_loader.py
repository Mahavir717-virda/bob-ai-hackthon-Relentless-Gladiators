"""
services/renewable/data_loader.py
====================================
Utilities for loading OpenSTEF Liander 2024 data and generating
deterministic synthetic fixtures when real data is absent.

The synthetic fixture is calibrated to mirror real OpenSTEF distributions:
- 15-minute UTC timestamps over a full calendar year
- Realistic Dutch solar generation profile (seasonal + diurnal)
- Realistic weather variables (cloud_cover, temperature, humidity, pressure)
- Unit: Watts (as the real dataset delivers)

RULE: This module NEVER modifies source data.  Read-only or generate-only.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .constants import RANDOM_SEED

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Real data loader (OpenSTEF Liander 2024 parquet files)
# ---------------------------------------------------------------------------

def _dataset_file(dataset_dir: str | Path, folder: str, asset_name: str) -> Path:
    """Resolve a dataset asset in either flat or type-partitioned layouts."""
    root = Path(dataset_dir) / folder
    flat_path = root / f"{asset_name}.parquet"
    if flat_path.exists():
        return flat_path
    matches = list(root.rglob(f"{asset_name}.parquet")) if root.exists() else []
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Multiple {folder} files found for asset {asset_name!r}: {matches}")
    raise FileNotFoundError(f"{folder} file not found for asset {asset_name!r} under {root}")


def _ensure_timestamp_column(df: pd.DataFrame) -> pd.DataFrame:
    """Expose parquet index timestamps as the standard timestamp column."""
    result = df.reset_index() if "timestamp" not in df.columns else df.copy()
    if "timestamp" not in result.columns:
        raise ValueError("Dataset file has no timestamp column or DatetimeIndex")
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    return result

def load_openstef_load(
    dataset_dir: str | Path,
    asset_name: str,
) -> pd.DataFrame:
    """
    Load a single asset's load measurements from the Liander 2024 dataset.

    Parameters
    ----------
    dataset_dir : Path to the downloaded dataset root
        (e.g. ml/datasets/liander2024)
    asset_name : str  – matches filename under load_measurements/

    Returns
    -------
    DataFrame with columns ['timestamp', 'load', 'available_at']
    Raises FileNotFoundError if the dataset has not been downloaded.
    """
    try:
        path = _dataset_file(dataset_dir, "load_measurements", asset_name)
    except (FileNotFoundError, ValueError):
        raise FileNotFoundError(
            f"Load measurements not found for asset: {asset_name!r}\n"
            "Download the dataset first:\n"
            "  from huggingface_hub import snapshot_download\n"
            "  snapshot_download('OpenSTEF/liander2024-energy-forecasting-benchmark',\n"
            "                    repo_type='dataset', local_dir='ml/datasets/liander2024')"
        )
    df = pd.read_parquet(path)
    # Normalise timestamp column name
    if "datetime" in df.columns and "timestamp" not in df.columns:
        df = df.rename(columns={"datetime": "timestamp"})
    df = _ensure_timestamp_column(df)
    logger.info("Loaded %d rows from %s", len(df), path)
    return df


def load_openstef_weather(
    dataset_dir: str | Path,
    asset_name: str,
    versioned: bool = False,
) -> pd.DataFrame:
    """
    Load weather measurements or versioned forecasts for a given asset.

    Parameters
    ----------
    versioned : bool  – if True, load weather_forecasts_versioned (for
        realistic back-testing without look-ahead bias).
    """
    folder = "weather_forecasts_versioned" if versioned else "weather_measurements"
    path = _dataset_file(dataset_dir, folder, asset_name)
    df = pd.read_parquet(path)
    if "datetime" in df.columns and "timestamp" not in df.columns:
        df = df.rename(columns={"datetime": "timestamp"})
    df = _ensure_timestamp_column(df)
    logger.info("Loaded weather %d rows from %s", len(df), path)
    return df


def list_solar_assets(dataset_dir: str | Path) -> list[str]:
    """Return asset names with group_name == 'solar_park' from targets YAML."""
    import yaml
    path = Path(dataset_dir) / "liander2024_targets.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Targets YAML not found: {path}")
    with open(path, encoding="utf-8") as f:
        targets = yaml.safe_load(f)
    return [t["name"] for t in targets if t.get("group_name") == "solar_park"]


# ---------------------------------------------------------------------------
# Synthetic fixture generator
# ---------------------------------------------------------------------------

def generate_synthetic_solar_fixture(
    n_days: int = 365,
    freq_minutes: int = 15,
    lat: float = 52.3,   # Amsterdam, Netherlands
    lon: float = 4.9,
    peak_capacity_w: float = 5_000_000,   # 5 MW nameplate
    seed: int = RANDOM_SEED,
    start_date: str = "2024-01-01",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate a deterministic synthetic solar + weather fixture that mirrors
    OpenSTEF Liander 2024 data characteristics.

    Returns
    -------
    (load_df, weather_df)
    load_df   : columns ['timestamp', 'load']  (Watts, UTC, 15-min)
    weather_df: columns ['timestamp', 'cloud_cover', 'temperature_2m',
                         'relative_humidity_2m', 'surface_pressure']  (hourly, UTC)
    """
    rng = np.random.default_rng(seed)
    n_steps = n_days * (24 * 60 // freq_minutes)
    timestamps = pd.date_range(start_date, periods=n_steps, freq=f"{freq_minutes}min", tz="UTC")

    # ── Astronomical signal ───────────────────────────────────────────────────
    doy    = timestamps.day_of_year.values          # 1-366
    hour   = timestamps.hour.values
    minute = timestamps.minute.values

    # Declination (Spencer)
    B_rad  = np.radians((360 / 365) * (doy - 81))
    decl   = np.radians(23.45 * np.sin(B_rad))
    lat_r  = np.radians(lat)

    eot = 9.87 * np.sin(2 * B_rad) - 7.53 * np.cos(B_rad) - 1.5 * np.sin(B_rad)
    solar_min = (hour * 60 + minute) + (lon / 15 * 60) + eot
    hour_angle = np.radians((solar_min / 4) - 180)

    sin_elev = (
        np.sin(lat_r) * np.sin(decl)
        + np.cos(lat_r) * np.cos(decl) * np.cos(hour_angle)
    )
    sin_elev = np.clip(sin_elev, 0.0, None)   # night = 0

    # ── Cloud cover: seasonal + random (hourly blocks) ────────────────────────
    n_hours = n_days * 24
    cloud_hourly = 40 + 20 * np.sin(np.linspace(0, 2 * np.pi, n_hours))
    cloud_hourly += rng.normal(0, 15, n_hours)
    cloud_hourly = np.clip(cloud_hourly, 0, 100)
    # Repeat each hour value for 4 x 15-min slots
    cloud_15min = np.repeat(cloud_hourly, 24 * 60 // freq_minutes // 24)[:n_steps]

    # ── Solar output (W) ─────────────────────────────────────────────────────
    # GHI proxy: clear-sky * (1 - cloud_fraction)
    cloud_fraction = cloud_15min / 100.0
    ghi_proxy      = sin_elev * (1 - 0.75 * cloud_fraction)
    # Panel efficiency: drops with temperature (modelled below)
    # Add sensor noise (1%)
    noise = rng.normal(1.0, 0.01, n_steps)
    load_w = peak_capacity_w * ghi_proxy * noise
    load_w = np.clip(load_w, 0, peak_capacity_w * 1.05)

    # ── Weather variables ─────────────────────────────────────────────────────
    hour_arr = np.arange(n_hours)
    day_arr  = hour_arr // 24
    # Temperature: seasonal + diurnal
    temp = (
        10
        + 8  * np.sin(2 * np.pi * day_arr / 365 - np.pi / 2)   # seasonal
        + 4  * np.sin(2 * np.pi * (hour_arr % 24) / 24 - np.pi) # diurnal
        + rng.normal(0, 0.5, n_hours)
    )
    humidity = 75 - 0.3 * temp + rng.normal(0, 5, n_hours)
    humidity = np.clip(humidity, 20, 100)
    pressure = 1013 + rng.normal(0, 5, n_hours)

    # Build hourly weather DF
    weather_timestamps = pd.date_range(start_date, periods=n_hours, freq="1h", tz="UTC")
    weather_df = pd.DataFrame({
        "timestamp": weather_timestamps,
        "cloud_cover": cloud_hourly,
        "temperature_2m": temp,
        "relative_humidity_2m": humidity,
        "surface_pressure": pressure,
    })

    load_df = pd.DataFrame({
        "timestamp": timestamps,
        "load": load_w,
    })

    logger.info(
        "Generated synthetic solar fixture: %d rows, peak %.1f MW, lat=%.2f lon=%.2f",
        n_steps, peak_capacity_w * 1e-6, lat, lon,
    )
    return load_df, weather_df


def list_wind_assets(dataset_dir: str | Path) -> list[str]:
    """Return asset names with group_name == 'wind_park' from targets YAML."""
    import yaml
    path = Path(dataset_dir) / "liander2024_targets.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Targets YAML not found: {path}")
    with open(path, encoding="utf-8") as f:
        targets = yaml.safe_load(f)
    return [t["name"] for t in targets if t.get("group_name") == "wind_park"]


def generate_synthetic_wind_fixture(
    n_days: int = 365,
    freq_minutes: int = 15,
    rated_capacity_w: float = 10_000_000,   # 10 MW nameplate
    seed: int = RANDOM_SEED + 10,
    start_date: str = "2024-01-01",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate a deterministic synthetic wind generation + weather fixture
    calibrated to Dutch onshore wind conditions and OpenSTEF formats.

    WIND-SPEED GAP DISCLOSURE (M3 Chunk 1 §6.3):
    Real OpenSTEF weather_measurements schema does not confirm wind speed.
    This function generates a calibrated synthetic weather DataFrame that
    explicitly includes 'wind_speed_10m' and 'wind_direction_10m' columns
    alongside confirmed columns (cloud_cover, temperature_2m, relative_humidity_2m,
    surface_pressure).

    Characteristics:
    - 15-minute generation series (Watts) generated via a standard turbine power curve:
        * Cut-in speed: 3.0 m/s (0 W below)
        * Rated speed: 12.0 m/s (rated capacity between 12 and 25 m/s)
        * Cut-out speed: 25.0 m/s (0 W above)
        * Cubic interpolation between cut-in and rated: P = P_rated * ((v - v_in) / (v_rated - v_in))^3
    - Hourly weather DataFrame (UTC timestamps) matching OpenSTEF weather format.

    Returns
    -------
    (load_df, weather_df)
    load_df    : columns ['timestamp', 'load']  (Watts, UTC, 15-min)
    weather_df : columns ['timestamp', 'cloud_cover', 'temperature_2m',
                          'relative_humidity_2m', 'surface_pressure',
                          'wind_speed_10m', 'wind_direction_10m']  (hourly, UTC)
    """
    rng = np.random.default_rng(seed)
    n_steps = n_days * (24 * 60 // freq_minutes)
    n_hours = n_days * 24
    timestamps = pd.date_range(start_date, periods=n_steps, freq=f"{freq_minutes}min", tz="UTC")
    weather_timestamps = pd.date_range(start_date, periods=n_hours, freq="1h", tz="UTC")

    # ── Hourly wind speed & direction ─────────────────────────────────────────
    hour_arr = np.arange(n_hours)
    day_arr = hour_arr // 24
    doy = (day_arr % 365) + 1

    # Seasonal variation: higher in winter, lower in summer (KNMI Netherlands pattern)
    seasonal_ws = 7.0 + 2.0 * np.cos(2 * np.pi * (doy - 15) / 365)
    diurnal_ws = 0.5 * np.sin(2 * np.pi * (hour_arr % 24 - 6) / 24)
    # Lognormal / Weibull-like distribution noise
    log_noise = rng.normal(0, 0.28, n_hours)
    hourly_ws = np.clip((seasonal_ws + diurnal_ws) * np.exp(log_noise), 0.0, 26.0)

    # Prevailing SW wind (~225 deg) with variation
    hourly_wd = (225.0 + rng.normal(0, 45, n_hours)) % 360.0

    # ── Atmospheric weather variables ─────────────────────────────────────────
    temp = (
        10.0
        + 8.0 * np.sin(2 * np.pi * day_arr / 365 - np.pi / 2)
        + 4.0 * np.sin(2 * np.pi * (hour_arr % 24) / 24 - np.pi)
        + rng.normal(0, 0.5, n_hours)
    )
    humidity = np.clip(75.0 - 0.3 * temp + rng.normal(0, 5, n_hours), 20.0, 100.0)
    pressure = 1013.0 + rng.normal(0, 6, n_hours)
    cloud = np.clip(50.0 + 20.0 * np.sin(2 * np.pi * day_arr / 365) + rng.normal(0, 15, n_hours), 0.0, 100.0)

    weather_df = pd.DataFrame({
        "timestamp": weather_timestamps,
        "cloud_cover": cloud,
        "temperature_2m": temp,
        "relative_humidity_2m": humidity,
        "surface_pressure": pressure,
        "wind_speed_10m": hourly_ws,
        "wind_direction_10m": hourly_wd,
    })

    # ── 15-minute wind generation (Watts) from turbine power curve ───────────
    ws_15min_interp = np.repeat(hourly_ws, 24 * 60 // freq_minutes // 24)[:n_steps]
    gust_noise = rng.normal(1.0, 0.04, n_steps)
    ws_15min = np.clip(ws_15min_interp * gust_noise, 0.0, 30.0)

    v_in = 3.0
    v_rated = 12.0
    v_out = 25.0

    power_fraction = np.zeros(n_steps, dtype=float)
    ramp_mask = (ws_15min >= v_in) & (ws_15min < v_rated)
    power_fraction[ramp_mask] = ((ws_15min[ramp_mask] - v_in) / (v_rated - v_in)) ** 3
    rated_mask = (ws_15min >= v_rated) & (ws_15min <= v_out)
    power_fraction[rated_mask] = 1.0

    sensor_noise = rng.normal(1.0, 0.015, n_steps)
    load_w = np.clip(rated_capacity_w * power_fraction * sensor_noise, 0.0, rated_capacity_w * 1.02)

    load_df = pd.DataFrame({
        "timestamp": timestamps,
        "load": load_w,
    })

    logger.info(
        "Generated synthetic wind fixture: %d rows, rated %.1f MW",
        n_steps, rated_capacity_w * 1e-6,
    )
    return load_df, weather_df

