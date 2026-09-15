#!/usr/bin/env python3
"""
ml/experiments/renewable/train_solar.py
=========================================
M3 Chunk 2 — Solar Generation Forecasting Experiment

This script:
1. Loads (or generates synthetic) solar + weather data.
2. Engineers features via solar_features.build_solar_features().
3. Trains a LightGBM model with chronological train/val split.
4. Reports MAE, RMSE, MAPE on the held-out validation window.
5. Saves the trained model and metadata JSON to ml/models/renewable/.

Usage
-----
    # With real data (after downloading liander2024 dataset):
    python ml/experiments/renewable/train_solar.py \\
        --dataset-dir ml/datasets/liander2024 \\
        --asset-name <solar_park_name> \\
        --output-dir ml/models/renewable

    # Without real data (runs on synthetic fixture — default):
    python ml/experiments/renewable/train_solar.py

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
    generate_synthetic_solar_fixture,
    load_openstef_load,
    load_openstef_weather,
)
from services.renewable.solar_model import train_solar_model

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
    p = argparse.ArgumentParser(description="Train LightGBM solar forecaster (M3 Chunk 2)")
    p.add_argument("--dataset-dir", default=None,
                   help="Path to liander2024 dataset root. If omitted, synthetic fixture is used.")
    p.add_argument("--asset-name", default="solar_park_synth_01",
                   help="Solar park asset name / filename stem in load_measurements/")
    p.add_argument("--lat", type=float, default=52.3,
                   help="Asset latitude (default: Amsterdam)")
    p.add_argument("--lon", type=float, default=4.9,
                   help="Asset longitude (default: Amsterdam)")
    p.add_argument("--output-dir", default="ml/models/renewable",
                   help="Directory for model artefacts")
    p.add_argument("--n-days", type=int, default=365,
                   help="Days of synthetic data (ignored if --dataset-dir provided)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)

    # ── 1. Load data ─────────────────────────────────────────────────────────
    if args.dataset_dir is not None:
        logger.info("Loading REAL data from %s / asset=%s", args.dataset_dir, args.asset_name)
        load_df    = load_openstef_load(args.dataset_dir, args.asset_name)
        weather_df = load_openstef_weather(args.dataset_dir, args.asset_name, versioned=False)
    else:
        logger.warning(
            "No --dataset-dir provided.  Running on SYNTHETIC fixture (%d days).\n"
            "This is representative but NOT a substitute for real data.\n"
            "Download the dataset and re-run with --dataset-dir ml/datasets/liander2024",
            args.n_days,
        )
        load_df, weather_df = generate_synthetic_solar_fixture(
            n_days=args.n_days,
            lat=args.lat,
            lon=args.lon,
        )

    # ── 2. Train + evaluate ───────────────────────────────────────────────────
    logger.info("Starting training for asset: %s", args.asset_name)
    result = train_solar_model(
        load_df=load_df,
        weather_df=weather_df,
        lat=args.lat,
        lon=args.lon,
        asset_name=args.asset_name,
        output_dir=output_dir,
    )

    # ── 3. Print results ──────────────────────────────────────────────────────
    m = result["metrics"]
    print("\n" + "=" * 60)
    print("  M3 Chunk 2 — Solar Forecasting — Validation Results")
    print("=" * 60)
    print(f"  Asset       : {args.asset_name}")
    print(f"  MAE         : {m['mae_mw']:.6f} MW")
    print(f"  RMSE        : {m['rmse_mw']:.6f} MW")
    print(f"  MAPE (day)  : {m['mape_pct']} %")
    print(f"  Val samples : {m['n_samples']:,}  ({m['n_daytime_samples_for_mape']:,} daytime for MAPE)")
    print(f"  Model saved : {result['model_path']}")
    print(f"  Metadata    : {result['metadata_path']}")
    print("=" * 60)

    print("\nTop-10 Features by Importance:")
    fi_sorted = sorted(result["feature_importance"].items(), key=lambda x: x[1], reverse=True)[:10]
    for rank, (feat, imp) in enumerate(fi_sorted, 1):
        print(f"  {rank:2d}. {feat:<25s} {imp:.0f}")
    print()


if __name__ == "__main__":
    main()
