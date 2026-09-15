"""
GridPilot AI — LightGBM Demand Models Training Script
=====================================================
Executes reproducible training for 15-min, 30-min, and 60-min horizons,
evaluates on held-out test split, exports model artifacts, and produces
the baseline-vs-model comparison table.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

from ml.models.demand.config import LightGBMTrainingConfig
from ml.models.demand.trainer import LightGBMDemandForecaster


def train_demand_models(
    features_path: Path | str = "./ml/datasets/openstef_demand_features.parquet",
    output_dir: Path | str = "./ml/models/demand",
    model_version: str = "demand-lgbm-v1",
    learning_rate: float = 0.05,
    num_boost_round: int = 500,
    early_stopping_rounds: int = 30,
) -> None:
    """Execute training pipeline and baseline comparison."""
    features_p = Path(features_path)
    if not features_p.exists():
        raise FileNotFoundError(f"Features dataset not found at {features_p}. Run Chunk 3 first.")

    print(f"Loading feature dataset from {features_p}...")
    df = pd.read_parquet(features_p)
    print(f"Loaded {len(df)} rows x {df.shape[1]} columns.")

    config = LightGBMTrainingConfig(
        model_version=model_version,
        output_dir=output_dir,
        num_boost_round=num_boost_round,
        early_stopping_rounds=early_stopping_rounds,
    )
    config.lgbm_params["learning_rate"] = learning_rate

    forecaster = LightGBMDemandForecaster(config)

    print("\nStarting LightGBM Multi-Horizon Training...")
    models, test_results, metadata = forecaster.train_and_evaluate(df)

    print("\n--- TEST SET EVALUATION METRICS ---")
    print(test_results.to_string(index=False))

    # Save artifacts
    print("\nSaving model artifacts...")
    saved_paths = forecaster.save_artifacts()
    for name, path in saved_paths.items():
        print(f"  {name}: {path}")

    # Compare with baselines
    print("\nComparing with Chunk 4 Baselines...")
    try:
        comparison_df = forecaster.compare_with_baselines()
        print("\n--- BASELINE VS LIGHTGBM COMPARISON TABLE ---")
        print(comparison_df.to_string(index=False))

        # Check claim discipline
        print("\n--- PERFORMANCE VERIFICATION ---")
        for h in config.horizons_minutes:
            h_sub = comparison_df[comparison_df["horizon_minutes"] == h]
            lgbm_row = h_sub[h_sub["model"] == "lightgbm"].iloc[0]
            persist_row = h_sub[h_sub["model"] == "persistence"].iloc[0]
            seasonal_row = h_sub[h_sub["model"] == "seasonal_naive"].iloc[0]

            lgbm_mae = lgbm_row["mae"]
            persist_mae = persist_row["mae"]
            seasonal_mae = seasonal_row["mae"]

            beats_persist = lgbm_mae < persist_mae
            beats_seasonal = lgbm_mae < seasonal_mae

            persist_diff_pct = (persist_mae - lgbm_mae) / persist_mae * 100.0

            status = "BEATS ALL BASELINES" if (beats_persist and beats_seasonal) else "DOES NOT BEAT BASELINE"
            print(
                f"Horizon T+{h}m: LightGBM MAE = {lgbm_mae:.4f} MW | "
                f"Persistence MAE = {persist_mae:.4f} MW ({persist_diff_pct:+.1f}%) | "
                f"Seasonal Naive MAE = {seasonal_mae:.4f} MW -> {status}"
            )
    except Exception as e:
        print(f"Warning: Baseline comparison skipped: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train LightGBM demand forecasting models.")
    parser.add_argument("--features", default="./ml/datasets/openstef_demand_features.parquet")
    parser.add_argument("--outdir", default="./ml/models/demand")
    parser.add_argument("--version", default="demand-lgbm-v1")
    parser.add_argument("--lr", type=float, default=0.05)
    parser.add_argument("--rounds", type=int, default=500)
    args = parser.parse_args()

    train_demand_models(
        features_path=args.features,
        output_dir=args.outdir,
        model_version=args.version,
        learning_rate=args.lr,
        num_boost_round=args.rounds,
    )
