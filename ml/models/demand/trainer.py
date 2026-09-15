"""
GridPilot AI — LightGBM Demand Forecaster Training & Evaluation
==============================================================
Trains, validates, evaluates, and serializes reproducible LightGBM
forecasters for 15-min, 30-min, and 60-min horizons.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

from ml.models.demand.config import LightGBMTrainingConfig
from services.forecasting.evaluate import calculate_metrics, chronological_split


class LightGBMDemandForecaster:
    """
    Multi-horizon demand forecasting trainer utilizing LightGBM.
    """

    def __init__(self, config: Optional[LightGBMTrainingConfig] = None) -> None:
        self.config = config or LightGBMTrainingConfig()
        self.models_: Dict[int, lgb.Booster] = {}
        self.feature_cols_: List[str] = []
        self.training_metadata_: Dict[str, Any] = {}
        self.test_metrics_: List[Dict[str, Any]] = []

    def _prepare_feature_cols(self, df: pd.DataFrame) -> List[str]:
        """Extract valid predictor feature columns."""
        excluded_cols = {
            self.config.timestamp_col,
            self.config.target_col,
            "load",
            "demand_kw",
            "available_at",
            "asset_id",
            "group_name",
            "is_imputed",
            "is_out_of_range",
            "is_reverse_flow",
        }
        # Also exclude any target columns
        for h in self.config.horizons_minutes:
            excluded_cols.add(f"target_{h}min")

        feature_cols = [
            c for c in df.columns
            if c not in excluded_cols
            and pd.api.types.is_numeric_dtype(df[c])
        ]
        return feature_cols

    def train_and_evaluate(
        self,
        features_df: pd.DataFrame,
    ) -> Tuple[Dict[int, lgb.Booster], pd.DataFrame, Dict[str, Any]]:
        """
        Train multi-horizon models, evaluate on test set, and record metrics.

        Parameters
        ----------
        features_df : pd.DataFrame
            Complete feature-engineered DataFrame (clean + features).

        Returns
        -------
        Tuple[Dict[int, lgb.Booster], pd.DataFrame, Dict[str, Any]]
            Dictionary of trained models, test evaluation DataFrame, and metadata.
        """
        df = features_df.sort_values(self.config.timestamp_col).reset_index(drop=True)
        self.feature_cols_ = self._prepare_feature_cols(df)

        # 1. Chronological split (70% train, 15% val, 15% test)
        split_res = chronological_split(
            df,
            timestamp_col=self.config.timestamp_col,
            train_ratio=self.config.train_ratio,
            val_ratio=self.config.val_ratio,
        )

        train_df = split_res.train_df
        val_df = split_res.val_df
        test_df = split_res.test_df

        self.models_ = {}
        self.test_metrics_ = []
        horizon_metadata: Dict[str, Any] = {}

        # 2. Train and evaluate for each horizon
        for h in self.config.horizons_minutes:
            periods = self.config.get_periods_for_horizon(h)
            target_col_name = f"target_{h}min"

            # Create target label by shifting future value into row t
            # Target at row t is the ground truth observed at t + periods
            train_target = train_df[self.config.target_col].shift(-periods)
            val_target = val_df[self.config.target_col].shift(-periods)
            test_target = test_df[self.config.target_col].shift(-periods)

            # Drop boundary rows where future target is unknown
            train_mask = train_target.notna() & train_df[self.feature_cols_].notna().all(axis=1)
            val_mask = val_target.notna() & val_df[self.feature_cols_].notna().all(axis=1)
            test_mask = test_target.notna() & test_df[self.feature_cols_].notna().all(axis=1)

            X_train, y_train = train_df.loc[train_mask, self.feature_cols_], train_target[train_mask]
            X_val, y_val = val_df.loc[val_mask, self.feature_cols_], val_target[val_mask]
            X_test, y_test = test_df.loc[test_mask, self.feature_cols_], test_target[test_mask]

            train_set = lgb.Dataset(X_train, label=y_train)
            val_set = lgb.Dataset(X_val, label=y_val, reference=train_set)

            start_t = time.time()
            booster = lgb.train(
                self.config.lgbm_params,
                train_set,
                num_boost_round=self.config.num_boost_round,
                valid_sets=[val_set],
                callbacks=[
                    lgb.early_stopping(self.config.early_stopping_rounds, verbose=False),
                ],
            )
            training_time = round(time.time() - start_t, 3)
            self.models_[h] = booster

            # Compute validation metrics
            val_preds = booster.predict(X_val)
            val_metrics = calculate_metrics(y_val, val_preds)

            # Compute test metrics
            test_preds = booster.predict(X_test)
            test_metrics = calculate_metrics(y_test, test_preds)

            self.test_metrics_.append({
                "model": "lightgbm",
                "horizon_minutes": h,
                "mae": test_metrics["mae"],
                "rmse": test_metrics["rmse"],
                "mape": test_metrics["mape"],
                "n": test_metrics["n"],
                "val_mae": val_metrics["mae"],
                "val_rmse": val_metrics["rmse"],
                "val_mape": val_metrics["mape"],
            })

            horizon_metadata[f"h{h}min"] = {
                "horizon_minutes": h,
                "best_iteration": booster.best_iteration,
                "training_seconds": training_time,
                "n_train_samples": len(X_train),
                "n_val_samples": len(X_val),
                "n_test_samples": len(X_test),
                "val_metrics": val_metrics,
                "test_metrics": test_metrics,
            }

        self.training_metadata_ = {
            "model_version": self.config.model_version,
            "feature_version": self.config.feature_version,
            "target_col": self.config.target_col,
            "hyperparameters": self.config.lgbm_params,
            "features_count": len(self.feature_cols_),
            "feature_names": self.feature_cols_,
            "split_info": {
                "train_samples": split_res.n_train,
                "val_samples": split_res.n_val,
                "test_samples": split_res.n_test,
                "train_start": split_res.train_start,
                "train_end": split_res.train_end,
                "val_start": split_res.val_start,
                "val_end": split_res.val_end,
                "test_start": split_res.test_start,
                "test_end": split_res.test_end,
            },
            "horizons": horizon_metadata,
        }

        test_results_df = pd.DataFrame(self.test_metrics_)
        return self.models_, test_results_df, self.training_metadata_

    def save_artifacts(
        self,
        output_dir: Optional[Path | str] = None,
    ) -> Dict[str, str]:
        """Serialize model files, training metadata, and test metrics."""
        out_dir = Path(output_dir or self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        saved_paths: Dict[str, str] = {}

        # 1. Save model per horizon in text and joblib formats
        for h, booster in self.models_.items():
            txt_path = out_dir / f"{self.config.model_version}_h{h}min.txt"
            joblib_path = out_dir / f"{self.config.model_version}_h{h}min.joblib"

            booster.save_model(str(txt_path))
            joblib.dump(booster, joblib_path)

            saved_paths[f"model_txt_{h}m"] = str(txt_path)
            saved_paths[f"model_joblib_{h}m"] = str(joblib_path)

        # 2. Save training metadata
        meta_path = out_dir / f"{self.config.model_version}_training_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self.training_metadata_, f, indent=2, default=str)
        saved_paths["metadata_json"] = str(meta_path)

        # 3. Save test metrics
        test_df = pd.DataFrame(self.test_metrics_)
        csv_path = out_dir / f"{self.config.model_version}_test_metrics.csv"
        test_df.to_csv(csv_path, index=False)
        saved_paths["test_metrics_csv"] = str(csv_path)

        return saved_paths

    def compare_with_baselines(
        self,
        baseline_csv_path: Path | str = "./baseline_outputs/baseline_evaluation.csv",
        output_comparison_dir: Optional[Path | str] = None,
    ) -> pd.DataFrame:
        """
        Merge LightGBM test metrics with Chunk 4 baseline metrics and evaluate honest winners.
        """
        base_p = Path(baseline_csv_path)
        if not base_p.exists():
            # Try secondary location
            fallback = Path("./ml/experiments/demand/baseline_outputs/baseline_evaluation.csv")
            if fallback.exists():
                base_p = fallback
            else:
                raise FileNotFoundError(f"Baseline results not found at {base_p}")

        baseline_df = pd.read_csv(base_p)
        lgbm_df = pd.DataFrame(self.test_metrics_)

        # Keep common comparison columns
        common_cols = ["model", "horizon_minutes", "mae", "rmse", "mape", "n"]
        b_sub = baseline_df[[c for c in common_cols if c in baseline_df.columns]].copy()
        l_sub = lgbm_df[[c for c in common_cols if c in lgbm_df.columns]].copy()

        comparison_df = pd.concat([b_sub, l_sub], ignore_index=True)
        comparison_df = comparison_df.sort_values(["horizon_minutes", "mae"]).reset_index(drop=True)

        # Export comparison
        out_dirs = [Path(self.config.output_dir), Path("./baseline_outputs")]
        if output_comparison_dir:
            out_dirs.append(Path(output_comparison_dir))

        for d in out_dirs:
            d.mkdir(parents=True, exist_ok=True)
            comparison_df.to_csv(d / "baseline_vs_lightgbm_comparison.csv", index=False)
            with open(d / "baseline_vs_lightgbm_comparison.json", "w", encoding="utf-8") as f:
                json.dump(comparison_df.to_dict(orient="records"), f, indent=2)

        return comparison_df
