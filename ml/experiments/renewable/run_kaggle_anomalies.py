#!/usr/bin/env python3
"""Train and evaluate Step 4 Kaggle Isolation Forest detectors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.renewable.kaggle_anomaly import train_kaggle_anomaly_detectors


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Kaggle renewable anomaly detectors")
    parser.add_argument("--dataset-dir", default="ml/datasets/kaggle_power_system")
    parser.add_argument("--forecast-artifact-dir", default="ml/models/renewable/artifacts/kaggle")
    parser.add_argument("--output-dir", default="ml/models/renewable/artifacts/kaggle_anomaly")
    parser.add_argument("--contamination", type=float, default=0.05)
    args = parser.parse_args()
    manifest = train_kaggle_anomaly_detectors(
        PROJECT_ROOT / args.dataset_dir, PROJECT_ROOT / args.forecast_artifact_dir,
        PROJECT_ROOT / args.output_dir, contamination=args.contamination,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()