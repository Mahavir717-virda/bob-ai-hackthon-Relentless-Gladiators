"""
Unit tests for LightGBM Demand Forecaster.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

from ml.models.demand.config import LightGBMTrainingConfig
from ml.models.demand.trainer import LightGBMDemandForecaster


class TestLightGBMDemandForecaster(unittest.TestCase):
    def setUp(self) -> None:
        # Create 200 rows of synthetic features
        n = 200
        ts = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
        t = np.arange(n)
        demand = 50.0 + 10.0 * np.sin(2 * np.pi * t / 96.0) + np.random.RandomState(42).normal(0, 0.5, n)

        self.df = pd.DataFrame({
            "timestamp": ts,
            "demand_mw": demand,
            "demand_mw_lag_15m": pd.Series(demand).shift(1),
            "demand_mw_lag_30m": pd.Series(demand).shift(2),
            "demand_mw_lag_60m": pd.Series(demand).shift(4),
            "temperature_2m": 15.0 + 5.0 * np.cos(2 * np.pi * t / 96.0),
            "hour": ts.hour,
            "day_of_week": ts.dayofweek,
        })

        self.config = LightGBMTrainingConfig(
            model_version="test-lgbm-v1",
            horizons_minutes=[15, 30],
            num_boost_round=10,
            early_stopping_rounds=5,
            train_ratio=0.7,
            val_ratio=0.15,
        )

    def test_trainer_end_to_end(self) -> None:
        forecaster = LightGBMDemandForecaster(self.config)
        models, test_results, metadata = forecaster.train_and_evaluate(self.df)

        self.assertIn(15, models)
        self.assertIn(30, models)
        self.assertEqual(len(test_results), 2)
        self.assertIn("mae", test_results.columns)
        self.assertIn("rmse", test_results.columns)

        # Verify predictions work
        X_sample = self.df[forecaster.feature_cols_].dropna().iloc[:5]
        preds_15 = models[15].predict(X_sample)
        self.assertEqual(len(preds_15), 5)
        self.assertTrue(np.all(np.isfinite(preds_15)))

        # Verify artifact saving
        with tempfile.TemporaryDirectory() as tmpdir:
            saved = forecaster.save_artifacts(tmpdir)
            self.assertIn("model_txt_15m", saved)
            self.assertIn("model_joblib_15m", saved)
            self.assertIn("metadata_json", saved)
            self.assertIn("test_metrics_csv", saved)

            for key, path_str in saved.items():
                self.assertTrue(Path(path_str).exists(), f"File {path_str} does not exist!")


if __name__ == "__main__":
    unittest.main()
