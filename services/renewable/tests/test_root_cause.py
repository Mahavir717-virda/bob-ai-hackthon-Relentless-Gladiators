from pathlib import Path

import numpy as np
import pandas as pd

from services.renewable.root_cause import analyzeRootCause, train_root_cause_model


def _rows(asset_type, asset_id, signal, diagnostic="uncertain", anomaly=False):
    n = len(signal)
    timestamps = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    data = {
        "asset_id": [asset_id] * n, "asset_type": [asset_type] * n, "timestamp": timestamps,
        "percentage_deviation": signal, "diagnostic_category": [diagnostic] * n, "anomaly": [anomaly] * n,
        "cloud_cover": np.linspace(0, 100, n), "temperature_2m": np.full(n, 12.0),
        "relative_humidity_2m": np.full(n, 70.0), "hour_of_day": timestamps.hour,
        "day_of_week": timestamps.dayofweek, "season": np.full(n, 0), "lag_1": np.r_[0.0, signal[:-1]],
        "roll_mean_4": pd.Series(signal).rolling(4, min_periods=1).mean(),
    }
    if asset_type == "solar":
        data.update(solar_elevation_deg=np.linspace(10, 50, n), cos_solar_zenith=np.linspace(.2, .8, n))
    else:
        data.update(wind_speed_10m=np.linspace(2, 16, n), wind_speed_cubed=np.linspace(2, 16, n) ** 3, wind_dir_sin=np.zeros(n), wind_dir_cos=np.ones(n))
    return pd.DataFrame(data)


def test_cloud_association_for_solar():
    signal = -np.linspace(0, 100, 60)
    df = _rows("solar", "solar-a", signal, "weather_driven_reduction")
    train_root_cause_model(df, "solar")
    result = analyzeRootCause("solar-a", df.iloc[-1].timestamp)
    assert result["category"] == "weather_cloud_cover"
    assert result["confidence"] > 0.2


def test_wind_speed_association_for_wind():
    speed = np.array(([3.0, 14.0, 6.0, 12.0, 8.0, 16.0] * 10))
    signal = -speed * 6.0
    df = _rows("wind", "wind-a", signal)
    df["cloud_cover"] = 50.0
    df["wind_speed_10m"] = speed
    df["wind_speed_cubed"] = speed ** 3
    df["lag_1"] = 0.0
    df["roll_mean_4"] = 0.0
    train_root_cause_model(df, "wind")
    result = analyzeRootCause("wind-a", df.iloc[-1].timestamp)
    assert result["category"] == "weather_wind_speed"


def test_persistent_pattern_not_attributed_to_weather():
    signal = np.r_[np.zeros(20), np.full(40, -50.0)]
    df = _rows("solar", "solar-pattern", signal, "normal_production", anomaly=False)
    df.loc[20:, "diagnostic_category"] = "possible_physical_fault"
    df.loc[20:, "anomaly"] = True
    df["cloud_cover"] = 20.0
    df[["hour_of_day", "day_of_week", "season", "solar_elevation_deg", "cos_solar_zenith"]] = 0.0
    train_root_cause_model(df, "solar")
    result = analyzeRootCause("solar-pattern", df.iloc[-1].timestamp)
    assert result["category"] in {"persistent_pattern", "unexplained_anomaly"}


def test_negligible_deviation_is_uncertain():
    df = _rows("solar", "solar-normal", np.full(60, 1.0), "normal_production")
    train_root_cause_model(df, "solar")
    result = analyzeRootCause("solar-normal", df.iloc[-1].timestamp)
    assert result["category"] == "uncertain"
    assert result["confidence"] == 0.0


def test_missing_history_is_uncertain():
    result = analyzeRootCause("missing-asset", "2026-01-01T00:00:00Z")
    assert result["category"] == "uncertain"
    assert result["confidence"] == 0.0
    assert "No registered model history" in result["evidence"]["reason"]


def test_module_avoids_causal_language():
    source = Path(__file__).parents[1].joinpath("root_cause.py").read_text(encoding="utf-8").lower()
    for prohibited in ("caused", "due to", "resulted from"):
        assert prohibited not in source
