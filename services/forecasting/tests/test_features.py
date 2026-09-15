"""
Unit tests proving leakage prevention and mathematical correctness
for demand forecasting feature engineering.
"""

from __future__ import annotations

import unittest
import numpy as np
import pandas as pd

from services.forecasting.features import (
    FEATURE_PIPELINE_VERSION,
    DemandFeaturePipeline,
    FeatureConfig,
)
from services.forecasting.holidays import is_dutch_holiday


class TestDemandFeaturePipeline(unittest.TestCase):
    def setUp(self) -> None:
        # Generate 200 timesteps of synthetic demand (15-min intervals)
        # using distinct monotonically recognizable values
        self.n_rows = 200
        self.ts = pd.date_range("2024-04-26 12:00:00", periods=self.n_rows, freq="15min", tz="UTC")
        self.raw_demand = np.array([float(10.0 + i * 0.5) for i in range(self.n_rows)])

        self.df = pd.DataFrame({
            "timestamp": self.ts,
            "demand_mw": self.raw_demand,
            "load": self.raw_demand * 1e6,
            "asset_id": "TEST_FEEDER",
        })

        self.config = FeatureConfig(
            target_col="demand_mw",
            timestamp_col="timestamp",
            asset_col="asset_id",
            freq_minutes=15,
            lag_minutes=[15, 30, 60, 1440],
            rolling_windows=[4, 16],
            rolling_stats=["mean", "std", "min", "max"],
            include_momentum=True,
            include_cyclical=True,
        )
        self.pipeline = DemandFeaturePipeline(self.config)

    def test_version_exported(self) -> None:
        self.assertEqual(FEATURE_PIPELINE_VERSION, "1.0.0")
        self.assertEqual(self.pipeline.version, "1.0.0")

    def test_lag_features_exact_past_offsets(self) -> None:
        """
        Assert that for each lag feature, row i matches raw target at row i-periods,
        and is NaN when insufficient history exists.
        """
        feat_df = self.pipeline.transform(self.df)

        lag_period_map = {
            "demand_mw_lag_15m": 1,
            "demand_mw_lag_30m": 2,
            "demand_mw_lag_60m": 4,
            "demand_mw_lag_1440m": 96,
        }

        for col_name, periods in lag_period_map.items():
            self.assertIn(col_name, feat_df.columns)

            # 1. First 'periods' rows must be strictly NaN
            leading_nans = feat_df[col_name].iloc[:periods]
            self.assertTrue(
                leading_nans.isna().all(),
                f"Expected leading {periods} NaNs in {col_name}, but found non-null values!",
            )

            # 2. Rows from 'periods' onward must match target shifted by exactly 'periods'
            expected_series = self.df["demand_mw"].shift(periods)
            valid_mask = expected_series.notna()

            mismatches = (feat_df.loc[valid_mask, col_name] != expected_series[valid_mask]).sum()
            self.assertEqual(
                mismatches,
                0,
                f"Leakage or mismatch detected in {col_name}: {mismatches} rows disagree!",
            )

            # 3. Explicit check at specific indices
            for check_idx in [periods, periods + 5, self.n_rows - 1]:
                if check_idx < self.n_rows:
                    actual_val = feat_df.loc[check_idx, col_name]
                    expected_val = self.df.loc[check_idx - periods, "demand_mw"]
                    self.assertAlmostEqual(actual_val, expected_val, places=6)

    def test_rolling_features_exact_past_windows(self) -> None:
        """
        Assert that rolling statistics at row i depend strictly on rows [i-w, i-1],
        excluding row i itself.
        """
        feat_df = self.pipeline.transform(self.df)

        for w in [4, 16]:
            mean_col = f"demand_mw_roll_mean_{w}"
            min_col = f"demand_mw_roll_min_{w}"
            max_col = f"demand_mw_roll_max_{w}"

            self.assertIn(mean_col, feat_df.columns)
            self.assertIn(min_col, feat_df.columns)
            self.assertIn(max_col, feat_df.columns)

            # First w rows must be NaN (since window w is applied to shift(1))
            self.assertTrue(
                feat_df[mean_col].iloc[:w].isna().all(),
                f"Expected first {w} rows to be NaN in {mean_col}!",
            )

            # Spot check several rows: compute manual slice over raw target [i-w : i]
            for i in [w, w + 10, w + 50]:
                past_window = self.raw_demand[i - w : i]  # strictly up to i-1
                expected_mean = float(np.mean(past_window))
                expected_min = float(np.min(past_window))
                expected_max = float(np.max(past_window))

                self.assertAlmostEqual(feat_df.loc[i, mean_col], expected_mean, places=6)
                self.assertAlmostEqual(feat_df.loc[i, min_col], expected_min, places=6)
                self.assertAlmostEqual(feat_df.loc[i, max_col], expected_max, places=6)

    def test_future_data_mutation_zero_leakage_proof(self) -> None:
        """
        MATHEMATICAL PROOF OF ZERO LEAKAGE:
        Mutating future target data (rows > cutoff) MUST have ZERO EFFECT
        on all computed features at rows <= cutoff.
        """
        cutoff = 100

        # Baseline features on untouched data
        df_base = self.df.copy()
        feat_base = self.pipeline.transform(df_base)

        # Mutated data: multiply all future values by 99999.0
        df_mutated = self.df.copy()
        df_mutated.loc[cutoff + 1 :, "demand_mw"] = (
            df_mutated.loc[cutoff + 1 :, "demand_mw"] * 99999.0
        )
        feat_mutated = self.pipeline.transform(df_mutated)

        feature_cols = self.pipeline.feature_names_

        # Assert all rows up to cutoff are 100% bit-for-bit identical
        for col in feature_cols:
            base_slice = feat_base.loc[:cutoff, col]
            mutated_slice = feat_mutated.loc[:cutoff, col]

            # Both should have identical null patterns
            self.assertTrue(
                (base_slice.isna() == mutated_slice.isna()).all(),
                f"Null pattern mismatch in {col} up to cutoff {cutoff}!",
            )

            # Non-null values must be identical
            valid = base_slice.notna()
            diff = np.abs(base_slice[valid] - mutated_slice[valid])
            max_diff = diff.max() if len(diff) > 0 else 0.0
            self.assertEqual(
                max_diff,
                0.0,
                f"FUTURE LEAKAGE DETECTED in {col}! Modifying row > {cutoff} changed row <= {cutoff} by {max_diff}!",
            )

    def test_calendar_and_dutch_holidays(self) -> None:
        """Verify calendar, weekend, season, and holiday features."""
        feat_df = self.pipeline.transform(self.df)

        self.assertIn("hour", feat_df.columns)
        self.assertIn("day_of_week", feat_df.columns)
        self.assertIn("is_weekend", feat_df.columns)
        self.assertIn("is_holiday", feat_df.columns)
        self.assertIn("season", feat_df.columns)

        # In our sample starting 2024-04-26 12:00:
        # April 26 is Friday (dow=4, weekend=0)
        # April 27 is Saturday (dow=5, weekend=1, Koningsdag Dutch Holiday = 1)
        # April 28 is Sunday (dow=6, weekend=1, is_holiday = 0)
        apr26_mask = feat_df["timestamp"].dt.strftime("%Y-%m-%d") == "2024-04-26"
        apr27_mask = feat_df["timestamp"].dt.strftime("%Y-%m-%d") == "2024-04-27"
        apr28_mask = feat_df["timestamp"].dt.strftime("%Y-%m-%d") == "2024-04-28"

        self.assertTrue((feat_df.loc[apr26_mask, "is_weekend"] == 0).all())
        self.assertTrue((feat_df.loc[apr26_mask, "is_holiday"] == 0).all())

        # Koningsdag on April 27
        self.assertTrue((feat_df.loc[apr27_mask, "is_weekend"] == 1).all())
        self.assertTrue((feat_df.loc[apr27_mask, "is_holiday"] == 1).all())

        # April 28: weekend but not holiday
        self.assertTrue((feat_df.loc[apr28_mask, "is_weekend"] == 1).all())
        self.assertTrue((feat_df.loc[apr28_mask, "is_holiday"] == 0).all())

        # April is Spring (season = 2)
        self.assertTrue((feat_df["season"] == 2).all())

    def test_weather_merge_and_alignment(self) -> None:
        """Verify external weather dataset is properly merged on timestamp."""
        weather_df = pd.DataFrame({
            "timestamp": self.ts,
            "temperature_2m": [15.0 + 0.1 * i for i in range(self.n_rows)],
            "cloud_cover": [50.0 for _ in range(self.n_rows)],
            "wind_speed_10m": [12.5 for _ in range(self.n_rows)],
            "shortwave_radiation": [250.0 for _ in range(self.n_rows)],
            "relative_humidity_2m": [75.0 for _ in range(self.n_rows)],
        })

        feat_df = self.pipeline.transform(self.df, weather_df=weather_df)

        for w_col in ["temperature_2m", "cloud_cover", "wind_speed_10m", "shortwave_radiation", "relative_humidity_2m"]:
            self.assertIn(w_col, feat_df.columns)
            self.assertEqual(len(feat_df[w_col].dropna()), self.n_rows)


if __name__ == "__main__":
    unittest.main()
