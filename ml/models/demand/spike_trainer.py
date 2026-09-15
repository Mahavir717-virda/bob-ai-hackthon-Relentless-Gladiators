"""
GridPilot AI — Demand Spike Classifier Trainer & Inference
===========================================================
Trains and evaluates multi-class XGBoost classifier for grid demand spike detection.
Evaluates on chronological test split and reports precision, recall, F1, and confusion matrix.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.utils.class_weight import compute_sample_weight
import xgboost as xgb

from ml.models.demand.spike_config import SpikeClassifierConfig
from ml.models.demand.spike_labeling import assign_spike_labels, derive_labeling_rule
from services.forecasting.errors import SpikeClassifierInputError


class DemandSpikeClassifier:
    """
    XGBoost 3-class demand spike detection classifier.

    Classes:
      0 = Normal
      1 = Moderate Spike
      2 = Severe Spike
    """

    def __init__(
        self,
        config: Optional[SpikeClassifierConfig] = None,
        models_dir: Path | str = "./ml/models/demand",
    ) -> None:
        self.config = config or SpikeClassifierConfig()
        self.models_dir = Path(models_dir)
        self.model: Optional[xgb.XGBClassifier] = None
        self.labeling_rule: Optional[Dict[str, Any]] = None
        self.evaluation_metrics: Optional[Dict[str, Any]] = None

    def build_spike_features(
        self,
        features_df: pd.DataFrame,
        lgbm_15m_model: Optional[Any] = None,
    ) -> pd.DataFrame:
        """
        Builds the exact feature set required for the spike classifier.

        Features:
          - current_load
          - forecast_load (predicted by LightGBM 15m)
          - load_growth_pct
          - historical_peak_24h
          - temp_c, humidity, cloud_cover, wind_speed, solar_radiation
          - hour, hour_sin, hour_cos, day_of_week, is_weekend
        """
        df = features_df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.sort_values("timestamp").reset_index(drop=True)

        # 1. Current load
        df["current_load"] = df["demand_mw"].astype(float)

        # 2. Historical peak (24h past rolling max using shift(1) to avoid leakage)
        df["historical_peak_24h"] = (
            df["demand_mw"].shift(1).rolling(window=96, min_periods=4).max().bfill()
        )

        # 3. Forecast load (from LightGBM 15m model if provided, else lag-1 or persistence fallback)
        if lgbm_15m_model is not None:
            # Predict using LightGBM features
            try:
                lgbm_feat_names = lgbm_15m_model.feature_name()
                avail_feats = [c for c in lgbm_feat_names if c in df.columns]
                if len(avail_feats) == len(lgbm_feat_names):
                    preds = lgbm_15m_model.predict(df[avail_feats])
                    df["forecast_load"] = np.maximum(0.0, preds)
                else:
                    df["forecast_load"] = df["demand_mw"].shift(1).bfill()
            except Exception:
                df["forecast_load"] = df["demand_mw"].shift(1).bfill()
        else:
            # Check if lag_15m exists, else persistence
            if "demand_lag_15m" in df.columns:
                df["forecast_load"] = df["demand_lag_15m"].bfill()
            else:
                df["forecast_load"] = df["demand_mw"].shift(1).bfill()

        # 4. Load growth percentage between forecast and current load
        eps = self.config.denominator_stabilizer_mw
        denom = np.maximum(df["current_load"], eps)
        df["load_growth_pct"] = ((df["forecast_load"] - df["current_load"]) / denom) * 100.0

        # 5. Calendar and weather features
        if "hour" not in df.columns:
            df["hour"] = df["timestamp"].dt.hour
        if "hour_sin" not in df.columns:
            df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24.0)
        if "hour_cos" not in df.columns:
            df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24.0)
        if "day_of_week" not in df.columns:
            df["day_of_week"] = df["timestamp"].dt.dayofweek
        if "is_weekend" not in df.columns:
            df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

        # Ensure weather features exist (fill with zero or forward fill if absent)
        weather_cols = ["temp_c", "humidity", "cloud_cover", "wind_speed", "solar_radiation"]
        for w_col in weather_cols:
            if w_col not in df.columns:
                df[w_col] = 0.0
            else:
                df[w_col] = df[w_col].ffill().bfill()

        return df

    def validate_feature_input(self, X: pd.DataFrame | np.ndarray) -> None:
        """Validates that input features match expectations and contain no invalid/missing values."""
        required = self.config.feature_names
        if isinstance(X, pd.DataFrame):
            missing = [col for col in required if col not in X.columns]
            if missing:
                raise SpikeClassifierInputError(
                    message=f"Missing required feature columns for spike classifier: {missing}",
                    missing_or_invalid_fields=missing,
                )
            # Check for NaNs
            nan_cols = [col for col in required if X[col].isna().any()]
            if nan_cols:
                raise SpikeClassifierInputError(
                    message=f"Feature input contains NaN values in columns: {nan_cols}",
                    missing_or_invalid_fields=nan_cols,
                )
        elif isinstance(X, np.ndarray):
            if X.ndim != 2 or X.shape[1] != len(required):
                raise SpikeClassifierInputError(
                    message=f"Expected numpy array of shape (N, {len(required)}), got {X.shape}",
                    missing_or_invalid_fields=[f"dimension_{X.shape}"],
                )
            if np.isnan(X).any():
                raise SpikeClassifierInputError(
                    message="Numpy feature array contains NaN values",
                    missing_or_invalid_fields=["nan_values"],
                )
        else:
            raise SpikeClassifierInputError(
                message=f"Unsupported feature input type: {type(X)}. Expected DataFrame or 2D numpy array."
            )

    def train_chronological(
        self,
        features_df: pd.DataFrame,
        lgbm_15m_model: Optional[Any] = None,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
    ) -> Dict[str, Any]:
        """
        Executes reproducible end-to-end training and test evaluation.

        Parameters
        ----------
        features_df : pd.DataFrame
            Dataset with timestamps and raw demand.
        lgbm_15m_model : Any, optional
            LightGBM 15m forecast booster.
        train_ratio : float
            Chronological train split proportion (0.70).
        val_ratio : float
            Chronological validation split proportion (0.15).

        Returns
        -------
        Dict[str, Any]
            Evaluation summary on test split.
        """
        # 1. Build features
        enriched_df = self.build_spike_features(features_df, lgbm_15m_model=lgbm_15m_model)

        # 2. Derive reproducible labeling rule strictly from training split
        n = len(enriched_df)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        train_raw = enriched_df.iloc[:train_end].copy()
        val_raw = enriched_df.iloc[train_end:val_end].copy()
        test_raw = enriched_df.iloc[val_end:].copy()

        rule_path = self.models_dir / "spike_labeling_rule_v1.json"
        self.labeling_rule = derive_labeling_rule(train_raw, self.config, output_path=rule_path)

        # 3. Assign labels to all splits using the single source of truth rule
        train_labels, _ = assign_spike_labels(train_raw, self.labeling_rule)
        val_labels, _ = assign_spike_labels(val_raw, self.labeling_rule)
        test_labels, _ = assign_spike_labels(test_raw, self.labeling_rule)

        train_raw["spike_class"] = train_labels
        val_raw["spike_class"] = val_labels
        test_raw["spike_class"] = test_labels

        feature_cols = self.config.feature_names
        X_train = train_raw[feature_cols]
        y_train = train_raw["spike_class"]

        X_val = val_raw[feature_cols]
        y_val = val_raw["spike_class"]

        X_test = test_raw[feature_cols]
        y_test = test_raw["spike_class"]

        # Drop the last step where target future is NaN
        X_train, y_train = X_train.iloc[:-1], y_train.iloc[:-1]
        X_val, y_val = X_val.iloc[:-1], y_val.iloc[:-1]
        X_test, y_test = X_test.iloc[:-1], y_test.iloc[:-1]

        # 4. Handle extreme class imbalance using sample weights
        sample_weights = compute_sample_weight(class_weight="balanced", y=y_train)

        # 5. Initialize and fit XGBoost classifier
        self.model = xgb.XGBClassifier(
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            learning_rate=self.config.learning_rate,
            subsample=self.config.subsample,
            colsample_bytree=self.config.colsample_bytree,
            min_child_weight=self.config.min_child_weight,
            objective=self.config.objective,
            num_class=self.config.num_class,
            eval_metric=self.config.eval_metric,
            random_state=self.config.random_seed,
            early_stopping_rounds=self.config.early_stopping_rounds,
        )

        self.model.fit(
            X_train,
            y_train,
            sample_weight=sample_weights,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        # 6. Evaluate on held-out test split
        y_pred = self.model.predict(X_test)
        y_proba = self.model.predict_proba(X_test)

        # Compute precision, recall, F1
        classes = [0, 1, 2]
        class_names = ["normal", "moderate", "severe"]

        prec_per_class = precision_score(y_test, y_pred, labels=classes, average=None, zero_division=0)
        rec_per_class = recall_score(y_test, y_pred, labels=classes, average=None, zero_division=0)
        f1_per_class = f1_score(y_test, y_pred, labels=classes, average=None, zero_division=0)

        prec_macro = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
        rec_macro = float(recall_score(y_test, y_pred, average="macro", zero_division=0))
        f1_macro = float(f1_score(y_test, y_pred, average="macro", zero_division=0))

        prec_weighted = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
        rec_weighted = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))
        f1_weighted = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))

        cm = confusion_matrix(y_test, y_pred, labels=classes).tolist()

        test_metrics = {
            "model_version": self.config.model_version,
            "feature_version": self.config.feature_version,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "test_sample_size": len(y_test),
            "macro_metrics": {
                "precision": round(prec_macro, 4),
                "recall": round(rec_macro, 4),
                "f1": round(f1_macro, 4),
            },
            "weighted_metrics": {
                "precision": round(prec_weighted, 4),
                "recall": round(rec_weighted, 4),
                "f1": round(f1_weighted, 4),
            },
            "per_class_metrics": {
                class_names[c]: {
                    "precision": round(float(prec_per_class[c]), 4),
                    "recall": round(float(rec_per_class[c]), 4),
                    "f1": round(float(f1_per_class[c]), 4),
                    "support": int((y_test == c).sum()),
                }
                for c in classes
            },
            "confusion_matrix": {
                "classes": class_names,
                "matrix": cm,
                "notes": "Rows = True Class, Columns = Predicted Class",
            },
            "best_iteration": int(self.model.best_iteration) if hasattr(self.model, "best_iteration") else None,
        }

        self.evaluation_metrics = test_metrics

        # 7. Save artifacts
        self.save_artifacts()

        return test_metrics

    def save_artifacts(self) -> None:
        """Serializes model, metadata, and evaluation metrics."""
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # 1. XGBoost model JSON & Joblib
        model_json_path = self.models_dir / f"{self.config.model_version}.json"
        model_joblib_path = self.models_dir / f"{self.config.model_version}.joblib"
        if self.model is not None:
            self.model.save_model(str(model_json_path))
            joblib.dump(self.model, model_joblib_path)

        # 2. Evaluation metrics JSON & CSV
        if self.evaluation_metrics is not None:
            metrics_json_path = self.models_dir / "spike_evaluation_metrics.json"
            with open(metrics_json_path, "w", encoding="utf-8") as f:
                json.dump(self.evaluation_metrics, f, indent=2)

            # Flatten to CSV
            records = []
            for c_name, c_m in self.evaluation_metrics["per_class_metrics"].items():
                records.append({
                    "model_version": self.config.model_version,
                    "class": c_name,
                    "precision": c_m["precision"],
                    "recall": c_m["recall"],
                    "f1": c_m["f1"],
                    "support": c_m["support"],
                })
            records.append({
                "model_version": self.config.model_version,
                "class": "macro_average",
                "precision": self.evaluation_metrics["macro_metrics"]["precision"],
                "recall": self.evaluation_metrics["macro_metrics"]["recall"],
                "f1": self.evaluation_metrics["macro_metrics"]["f1"],
                "support": self.evaluation_metrics["test_sample_size"],
            })
            pd.DataFrame(records).to_csv(self.models_dir / "spike_evaluation_metrics.csv", index=False)

    def load_model(self) -> None:
        """Loads trained XGBoost model and labeling rule from models_dir."""
        # 1. Model
        joblib_path = self.models_dir / f"{self.config.model_version}.joblib"
        json_path = self.models_dir / f"{self.config.model_version}.json"

        if joblib_path.exists():
            self.model = joblib.load(joblib_path)
        elif json_path.exists():
            self.model = xgb.XGBClassifier()
            self.model.load_model(str(json_path))

        # 2. Labeling rule
        rule_path = self.models_dir / "spike_labeling_rule_v1.json"
        if rule_path.exists():
            with open(rule_path, "r", encoding="utf-8") as f:
                self.labeling_rule = json.load(f)

    def predict(self, X: pd.DataFrame | np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predicts spike classes and probabilities.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            (predicted classes 0/1/2, class probabilities shape (N, 3))
        """
        if self.model is None:
            self.load_model()
            if self.model is None:
                raise RuntimeError("Spike classifier model has not been trained or loaded.")

        self.validate_feature_input(X)
        if isinstance(X, pd.DataFrame):
            X = X[self.config.feature_names]

        preds = self.model.predict(X)
        probas = self.model.predict_proba(X)
        return preds, probas
