"""
GridPilot AI — Train & Serialize Demand Artifacts
=================================================
Trains LightGBM multi-horizon demand forecasters and XGBoost spike classifier
on real OpenSTEF 2024 data, validates chronologically, and serializes:
  - ml/models/demand/demand_lgbm.pkl
  - ml/models/demand/demand_lgbm_metadata.json
  - ml/models/demand/spike_xgb.pkl
  - ml/models/demand/spike_xgb_metadata.json
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score

from ml.models.demand.config import LightGBMTrainingConfig
from ml.models.demand.spike_config import SpikeClassifierConfig
from ml.models.demand.spike_trainer import DemandSpikeClassifier
from ml.models.demand.trainer import LightGBMDemandForecaster
from services.forecasting.demand_model import DemandLGBMModel


def run_training_and_serialization() -> None:
    models_dir = Path("./ml/models/demand")
    features_path = Path("./ml/datasets/openstef_demand_features.parquet")
    models_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("STEP 2-6: Training LightGBM Demand Forecasting Models")
    print("=" * 70)

    if not features_path.exists():
        raise FileNotFoundError(f"Feature dataset not found at {features_path}")

    print(f"Loading dataset: {features_path}")
    features_df = pd.read_parquet(features_path)
    print(f"Dataset shape: {features_df.shape[0]} rows x {features_df.shape[1]} columns")

    # 1. Train LightGBM Forecaster
    lgbm_config = LightGBMTrainingConfig(
        model_version="demand-lgbm-v1",
        output_dir=models_dir,
    )
    forecaster = LightGBMDemandForecaster(lgbm_config)
    models_dict, test_results, metadata = forecaster.train_and_evaluate(features_df)

    print("\nLightGBM Test Results:")
    print(test_results.to_string(index=False))

    # Baseline comparison
    try:
        comparison_df = forecaster.compare_with_baselines()
        print("\nBaseline Comparison:")
        print(comparison_df.to_string(index=False))
    except Exception as e:
        print(f"Note on baseline comparison: {e}")

    # 2. Package & Serialize DemandLGBMModel to demand_lgbm.pkl
    print("\n" + "=" * 70)
    print("STEP 7-8: Serializing demand_lgbm.pkl & metadata")
    print("=" * 70)

    horizon_rmse = {}
    for h, m_data in metadata.get("horizons", {}).items():
        h_min = m_data.get("horizon_minutes")
        rmse = m_data.get("test_metrics", {}).get("rmse")
        if h_min and rmse:
            horizon_rmse[h_min] = float(rmse)

    container = DemandLGBMModel(
        models=models_dict,
        feature_names=metadata["feature_names"],
        horizon_rmse=horizon_rmse,
        metadata=metadata,
    )

    lgbm_pkl_path = models_dir / "demand_lgbm.pkl"
    joblib.dump(container, lgbm_pkl_path)
    print(f"Saved: {lgbm_pkl_path} (size: {lgbm_pkl_path.stat().st_size} bytes)")

    # Save native text model files for robust cross-platform loading
    for h, b in models_dict.items():
        txt_path = models_dir / f"demand-lgbm-v1_h{h}min.txt"
        b.save_model(str(txt_path))
        print(f"Saved native text model: {txt_path}")

    # Demand Metadata
    metadata_out = {
        "model_name": "GridPilot Demand LightGBM Forecaster",
        "algorithm": "LightGBM Regressor (Multi-Horizon Boosters)",
        "version": "demand-lgbm-v1",
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "target": "demandMw",
        "horizons": [15, 30, 60],
        "feature_names": metadata["feature_names"],
        "training_row_count": metadata["split_info"]["train_samples"],
        "validation_row_count": metadata["split_info"]["val_samples"],
        "test_row_count": metadata["split_info"]["test_samples"],
        "metrics_per_horizon": {
            f"{row['horizon_minutes']}m": {
                "mae": round(row["mae"], 4),
                "rmse": round(row["rmse"], 4),
                "mape": round(row["mape"], 4),
            }
            for _, row in test_results.iterrows()
        },
        "overall_test_metrics": {
            "mae": round(float(test_results["mae"].mean()), 4),
            "rmse": round(float(test_results["rmse"].mean()), 4),
            "mape": round(float(test_results["mape"].mean()), 4),
        },
        "baseline_comparison": comparison_df.to_dict(orient="records") if "comparison_df" in locals() else [],
        "random_seed": lgbm_config.lgbm_params.get("seed", 42),
        "model_hyperparameters": lgbm_config.lgbm_params,
        "artifact_path": "ml/models/demand/demand_lgbm.pkl",
        "serialization_format": "joblib",
    }

    lgbm_meta_path = models_dir / "demand_lgbm_metadata.json"
    with open(lgbm_meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata_out, f, indent=2)
    print(f"Saved metadata: {lgbm_meta_path}")

    # 3. Train Spike XGBoost Classifier
    print("\n" + "=" * 70)
    print("STEP 10-13: Training & Serializing Spike XGBoost Classifier")
    print("=" * 70)

    spike_config = SpikeClassifierConfig()
    spike_trainer = DemandSpikeClassifier(config=spike_config, models_dir=models_dir)

    # Use 15m LightGBM booster for forecast_load feature during training
    booster_15m = models_dict[15]
    spike_metrics = spike_trainer.train_chronological(features_df, lgbm_15m_model=booster_15m)

    # Save spike_xgb.pkl
    spike_pkl_path = models_dir / "spike_xgb.pkl"
    joblib.dump(spike_trainer.model, spike_pkl_path)
    print(f"Saved: {spike_pkl_path} (size: {spike_pkl_path.stat().st_size} bytes)")

    # Read rule metadata
    rule_path = models_dir / "spike_labeling_rule_v1.json"
    rule_meta = {}
    if rule_path.exists():
        with open(rule_path, "r", encoding="utf-8") as f:
            rule_meta = json.load(f)

    # Compute test accuracy
    cm = spike_metrics["confusion_matrix"]["matrix"]
    total_samples = spike_metrics["test_sample_size"]
    correct_samples = sum(cm[i][i] for i in range(len(cm)))
    test_accuracy = round(correct_samples / total_samples, 4)

    # Spike Metadata
    spike_metadata_out = {
        "model_name": "GridPilot Demand Spike XGBoost Classifier",
        "algorithm": "XGBoost Classifier (multi:softprob)",
        "version": "demand-spike-xgb-v1",
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "target": "spike_class",
        "classes": ["normal", "moderate", "severe"],
        "class_mapping": {0: "normal", 1: "moderate", 2: "severe"},
        "feature_names": spike_config.feature_names,
        "sample_size": total_samples,
        "labeling_rule": rule_meta,
        "evaluation_metrics": {
            "accuracy": test_accuracy,
            "macro_precision": spike_metrics["macro_metrics"]["precision"],
            "macro_recall": spike_metrics["macro_metrics"]["recall"],
            "macro_f1": spike_metrics["macro_metrics"]["f1"],
            "weighted_precision": spike_metrics["weighted_metrics"]["precision"],
            "weighted_recall": spike_metrics["weighted_metrics"]["recall"],
            "weighted_f1": spike_metrics["weighted_metrics"]["f1"],
            "per_class": spike_metrics["per_class_metrics"],
            "confusion_matrix": spike_metrics["confusion_matrix"],
        },
        "model_hyperparameters": {
            "n_estimators": spike_config.n_estimators,
            "max_depth": spike_config.max_depth,
            "learning_rate": spike_config.learning_rate,
            "subsample": spike_config.subsample,
            "colsample_bytree": spike_config.colsample_bytree,
            "min_child_weight": spike_config.min_child_weight,
            "objective": spike_config.objective,
            "num_class": spike_config.num_class,
            "random_seed": spike_config.random_seed,
        },
        "artifact_path": "ml/models/demand/spike_xgb.pkl",
        "serialization_format": "joblib",
    }

    spike_meta_path = models_dir / "spike_xgb_metadata.json"
    with open(spike_meta_path, "w", encoding="utf-8") as f:
        json.dump(spike_metadata_out, f, indent=2)
    print(f"Saved metadata: {spike_meta_path}")

    # 4. Verify reload & inference
    print("\n" + "=" * 70)
    print("VERIFICATION: Reloading & Testing Serialized Artifacts")
    print("=" * 70)

    # Load demand_lgbm via ModelLoader
    from services.forecasting.model_loader import ModelLoader
    loader = ModelLoader(models_dir=models_dir)
    loaded_lgbm = loader.get_demand_model(force_reload=True)
    print(f"Reloaded demand model type: {type(loaded_lgbm)}")
    test_sample = features_df.tail(10)[loaded_lgbm.feature_names]
    preds_15 = loaded_lgbm.predict(test_sample, horizon=15)
    preds_30 = loaded_lgbm.predict(test_sample, horizon=30)
    preds_60 = loaded_lgbm.predict(test_sample, horizon=60)
    assert not np.isnan(preds_15).any(), "NaN found in 15m predictions!"
    assert not np.isnan(preds_30).any(), "NaN found in 30m predictions!"
    assert not np.isnan(preds_60).any(), "NaN found in 60m predictions!"
    print(f"Sample 15m predictions (MW): {np.round(preds_15[:3], 3)}")
    print(f"Sample 30m predictions (MW): {np.round(preds_30[:3], 3)}")
    print(f"Sample 60m predictions (MW): {np.round(preds_60[:3], 3)}")

    # Load spike_xgb.pkl
    loaded_spike = joblib.load(spike_pkl_path)
    print(f"Reloaded spike_xgb.pkl type: {type(loaded_spike)}")
    spike_test_feats = spike_trainer.build_spike_features(features_df.tail(150), lgbm_15m_model=booster_15m)
    spike_sample = spike_test_feats.tail(10)[spike_config.feature_names]
    spike_preds = loaded_spike.predict(spike_sample)
    spike_probas = loaded_spike.predict_proba(spike_sample)
    assert not np.isnan(spike_preds).any(), "NaN in spike predictions!"
    assert not np.isnan(spike_probas).any(), "NaN in spike probas!"
    print(f"Sample spike predictions: {spike_preds[:3]}")
    print(f"Sample spike probabilities: {np.round(spike_probas[:3], 4)}")

    print("\nALL ARTIFACTS TRAINED, SERIALIZED, AND VERIFIED!")


if __name__ == "__main__":
    run_training_and_serialization()
