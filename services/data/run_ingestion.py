"""
GridPilot AI — Demand Data Ingestion Runner
===========================================
Executes the demand ingestion pipeline on target OpenSTEF Liander 2024 assets,
generating canonical clean datasets and machine-readable data quality reports.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import urllib.parse
import urllib.request
import pandas as pd

from services.data.config import AssetCategory, IngestionConfig, MissingValuePolicy
from services.data.pipeline import DemandIngestionPipeline

BASE_RESOLVE = "https://huggingface.co/datasets/OpenSTEF/liander2024-energy-forecasting-benchmark/resolve/main"


def fetch_or_load_openstef(
    group: str = "mv_feeder",
    asset_name: str = "OS Edam",
    cache_dir: Path | str = "./ml/datasets/raw",
) -> Path:
    """Download OpenSTEF asset file if not already cached locally."""
    cache_path = Path(cache_dir) / group / f"{asset_name}.parquet"
    if cache_path.exists():
        return cache_path

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    rel_path = f"load_measurements/{group}/{asset_name}.parquet"
    parts = rel_path.split("/")
    encoded = "/".join(urllib.parse.quote(p) for p in parts)
    url = f"{BASE_RESOLVE}/{encoded}"

    print(f"Downloading OpenSTEF dataset from {url}...")
    urllib.request.urlretrieve(url, cache_path)
    print(f"Saved to {cache_path}")
    return cache_path


def run_pipeline(
    asset_name: str = "OS Edam",
    group: str = "mv_feeder",
    missing_policy: MissingValuePolicy = MissingValuePolicy.FORWARD_FILL_MAX_GAP,
    output_dir: Path | str = "./ml/datasets",
) -> None:
    """Run ingestion pipeline for a given asset and save canonical parquet & quality report."""
    raw_path = fetch_or_load_openstef(group=group, asset_name=asset_name)

    config = IngestionConfig(
        asset_id=asset_name,
        group_name=AssetCategory(group),
        missing_policy=missing_policy,
        max_fill_gap_intervals=4,  # max 1 hour gap
    )

    pipeline = DemandIngestionPipeline(config)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    canonical_path = out_dir / "openstef_demand_clean.parquet"
    report_path = out_dir / "data_quality_report.json"

    print(f"Processing '{asset_name}' ({group})...")
    df_clean, report = pipeline.process(
        source=raw_path,
        output_canonical_path=canonical_path,
        output_report_path=report_path,
    )

    print(f"Ingestion successful!")
    print(f"  Rows in: {report.rows_in}")
    print(f"  Rows out: {report.rows_out}")
    print(f"  Initial missing: {report.missing_demand_handling['initial_missing_count']}")
    print(f"  Imputed count: {report.missing_demand_handling['imputed_count']}")
    print(f"  Out of range count: {report.range_validation['out_of_range_count']}")
    print(f"  Reverse flow (negative load) count: {report.range_validation['negative_load_count']}")
    print(f"  Canonical Parquet: {canonical_path}")
    print(f"  Quality Report: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest OpenSTEF demand data.")
    parser.add_argument("--asset", default="OS Edam", help="Asset identifier")
    parser.add_argument("--group", default="mv_feeder", help="Asset category")
    parser.add_argument(
        "--policy",
        default="forward_fill_max_gap",
        choices=["forward_fill_max_gap", "leave_as_null", "drop"],
        help="Missing demand value handling policy",
    )
    args = parser.parse_args()

    run_pipeline(
        asset_name=args.asset,
        group=args.group,
        missing_policy=MissingValuePolicy(args.policy),
    )
