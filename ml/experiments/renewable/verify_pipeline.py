#!/usr/bin/env python3
"""Local smoke test for the synthetic renewable intelligence pipeline."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.renewable.anomaly_detector import detect_anomalies
from services.renewable.curtailment import classify_deviation
from services.renewable.data_loader import (
    generate_synthetic_solar_fixture,
    generate_synthetic_wind_fixture,
)
from services.renewable.performance import calculate_performance
from services.renewable.renewable_service import (
    _pipeline,
    _root_cause_analysis,
    analyzeRootCause,
    detectAnomalies,
    getRenewableStatus,
)
from services.renewable.solar_model import load_solar_model, predict_solar
from services.renewable.wind_model import forecast_wind_generation, load_wind_model


MODEL_DIR = PROJECT_ROOT / "ml" / "models" / "renewable"
LATITUDE = 52.3
LONGITUDE = 4.9
ASSET_IDS = {"solar": "solar_park_synth_01", "wind": "wind_park_synth_01"}
WINDOW_START = pd.Timestamp("2024-06-01 00:00:00+00:00")
WINDOW_END = WINDOW_START + pd.Timedelta(hours=48) - pd.Timedelta(minutes=15)
SAMPLE_COUNT = 10


def _print_frame(title: str, frame: pd.DataFrame, columns: list[str]) -> None:
    print(f"\n{title}")
    print(frame.loc[:, columns].to_string(index=False))


def _sample_indices(frame: pd.DataFrame) -> list[int]:
    if len(frame) < SAMPLE_COUNT:
        return list(range(len(frame)))
    return np.linspace(0, len(frame) - 1, SAMPLE_COUNT, dtype=int).tolist()


def _metadata_report(asset_type: str) -> tuple[Path, Path, dict]:
    prefix = f"{asset_type}_lgbm_{ASSET_IDS[asset_type]}"
    model_path = MODEL_DIR / f"{prefix}.pkl"
    metadata_path = MODEL_DIR / f"{prefix}_metadata.json"
    print(f"\n[{asset_type.upper()} MODEL ARTIFACTS]")
    print(f"model: {model_path} | exists={model_path.exists()}")
    print(f"metadata: {metadata_path} | exists={metadata_path.exists()}")
    if not model_path.exists() or not metadata_path.exists():
        raise FileNotFoundError(f"Missing model artifact or metadata for {asset_type}: {model_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    print(f"version: {metadata['version']}")
    print(f"training window: {metadata['train_period']}")
    print(f"validation window: {metadata['val_period']}")
    print(f"validation metrics: {metadata['validation_metrics']}")
    return model_path, metadata_path, metadata


def _build_asset_pipeline(asset_type: str, load_df: pd.DataFrame, weather_df: pd.DataFrame, model_path: Path) -> dict:
    asset_id = ASSET_IDS[asset_type]
    if asset_type == "solar":
        model = load_solar_model(model_path)
        print(f"{asset_type.upper()} model load: success ({type(model).__name__})")
        forecast = predict_solar(model, load_df, weather_df, LATITUDE, LONGITUDE, asset_id)
    else:
        model = load_wind_model(model_path)
        print(f"{asset_type.upper()} model load: success ({type(model).__name__})")
        forecast = forecast_wind_generation(model, load_df, weather_df, asset_id, wind_speed_source="real")

    actual = load_df.copy()
    actual["timestamp"] = pd.to_datetime(actual["timestamp"], utc=True)
    actual = actual.set_index("timestamp")["load"].mul(1e-6).rename("actual_mw")
    frame = pd.concat([forecast.rename("expected_mw"), actual], axis=1, join="inner").reset_index()
    frame = frame.rename(columns={frame.columns[0]: "timestamp"})
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.loc[frame["timestamp"].between(WINDOW_START, WINDOW_END)].reset_index(drop=True)
    if len(frame) != 192:
        raise ValueError(f"Expected 192 rows in the 48-hour {asset_type} window, got {len(frame)}")
    return {"asset_id": asset_id, "asset_type": asset_type, "forecast_frame": frame, "weather": weather_df}


def _run_internal(asset: dict) -> None:
    frame = asset["forecast_frame"]
    asset_id = asset["asset_id"]
    asset_type = asset["asset_type"]
    performance = calculate_performance(
        asset_id,
        asset_type,
        frame["timestamp"],
        frame["expected_mw"],
        frame["actual_mw"],
    )
    diagnostics = classify_deviation(performance, asset["weather"])
    detected = detect_anomalies(performance, diagnostics, asset["weather"])
    asset["performance"] = performance
    asset["diagnostics"] = diagnostics
    asset["detected"] = detected

    sample = _sample_indices(detected)
    _print_frame(
        f"[{asset_type.upper()} FORECAST SAMPLE]",
        frame.iloc[sample],
        ["timestamp", "expected_mw"],
    )
    _print_frame(
        f"[{asset_type.upper()} PERFORMANCE SAMPLE]",
        performance.iloc[sample],
        ["timestamp", "expected_mw", "actual_mw", "performance_ratio", "zero_expected_edge_case"],
    )
    diagnostic_sample = diagnostics.iloc[sample].copy()
    _print_frame(
        f"[{asset_type.upper()} DIAGNOSTIC SAMPLE]",
        diagnostic_sample,
        ["timestamp", "diagnostic_category", "diagnostic_confidence"],
    )
    _print_frame(
        f"[{asset_type.upper()} ANOMALY SAMPLE]",
        detected.iloc[sample],
        ["timestamp", "anomaly_score", "anomaly", "anomaly_suppressed_reason"],
    )
    anomaly_rows = detected.loc[detected["anomaly"]].copy()
    print(f"[{asset_type.upper()} ANOMALIES] {len(anomaly_rows)} flagged out of {len(detected)} rows")
    for row in anomaly_rows.itertuples(index=False):
        result = _root_cause_analysis(asset_id, row.timestamp)
        print(
            f"root cause: timestamp={row.timestamp.isoformat()} "
            f"category={result['category']} confidence={result['confidence']}"
        )


def _service_checks(assets: dict[str, dict]) -> list[str]:
    mismatches: list[str] = []
    print("\n[PUBLIC SERVICE CHECKS]")
    for asset_type, asset in assets.items():
        asset_id = asset["asset_id"]
        detected = asset["detected"]
        sample = _sample_indices(detected)
        print(f"\n{asset_type.upper()} getRenewableStatus outputs:")
        for index in sample:
            timestamp = detected.iloc[index]["timestamp"]
            public_status = getRenewableStatus(asset_id, timestamp)
            internal = detected.iloc[index]
            print(json.dumps(public_status, sort_keys=True, default=str))
            expected_ratio = internal["performance_ratio"]
            public_ratio = public_status["performanceRatio"]
            ratios_match = (
                pd.isna(expected_ratio) and public_ratio is None
            ) or (
                not pd.isna(expected_ratio) and np.isclose(float(expected_ratio), float(public_ratio))
            )
            fields_match = (
                public_status["expectedMw"] == float(internal["expected_mw"])
                and public_status["actualMw"] == float(internal["actual_mw"])
                and public_status["anomaly"] == bool(internal["anomaly"])
                and ratios_match
            )
            if not fields_match:
                mismatches.append(
                    f"{asset_id} {timestamp.isoformat()}: internal anomaly={bool(internal['anomaly'])}, "
                    f"public anomaly={public_status['anomaly']}; "
                    f"internal ratio={expected_ratio}, public ratio={public_ratio}"
                )

        public_anomalies = detectAnomalies({
            "asset_id": asset_id,
            "start": WINDOW_START,
            "end": WINDOW_END,
        })
        print(f"{asset_type.upper()} detectAnomalies output ({len(public_anomalies)} rows):")
        for result in public_anomalies:
            print(json.dumps(result, sort_keys=True, default=str))
        internal_count = int(detected["anomaly"].sum())
        if len(public_anomalies) != internal_count:
            mismatches.append(
                f"{asset_id}: internal anomaly count={internal_count}, public count={len(public_anomalies)}"
            )

        print(f"{asset_type.upper()} analyzeRootCause outputs:")
        for result in public_anomalies:
            root_result = analyzeRootCause(asset_id, result["timestamp"])
            print(json.dumps(root_result, sort_keys=True, default=str))
    return mismatches


def main() -> None:
    issues: list[str] = []
    exceptions: list[str] = []
    total_rows = 0
    total_anomalies = 0
    assets: dict[str, dict] = {}
    try:
        print("GRIDPILOT RENEWABLE SYNTHETIC PIPELINE VERIFICATION")
        print(f"project root: {PROJECT_ROOT}")
        print(f"window: {WINDOW_START.isoformat()} through {WINDOW_END.isoformat()} (192 rows per asset)")

        artifacts = {asset_type: _metadata_report(asset_type) for asset_type in ASSET_IDS}

        print("\n[SYNTHETIC FIXTURE GENERATION]")
        # Full-year history is required for the trained 672-step lag features;
        # only the deterministic 48-hour verification window is processed below.
        solar_load, solar_weather = generate_synthetic_solar_fixture(n_days=365, seed=42)
        wind_load, wind_weather = generate_synthetic_wind_fixture(n_days=365, seed=52)
        print(f"solar source rows: {len(solar_load)} load / {len(solar_weather)} weather")
        print(f"wind source rows: {len(wind_load)} load / {len(wind_weather)} weather")
        print("feature history retained: 672 prior 15-minute steps")

        assets["solar"] = _build_asset_pipeline("solar", solar_load, solar_weather, artifacts["solar"][0])
        assets["wind"] = _build_asset_pipeline("wind", wind_load, wind_weather, artifacts["wind"][0])
        for asset in assets.values():
            _run_internal(asset)
            total_rows += len(asset["detected"])
            total_anomalies += int(asset["detected"]["anomaly"].sum())

        issues.extend(_service_checks(assets))

        print("\n[PUBLIC NIGHT/CALM EDGE CASE]")
        solar = assets["solar"]
        night_index = int(solar["forecast_frame"]["expected_mw"].abs().idxmin())
        night_timestamp = solar["forecast_frame"].iloc[night_index]["timestamp"]
        night_status = getRenewableStatus(solar["asset_id"], night_timestamp)
        print(json.dumps(night_status, indent=2, sort_keys=True, default=str))
        if night_status["performanceRatio"] is None or not isinstance(night_status["anomaly"], bool):
            issues.append("night/calm public status has an invalid ratio or anomaly value")
        else:
            print("night/calm status check: performanceRatio is finite and anomaly is boolean")
    except Exception:
        details = traceback.format_exc()
        exceptions.append(details)
        print("\n[EXCEPTION: PIPELINE STOPPED]")
        print(details)

    print("\nFINAL SUMMARY")
    print(f"total rows processed: {total_rows}")
    anomaly_percent = (100.0 * total_anomalies / total_rows) if total_rows else 0.0
    print(f"total anomalies detected: {total_anomalies} ({anomaly_percent:.2f}%)")
    print(f"internal/public mismatches: {issues if issues else 'none'}")
    print(f"exceptions: {'present' if exceptions else 'none'}")
    if exceptions:
        print("overall verdict: PIPELINE_HAS_ISSUES")
        print("issues: exception raised; see full traceback above")
    elif issues:
        print("overall verdict: PIPELINE_HAS_ISSUES")
        print(f"issues: {issues}")
    else:
        print("overall verdict: PIPELINE_HEALTHY")


if __name__ == "__main__":
    main()