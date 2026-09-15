"""
Unit tests for forecasting baselines and chronological evaluation.
"""

from __future__ import annotations

import unittest
import numpy as np
import pandas as pd

from services.forecasting.baselines import (
    PersistenceForecaster,
    SeasonalNaiveForecaster,
    evaluate_baselines_on_split,
)
from services.forecasting.evaluate import calculate_metrics, chronological_split


class TestBaselines(unittest.TestCase):
    def setUp(self) -> None:
        self.n_points = 300
        self.ts = pd.date_range("2024-01-01", periods=self.n_points, freq="15min", tz="UTC")
        # Periodic synthetic demand: daily sine wave + trend
        t = np.arange(self.n_points)
        self.demand = 50.0 + 10.0 * np.sin(2 * np.pi * t / 96.0) + 0.05 * t
        self.df = pd.DataFrame({
            "timestamp": self.ts,
            "demand_mw": self.demand,
        })

    def test_chronological_split_strict_ordering(self) -> None:
        res = chronological_split(self.df, timestamp_col="timestamp", train_ratio=0.7, val_ratio=0.15)

        self.assertEqual(res.n_train, 210)
        self.assertEqual(res.n_val, 45)
        self.assertEqual(res.n_test, 45)

        # Assert no overlap and strict time ordering
        self.assertTrue(pd.to_datetime(res.train_end) < pd.to_datetime(res.val_start))
        self.assertTrue(pd.to_datetime(res.val_end) < pd.to_datetime(res.test_start))

        # Assert zero shuffle: first timestamp is unchanged
        self.assertEqual(str(res.train_df["timestamp"].iloc[0]), str(self.df["timestamp"].iloc[0]))
        self.assertEqual(str(res.test_df["timestamp"].iloc[-1]), str(self.df["timestamp"].iloc[-1]))

    def test_calculate_metrics(self) -> None:
        y_true = np.array([10.0, 20.0, 30.0, 40.0])
        y_pred = np.array([12.0, 18.0, 33.0, 36.0])

        metrics = calculate_metrics(y_true, y_pred)
        # Errors: [2, -2, 3, -4]
        # Abs errors: [2, 2, 3, 4] -> MAE = 11 / 4 = 2.75
        self.assertAlmostEqual(metrics["mae"], 2.75)
        # Squared errors: [4, 4, 9, 16] -> MSE = 33 / 4 = 8.25 -> RMSE = sqrt(8.25) ~= 2.8723
        self.assertAlmostEqual(metrics["rmse"], np.sqrt(8.25), places=3)
        # Pct errors: [2/10, 2/20, 3/30, 4/40] = [0.2, 0.1, 0.1, 0.1] -> mean 0.125 -> 12.5%
        self.assertAlmostEqual(metrics["mape"], 12.5)
        self.assertEqual(metrics["n"], 4)

    def test_persistence_forecaster(self) -> None:
        model = PersistenceForecaster(freq_minutes=15)
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])

        # 15m (1 step shift)
        p15 = model.predict_series(s, horizon_minutes=15)
        self.assertTrue(np.isnan(p15.iloc[0]))
        self.assertEqual(p15.iloc[1], 10.0)
        self.assertEqual(p15.iloc[4], 40.0)

        # 30m (2 step shift)
        p30 = model.predict_series(s, horizon_minutes=30)
        self.assertTrue(np.isnan(p30.iloc[0]))
        self.assertTrue(np.isnan(p30.iloc[1]))
        self.assertEqual(p30.iloc[2], 10.0)
        self.assertEqual(p30.iloc[4], 30.0)

    def test_seasonal_naive_forecaster(self) -> None:
        # Cycle of 4 steps
        model = SeasonalNaiveForecaster(freq_minutes=15, seasonal_cycle_minutes=60)
        s = pd.Series(list(range(10)), dtype=float)

        p = model.predict_series(s, horizon_minutes=15)
        self.assertTrue(p.iloc[:4].isna().all())
        self.assertEqual(p.iloc[4], 0.0)
        self.assertEqual(p.iloc[9], 5.0)

    def test_evaluate_baselines_on_split(self) -> None:
        test_start_idx = 255
        res_df = evaluate_baselines_on_split(
            self.df["demand_mw"],
            test_start_idx=test_start_idx,
            horizons_minutes=[15, 30, 60],
            freq_minutes=15,
        )

        self.assertEqual(len(res_df), 6)  # 3 persistence + 3 seasonal_naive
        self.assertListEqual(
            res_df.columns.tolist(),
            ["model", "horizon_minutes", "mae", "rmse", "mape", "n"],
        )
        self.assertTrue((res_df["n"] == (self.n_points - test_start_idx)).all())
        self.assertTrue(res_df["mae"].notna().all())
        self.assertTrue(res_df["rmse"].notna().all())


if __name__ == "__main__":
    unittest.main()
