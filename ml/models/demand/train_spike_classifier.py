"""
GridPilot AI — Train Demand Spike Classifier
============================================
Execution script to train XGBoost demand spike classifier, derive reproducible
labeling rule from training data, evaluate on held-out test split, and save artifacts.
"""

import json
from pathlib import Path
import joblib
import pandas as pd

from ml.models.demand.spike_config import SpikeClassifierConfig
from ml.models.demand.spike_trainer import DemandSpikeClassifier


def main() -> None:
    print("=" * 70)
    print("GridPilot AI — Demand Spike Classifier Training")
    print("=" * 70)

    features_path = Path("./ml/datasets/openstef_demand_features.parquet")
    models_dir = Path("./ml/models/demand")

    if not features_path.exists():
        raise FileNotFoundError(f"Feature dataset not found at {features_path}")

    print(f"Loading feature-engineered dataset from: {features_path}")
    features_df = pd.read_parquet(features_path)
    print(f"Loaded {len(features_df)} rows and {len(features_df.columns)} columns.")

    # Load LightGBM 15m model if available
    lgbm_15m_path = models_dir / "demand-lgbm-v1_h15min.joblib"
    lgbm_15m = None
    if lgbm_15m_path.exists():
        print(f"Loading LightGBM 15m forecast booster from: {lgbm_15m_path}")
        lgbm_15m = joblib.load(lgbm_15m_path)

    config = SpikeClassifierConfig()
    trainer = DemandSpikeClassifier(config=config, models_dir=models_dir)

    print("\nExecuting chronological training and evaluation...")
    metrics = trainer.train_chronological(features_df, lgbm_15m_model=lgbm_15m)

    print("\nTraining complete! Artifacts saved to:", models_dir)
    print("\n--- TEST EVALUATION REPORT ---")
    print(f"Model Version: {metrics['model_version']}")
    print(f"Test Samples:  {metrics['test_sample_size']}")
    print(f"Macro Precision: {metrics['macro_metrics']['precision']:.4f}")
    print(f"Macro Recall:    {metrics['macro_metrics']['recall']:.4f}")
    print(f"Macro F1:        {metrics['macro_metrics']['f1']:.4f}")

    print("\nPer-Class Metrics:")
    for c_name, c_m in metrics["per_class_metrics"].items():
        print(f"  [{c_name.upper()}]: Precision={c_m['precision']:.4f}, Recall={c_m['recall']:.4f}, F1={c_m['f1']:.4f}, Support={c_m['support']}")

    print("\nConfusion Matrix (Rows = True, Columns = Pred):")
    classes = metrics["confusion_matrix"]["classes"]
    cm = metrics["confusion_matrix"]["matrix"]
    print(f"       {'  '.join([f'{c[:5]:>7}' for c in classes])}")
    for i, row in enumerate(cm):
        row_str = "  ".join([f"{val:>7}" for val in row])
        print(f"{classes[i][:7]:>7}: {row_str}")

    print("\nLabeling Rule:")
    rule_path = models_dir / "spike_labeling_rule_v1.json"
    with open(rule_path, "r") as f:
        rule = json.load(f)
    print(f"  Moderate Spike Threshold: >= {rule['thresholds']['moderate_spike_growth_pct_min']}% growth")
    print(f"  Severe Spike Threshold:   >= {rule['thresholds']['severe_spike_growth_pct_min']}% growth")


if __name__ == "__main__":
    main()
