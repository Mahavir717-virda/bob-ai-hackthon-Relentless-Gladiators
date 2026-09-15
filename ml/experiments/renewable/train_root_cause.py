"""Script to train and persist root-cause XGBoost models to disk."""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

import pandas as pd
import numpy as np

from services.renewable.data_loader import (
    generate_synthetic_solar_fixture,
    generate_synthetic_wind_fixture,
)
from services.renewable.solar_model import load_solar_model, predict_solar
from services.renewable.wind_model import load_wind_model, forecast_wind_generation
from services.renewable.solar_features import build_solar_features
from services.renewable.wind_features import build_wind_features
from services.renewable.performance import calculate_performance
from services.renewable.curtailment import classify_deviation
from services.renewable.anomaly_detector import detect_anomalies
from services.renewable.root_cause import train_root_cause_model, _BUNDLES

MODEL_DIR = Path(__file__).resolve().parents[3] / "ml" / "models" / "renewable"
LATITUDE, LONGITUDE = 52.3, 4.9

SOLAR_FEATURE_COLS = [
    "solar_elevation_deg", "cos_solar_zenith", "cloud_cover", "temperature_2m",
    "relative_humidity_2m", "surface_pressure",
    "hour_of_day", "minute_of_day", "day_of_year", "month", "day_of_week",
    "is_weekend", "season",
    "lag_1", "lag_2", "lag_4", "lag_8", "lag_96", "lag_192", "lag_672",
    "roll_mean_4", "roll_mean_96", "roll_std_96",
]

WIND_FEATURE_COLS = [
    "wind_speed_10m", "wind_speed_cubed", "wind_direction_10m",
    "wind_dir_sin", "wind_dir_cos", "air_density_proxy",
    "wind_speed_roll_mean_4", "wind_speed_roll_mean_96",
    "cloud_cover", "temperature_2m", "relative_humidity_2m", "surface_pressure",
    "hour_of_day", "minute_of_day", "day_of_year", "month", "day_of_week",
    "is_weekend", "season",
    "lag_1", "lag_2", "lag_4", "lag_8", "lag_96", "lag_192", "lag_672",
    "roll_mean_4", "roll_mean_96", "roll_std_96",
]


def _build_analysis(asset_id, asset_type, load_df, weather_df, forecast, feature_cols):
    actual = load_df.copy()
    actual["timestamp"] = pd.to_datetime(actual["timestamp"], utc=True)
    actual = actual.set_index("timestamp")["load"].mul(1e-6).rename("actual_mw")
    data = pd.concat([forecast.rename("expected_mw"), actual], axis=1, join="inner").reset_index()
    data = data.rename(columns={data.columns[0]: "timestamp"})
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)

    perf = calculate_performance(asset_id, asset_type, data["timestamp"], data["expected_mw"], data["actual_mw"])
    diag = classify_deviation(perf, weather_df)
    detected = detect_anomalies(perf, diag, weather_df)
    detected["asset_id"] = asset_id
    detected["asset_type"] = asset_type
    return detected


def main():
    print("=== Training root-cause models ===")

    # --- Solar ---
    print("\n[1] Generating solar fixture + building solar detected frame...")
    solar_load, solar_weather = generate_synthetic_solar_fixture(n_days=365, seed=42)
    solar_model = load_solar_model(MODEL_DIR / "solar_lgbm_solar_park_synth_01.pkl")
    solar_forecast = predict_solar(solar_model, solar_load, solar_weather, LATITUDE, LONGITUDE, "solar_park_synth_01")
    solar_detected = _build_analysis("solar_park_synth_01", "solar", solar_load, solar_weather, solar_forecast, SOLAR_FEATURE_COLS)
    n_solar_anomalies = int(solar_detected["anomaly"].sum())
    print(f"   solar rows: {len(solar_detected)}, anomalies: {n_solar_anomalies}")

    # Merge solar feature columns
    solar_features_df = build_solar_features(solar_load, solar_weather, LATITUDE, LONGITUDE, "solar_park_synth_01")
    solar_features_df = solar_features_df.reset_index()
    solar_analysis = solar_detected.copy()
    solar_analysis["timestamp"] = pd.to_datetime(solar_analysis["timestamp"], utc=True)
    for col in SOLAR_FEATURE_COLS:
        if col in solar_features_df.columns:
            solar_analysis = solar_analysis.merge(
                solar_features_df[["timestamp", col]], on="timestamp", how="left", suffixes=("", "_feat")
            )

    # --- Wind ---
    print("\n[2] Generating wind fixture + building wind detected frame...")
    wind_load, wind_weather = generate_synthetic_wind_fixture(n_days=365, seed=52)
    wind_model = load_wind_model(MODEL_DIR / "wind_lgbm_wind_park_synth_01.pkl")
    wind_forecast = forecast_wind_generation(wind_model, wind_load, wind_weather, "wind_park_synth_01", wind_speed_source="real")
    wind_detected = _build_analysis("wind_park_synth_01", "wind", wind_load, wind_weather, wind_forecast, WIND_FEATURE_COLS)
    n_wind_anomalies = int(wind_detected["anomaly"].sum())
    print(f"   wind rows: {len(wind_detected)}, anomalies: {n_wind_anomalies}")

    # Merge wind feature columns
    wind_features_df = build_wind_features(wind_load, wind_weather, "wind_park_synth_01", wind_speed_source="auto")
    wind_features_df = wind_features_df.reset_index()
    wind_analysis = wind_detected.copy()
    wind_analysis["timestamp"] = pd.to_datetime(wind_analysis["timestamp"], utc=True)
    for col in WIND_FEATURE_COLS:
        if col in wind_features_df.columns:
            wind_analysis = wind_analysis.merge(
                wind_features_df[["timestamp", col]], on="timestamp", how="left", suffixes=("", "_feat")
            )

    analysis_df = pd.concat([solar_analysis, wind_analysis], ignore_index=True)
    print(f"\n[3] Combined analysis_df: {len(analysis_df)} rows, columns={len(analysis_df.columns)}")

    # --- Train solar root-cause ---
    print("\n[4] Training solar root-cause model (auto-saves to ml/models/renewable/)...")
    solar_rc = train_root_cause_model(analysis_df, "solar")
    m = solar_rc["metrics"]
    print(f"   Solar  MAE={m['mae_percentage_points']:.3f} pp   RMSE={m['rmse_percentage_points']:.3f} pp")
    print(f"   saved model:    {solar_rc.get('model_path', 'NOT SAVED')}")
    print(f"   saved metadata: {solar_rc.get('metadata_path', 'NOT SAVED')}")
    print(f"   saved rows:     {solar_rc.get('rows_path', 'NOT SAVED')}")

    # --- Train wind root-cause ---
    print("\n[5] Training wind root-cause model...")
    wind_rc = train_root_cause_model(analysis_df, "wind")
    m = wind_rc["metrics"]
    print(f"   Wind   MAE={m['mae_percentage_points']:.3f} pp   RMSE={m['rmse_percentage_points']:.3f} pp")
    print(f"   saved model:    {wind_rc.get('model_path', 'NOT SAVED')}")
    print(f"   saved metadata: {wind_rc.get('metadata_path', 'NOT SAVED')}")
    print(f"   saved rows:     {wind_rc.get('rows_path', 'NOT SAVED')}")

    print(f"\n[6] _BUNDLES registered: {list(_BUNDLES.keys())}")


if __name__ == "__main__":
    main()
