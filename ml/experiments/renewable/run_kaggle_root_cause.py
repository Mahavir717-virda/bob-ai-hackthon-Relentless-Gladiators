#!/usr/bin/env python3
"""Train Step 5 Kaggle deviation-association models."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.renewable.kaggle_root_cause import train_kaggle_root_cause_models


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Kaggle renewable root-cause association models")
    parser.add_argument("--dataset-dir", default="ml/datasets/kaggle_power_system")
    parser.add_argument("--forecast-artifact-dir", default="ml/models/renewable/artifacts/kaggle")
    parser.add_argument("--output-dir", default="ml/models/renewable/artifacts/kaggle")
    parser.add_argument("--min-rows", type=int, default=500)
    args = parser.parse_args()
    result = train_kaggle_root_cause_models(
        PROJECT_ROOT / args.dataset_dir, PROJECT_ROOT / args.forecast_artifact_dir,
        PROJECT_ROOT / args.output_dir, min_rows=args.min_rows,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()