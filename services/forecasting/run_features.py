"""
GridPilot AI — Demand Feature Engineering Runner
=================================================
Consumes the cleaned canonical dataset (openstef_demand_clean.parquet)
and aligns it with confirmed OpenMeteo weather features to produce the
canonical feature store: openstef_demand_features.parquet.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import urllib.parse
import urllib.request
import pandas as pd

from services.forecasting.features import DemandFeaturePipeline, FeatureConfig

BASE_RESOLVE = "https://huggingface.co/datasets/OpenSTEF/liander2024-energy-forecasting-benchmark/resolve/main"


def fetch_or_load_weather(
    group: str = "mv_feeder",
    asset_name: str = "OS Edam",
    cache_dir: Path | str = "./ml/datasets/raw",
) -> pd.DataFrame:
    """Download OpenMeteo weather measurements for the asset if not cached."""
    cache_path = Path(cache_dir) / f"weather_{group}_{asset_name}.parquet"
    if cache_path.exists():
        return pd.read_parquet(cache_path)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    rel_path = f"weather_measurements/{group}/{asset_name}.parquet"
    parts = rel_path.split("/")
    encoded = "/".join(urllib.parse.quote(p) for p in parts)
    url = f"{BASE_RESOLVE}/{encoded}"

    print(f"Downloading weather dataset from {url}...")
    urllib.request.urlretrieve(url, cache_path)
    print(f"Saved weather to {cache_path}")
    return pd.read_parquet(cache_path)


def generate_demand_features(
    canonical_input_path: Path | str = "./ml/datasets/openstef_demand_clean.parquet",
    output_feature_path: Path | str = "./ml/datasets/openstef_demand_features.parquet",
    output_metadata_path: Path | str = "./ml/datasets/feature_metadata.json",
    group: str = "mv_feeder",
    asset_name: str = "OS Edam",
) -> None:
    """Generate and export demand features."""
    input_p = Path(canonical_input_path)
    if not input_p.exists():
        raise FileNotFoundError(
            f"Canonical dataset not found at {input_p}. Run Chunk 2 ingestion first."
        )

    print(f"Loading canonical dataset: {input_p}...")
    clean_df = pd.read_parquet(input_p)
    print(f"Loaded {len(clean_df)} rows.")

    # Load matching weather features
    weather_df = fetch_or_load_weather(group=group, asset_name=asset_name)
    print(f"Loaded weather dataset ({len(weather_df)} rows).")

    # Configure pipeline
    config = FeatureConfig(
        target_col="demand_mw",
        timestamp_col="timestamp",
        asset_col="asset_id",
        freq_minutes=15,
        lag_minutes=[15, 30, 60, 1440],
        rolling_windows=[4, 16, 96],
        rolling_stats=["mean", "std", "min", "max"],
        include_momentum=True,
        include_cyclical=True,
    )
    pipeline = DemandFeaturePipeline(config)

    print("Building features...")
    features_df = pipeline.transform(clean_df, weather_df=weather_df)
    metadata = pipeline.get_metadata()

    # Save outputs
    out_feat_p = Path(output_feature_path)
    out_feat_p.parent.mkdir(parents=True, exist_ok=True)
    features_df.to_parquet(out_feat_p, index=False)
    print(f"Saved feature dataset to {out_feat_p} (shape: {features_df.shape})")

    out_meta_p = Path(output_metadata_path)
    with open(out_meta_p, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved feature metadata to {out_meta_p}")

    print(f"\nFeature Engineering Summary:")
    print(f"  Total columns: {features_df.shape[1]}")
    print(f"  Engineered feature count: {metadata['total_features']}")
    print(f"  Numeric features: {len(metadata['numeric_features'])}")
    print(f"  Categorical features: {len(metadata['categorical_features'])}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run demand feature engineering.")
    parser.add_argument("--asset", default="OS Edam")
    parser.add_argument("--group", default="mv_feeder")
    args = parser.parse_args()

    generate_demand_features(group=args.group, asset_name=args.asset)
