"""
GridPilot AI — Demand Baseline Evaluation Runner
=================================================
Evaluates persistence and seasonal-naive baselines on the exact
chronological test split of the OpenSTEF Liander 2024 dataset.

Outputs:
  - baseline_outputs/baseline_evaluation.csv
  - baseline_outputs/baseline_evaluation.json
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

from services.forecasting.baselines import evaluate_baselines_on_split
from services.forecasting.evaluate import chronological_split


def run_baselines_evaluation(
    dataset_path: Path | str = "./ml/datasets/openstef_demand_features.parquet",
    output_dirs: list[Path | str] = ["./baseline_outputs", "./ml/experiments/demand/baseline_outputs"],
    target_col: str = "demand_mw",
    horizons_minutes: list[int] = [15, 30, 60],
) -> pd.DataFrame:
    """Execute baseline evaluation and save evaluation artifacts."""
    data_p = Path(dataset_path)
    if not data_p.exists():
        # Fallback to clean dataset if features parquet not found
        fallback_p = Path("./ml/datasets/openstef_demand_clean.parquet")
        if fallback_p.exists():
            data_p = fallback_p
        else:
            raise FileNotFoundError(f"Neither {data_p} nor {fallback_p} found.")

    print(f"Loading dataset from {data_p}...")
    df = pd.read_parquet(data_p)
    df = df.sort_values("timestamp").reset_index(drop=True)
    print(f"Loaded {len(df)} records ({df['timestamp'].min()} -> {df['timestamp'].max()})")

    # Chronological split (70% train, 15% val, 15% test)
    split_res = chronological_split(df, timestamp_col="timestamp", train_ratio=0.70, val_ratio=0.15)
    print(f"Chronological split:")
    print(f"  Train: {split_res.train_start} -> {split_res.train_end} ({split_res.n_train} rows)")
    print(f"  Val:   {split_res.val_start} -> {split_res.val_end} ({split_res.n_val} rows)")
    print(f"  Test:  {split_res.test_start} -> {split_res.test_end} ({split_res.n_test} rows)")

    test_start_idx = split_res.n_train + split_res.n_val

    # Evaluate baselines across 15, 30, 60 minutes
    print("\nEvaluating persistence and seasonal naive baselines...")
    results_df = evaluate_baselines_on_split(
        full_series=df[target_col],
        test_start_idx=test_start_idx,
        horizons_minutes=horizons_minutes,
        freq_minutes=15,
    )

    # Add metadata columns
    results_df["target_col"] = target_col
    results_df["test_samples"] = split_res.n_test

    print("\n--- BASELINE EVALUATION RESULTS (TEST SET) ---")
    print(results_df.to_string(index=False))

    # Save to all target output directories
    results_dict = results_df.to_dict(orient="records")

    for out_d in output_dirs:
        out_p = Path(out_d)
        out_p.mkdir(parents=True, exist_ok=True)

        csv_path = out_p / "baseline_evaluation.csv"
        results_df.to_csv(csv_path, index=False)
        print(f"Saved: {csv_path}")

        json_path = out_p / "baseline_evaluation.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "split": {
                        "train_samples": split_res.n_train,
                        "val_samples": split_res.n_val,
                        "test_samples": split_res.n_test,
                        "test_start": split_res.test_start,
                        "test_end": split_res.test_end,
                    },
                    "horizons_minutes": horizons_minutes,
                    "target_col": target_col,
                    "results": results_dict,
                },
                f,
                indent=2,
            )
        print(f"Saved: {json_path}")

    return results_df


if __name__ == "__main__":
    run_baselines_evaluation()
