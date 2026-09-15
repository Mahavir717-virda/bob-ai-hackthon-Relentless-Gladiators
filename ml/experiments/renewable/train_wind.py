#!/usr/bin/env python3
"""
ml/experiments/renewable/train_wind.py
========================================
M3 Chunk 3 — Wind Generation Forecasting Experiment

This script:
1. Loads (or generates synthetic) wind generation + weather data.
2. Performs Step 0 check and logs wind speed source status (real vs synthetic fallback).
3. Engineers features via wind_features.build_wind_features().
4. Verifies anti-leakage property.
5. Trains a LightGBM model with chronological train/val split.
6. Reports MAE, RMSE, MAPE on the held-out validation window.
7. Saves the trained model and metadata JSON to ml/models/renewable/.

Usage
-----
    # With real data (after downloading liander2024 dataset):
    python ml/experiments/renewable/train_wind.py \\
        --dataset-dir ml/datasets/liander2024 \\
        --asset-name <wind_park_name> \\
        --output-dir ml/models/renewable

    # Without real data (runs on synthetic fixture — default):
    python ml/experiments/renewable/train_wind.py

RULE (Rule A): This script trains a prediction model only.
It never makes dispatch decisions.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running from project root or from this directory
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from services.renewable.data_loader import (
    generate_synthetic_wind_fixture,
    load_openstef_load,
    load_openstef_weather,
)
from services.renewable.wind_model import train_wind_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train LightGBM wind forecaster (M3 Chunk 3)")
    p.add_argument("--dataset-dir", default=None,
                   help="Path to liander2024 dataset root. If omitted, synthetic fixture is used.")
    p.add_argument("--asset-name", default="wind_park_synth_01",
                   help="Wind park asset name / filename stem in load_measurements/")
    p.add_argument("--output-dir", default="ml/models/renewable",
                   help="Directory for model artefacts")
    p.add_argument("--n-days", type=int, default=365,
                   help="Days of synthetic data (ignored if --dataset-dir provided)")
    p.add_argument("--rated-capacity-mw", type=float, default=10.0,
                   help="Nameplate capacity in MW for synthetic fixture (default: 10.0)")
    p.add_argument("--wind-speed-source", default="auto", choices=["auto", "real", "synthetic"],
                   help="Source mode for wind speed: auto (real if present, else synthetic), real, or synthetic")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)

    # ── Step 0: Check data source & wind speed availability ──────────────────
    print("=" * 70)
    print("  M3 Chunk 3 — Step 0: Wind-Speed Gap Verification")
    print("=" * 70)

    if args.dataset_dir is not None:
        logger.info("Loading REAL data from %s / asset=%s", args.dataset_dir, args.asset_name)
        load_df = load_openstef_load(args.dataset_dir, args.asset_name)
        weather_df = load_openstef_weather(args.dataset_dir, args.asset_name, versioned=False)
        has_real_ws = "wind_speed_10m" in weather_df.columns
        print(f"  Dataset dir       : {args.dataset_dir}")
        print(f"  Asset name        : {args.asset_name}")
        print(f"  weather columns   : {list(weather_df.columns)}")
        print(f"  Real wind speed   : {'PRESENT' if has_real_ws else 'ABSENT'}")
        if not has_real_ws:
            print("  GAP DETECTED      : 'wind_speed_10m' not found in real weather file.")
            print("  RESOLUTION CHOSEN : Option (b) - Calibrated synthetic fixture fallback.")
    else:
        print("  Dataset dir       : None (Running on calibrated synthetic fixture)")
        print("  GAP DISCLOSURE    : OpenSTEF Liander 2024 published weather schema does not")
        print("                      confirm wind speed (docs/data/openstef-renewable.md §6.3).")
        print("  RESOLUTION CHOSEN : Option (b) - Deterministic calibrated synthetic fixture.")
        rated_w = args.rated_capacity_mw * 1e6
        load_df, weather_df = generate_synthetic_wind_fixture(
            n_days=args.n_days,
            rated_capacity_w=rated_w,
        )

    # ── Step 1 & 2 & 3: Train + evaluate ─────────────────────────────────────
    data_source = (
        f"OpenSTEF Liander 2024 ({args.dataset_dir})"
        if args.dataset_dir is not None
        else "calibrated_synthetic_fixture"
    )
    logger.info("Starting training for wind asset: %s (source: %s)", args.asset_name, data_source)
    result = train_wind_model(
        load_df=load_df,
        weather_df=weather_df,
        asset_name=args.asset_name,
        output_dir=output_dir,
        wind_speed_source=args.wind_speed_source,
        data_source=data_source,
    )

    # ── Step 4: Print validation report ──────────────────────────────────────
    m = result["metrics"]
    print("\n" + "=" * 70)
    print("  M3 Chunk 3 — Wind Forecasting — Validation Results")
    print("=" * 70)
    print(f"  Asset                : {args.asset_name}")
    print(f"  MAE                  : {m['mae_mw']:.6f} MW")
    print(f"  RMSE                 : {m['rmse_mw']:.6f} MW")
    mape_str = f"{m['mape_pct']:.2f} %" if m['mape_pct'] is not None else "N/A"
    print(f"  MAPE (active wind)   : {mape_str}")
    print(f"  Total samples (val)  : {m['n_samples']}")
    print(f"  Active wind samples  : {m['n_active_samples_for_mape']} (gen >= {m['calm_threshold_mw']} MW)")
    print(f"  Model saved to       : {result['model_path']}")
    print(f"  Metadata saved to    : {result['metadata_path']}")

    print("\n  Top-10 Features by Importance:")
    for rank, (feat, score) in enumerate(result["top_features"], 1):
        print(f"    {rank:2d}. {feat:<26} : {score:5d}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
