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


    # ------------------------------------------------------------------
    # Timestamp ordering
    # ------------------------------------------------------------------

    def test_transform_sorts_unsorted_input(self) -> None:
        """
        transform() must sort rows by timestamp before computing features.

        If the input is shuffled, lag values at each output row must still
        equal the value that was 'periods' steps earlier in calendar time,
        not in the original (shuffled) row order.
        """
        # Shuffle the standard 200-row dataset
        df_shuffled = self.df.sample(frac=1.0, random_state=0).reset_index(drop=True)

        feat_df = self.pipeline.transform(df_shuffled)

        # Output must be sorted chronologically
        ts_out = pd.to_datetime(feat_df["timestamp"])
        self.assertTrue(
            (ts_out.diff().iloc[1:] >= pd.Timedelta(0)).all(),
            "transform() output is not chronologically sorted!",
        )

        # lag_15m at any row must equal demand_mw exactly one step earlier in
        # the *sorted* output, not in the shuffled input order.
        sorted_demand = feat_df["demand_mw"].reset_index(drop=True)
        expected_lag1 = sorted_demand.shift(1)
        actual_lag1 = feat_df["demand_mw_lag_15m"].reset_index(drop=True)

        valid = expected_lag1.notna()
        mismatches = (actual_lag1[valid] != expected_lag1[valid]).sum()
        self.assertEqual(
            mismatches,
            0,
            "lag_15m values do not match chronologically sorted demand after shuffled input!",
        )

    def test_output_timestamp_monotonic_ascending(self) -> None:
        """
        Even when called on an already-sorted DataFrame, the output
        timestamp column must be strictly monotonically increasing.
        """
        feat_df = self.pipeline.transform(self.df)
        ts = pd.to_datetime(feat_df["timestamp"])
        diffs = ts.diff().iloc[1:]
        self.assertTrue(
            (diffs > pd.Timedelta(0)).all(),
            "Output timestamps are not strictly monotonically increasing!",
        )

    # ------------------------------------------------------------------
    # Missing history (insufficient rows for a given lag)
    # ------------------------------------------------------------------

    def test_lag_nan_for_insufficient_history(self) -> None:
        """
        When fewer rows exist than required for a lag, the corresponding
        feature cells must be NaN — never a spurious numeric value.

        Specifically:
          - lag_15m  needs 1 prior row  → row 0 is NaN
          - lag_30m  needs 2 prior rows → rows 0-1 are NaN
          - lag_60m  needs 4 prior rows → rows 0-3 are NaN
          - lag_1440m needs 96 prior rows → rows 0-95 are NaN
        """
        # Use only 10 rows — enough to test the first three lags but not the 24h lag
        df_short = self.df.iloc[:10].copy().reset_index(drop=True)
        feat_df = self.pipeline.transform(df_short)

        expected_nan_counts = {
            "demand_mw_lag_15m": 1,
            "demand_mw_lag_30m": 2,
            "demand_mw_lag_60m": 4,
            "demand_mw_lag_1440m": 10,  # all 10 rows are NaN: need 96, only have 10
        }

        for col, expected_nans in expected_nan_counts.items():
            self.assertIn(col, feat_df.columns, f"{col} missing from output!")
            actual_nans = feat_df[col].isna().sum()
            self.assertEqual(
                actual_nans,
                expected_nans,
                f"{col}: expected {expected_nans} NaN rows with 10-row input, got {actual_nans}!",
            )

    def test_single_row_all_lags_nan(self) -> None:
        """
        A single-row DataFrame must produce all-NaN lag and rolling features
        (there is no past to look back at).
        """
        df_one = self.df.iloc[:1].copy().reset_index(drop=True)
        feat_df = self.pipeline.transform(df_one)

        lag_cols = [c for c in feat_df.columns if "_lag_" in c]
        roll_cols = [c for c in feat_df.columns if "_roll_" in c]
        momentum_cols = [c for c in feat_df.columns if "_diff_" in c]

        for col in lag_cols + roll_cols + momentum_cols:
            self.assertTrue(
                feat_df[col].isna().all(),
                f"{col} should be all-NaN for a single-row input, but got a value!",
            )

    def test_minimum_rows_for_24h_lag(self) -> None:
        """
        lag_1440m requires exactly 96 prior rows.
        Row 96 (0-indexed) must be the first non-NaN value for that feature.
        """
        # 97 rows: row 0-95 → NaN, row 96 → first valid lag_1440m
        df_97 = self.df.iloc[:97].copy().reset_index(drop=True)
        feat_df = self.pipeline.transform(df_97)

        col = "demand_mw_lag_1440m"
        self.assertIn(col, feat_df.columns)

        # Rows 0-95 must be NaN
        self.assertTrue(
            feat_df[col].iloc[:96].isna().all(),
            f"Expected rows 0-95 to be NaN in {col} with 97-row input!",
        )
        # Row 96 must be a valid number (equal to row 0's demand_mw)
        self.assertFalse(
            pd.isna(feat_df.loc[96, col]),
            f"Expected row 96 to be non-NaN in {col} with 97-row input!",
        )
        self.assertAlmostEqual(
            feat_df.loc[96, col],
            self.df.loc[0, "demand_mw"],
            places=6,
            msg=f"Row 96 of {col} should equal row 0 demand_mw!",
        )

    # ------------------------------------------------------------------
    # Future-data leakage (extended cases)
    # ------------------------------------------------------------------

    def test_lag_values_never_reference_current_or_future_row(self) -> None:
        """
        Explicit proof: at row i, every lag column must reference a row
        index strictly less than i (i.e. shift >= 1).

        We verify this by checking that lag_15m[i] == demand_mw[i-1] for
        every valid row, which means row i was NOT used to produce lag_15m[i].
        """
        feat_df = self.pipeline.transform(self.df)

        for i in range(1, len(feat_df)):
            lag_val = feat_df.loc[i, "demand_mw_lag_15m"]
            past_val = feat_df.loc[i - 1, "demand_mw"]
            if not pd.isna(lag_val):
                self.assertAlmostEqual(
                    lag_val,
                    past_val,
                    places=6,
                    msg=f"At row {i}: lag_15m={lag_val} != demand_mw[{i-1}]={past_val} — possible leakage!",
                )

    def test_rolling_mean_excludes_current_row(self) -> None:
        """
        For window=4, the rolling mean at row i must equal the mean of
        demand_mw[i-4 : i] — i.e. rows i-4, i-3, i-2, i-1 (never row i).

        We verify this by checking that if demand_mw[i] is changed, the
        rolling mean at row i does not change.
        """
        config_small = FeatureConfig(
            target_col="demand_mw",
            timestamp_col="timestamp",
            asset_col=None,  # no groupby, simpler path
            freq_minutes=15,
            lag_minutes=[15],
            rolling_windows=[4],
            rolling_stats=["mean"],
            include_momentum=False,
            include_cyclical=False,
        )
        pipeline = DemandFeaturePipeline(config_small)

        # Compute reference features
        df_ref = self.df[["timestamp", "demand_mw"]].copy()
        feat_ref = pipeline.transform(df_ref)

        # Mutate only the current row's demand_mw at row 50, then re-run
        df_mut = df_ref.copy()
        df_mut.loc[50, "demand_mw"] = 999999.0
        feat_mut = pipeline.transform(df_mut)

        roll_col = "demand_mw_roll_mean_4"
        # The rolling mean AT row 50 must be identical in both runs
        # because roll_mean_4[50] depends only on rows 46-49
        self.assertAlmostEqual(
            feat_ref.loc[50, roll_col],
            feat_mut.loc[50, roll_col],
            places=6,
            msg="roll_mean_4 at row 50 changed when only row 50's demand_mw was mutated — current row leakage!",
        )

        # Rows 51-54 SHOULD differ (they now have row 50 in their past window)
        for future_row in [51, 52, 53, 54]:
            self.assertNotAlmostEqual(
                feat_ref.loc[future_row, roll_col],
                feat_mut.loc[future_row, roll_col],
                places=6,
                msg=f"roll_mean_4 at row {future_row} did NOT change when row 50 was mutated — past not used!",
            )


if __name__ == "__main__":
    unittest.main()
