#!/usr/bin/env python3
"""Train the Step 3 aggregate Kaggle solar and wind forecasters."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.renewable.kaggle_forecasting import train_kaggle_forecasters


def main() -> None:
    parser = argparse.ArgumentParser(description="Train aggregate Kaggle renewable forecasters")
    parser.add_argument("--dataset-dir", default="ml/datasets/kaggle_power_system")
    parser.add_argument("--output-dir", default="ml/models/renewable/artifacts/kaggle")
    parser.add_argument("--min-valid-observations", type=int, default=500)
    args = parser.parse_args()
    manifest = train_kaggle_forecasters(
        PROJECT_ROOT / args.dataset_dir, PROJECT_ROOT / args.output_dir,
        min_valid_observations=args.min_valid_observations,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()