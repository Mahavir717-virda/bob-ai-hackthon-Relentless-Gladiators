"""
Unit tests for the demand data ingestion pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd

from services.data.config import AssetCategory, IngestionConfig, MissingValuePolicy
from services.data.pipeline import DemandIngestionPipeline
from services.data.policies import handle_missing_demand
from services.data.quality_reporter import DataQualityReport
from services.data.schema import validate_schema
from services.data.validator import (
    detect_and_handle_duplicates,
    detect_missing_intervals,
    normalize_and_sort_timestamps,
    validate_numeric_ranges,
)


class TestDemandIngestion(unittest.TestCase):
    def setUp(self) -> None:
        self.config = IngestionConfig(
            asset_id="TEST_SUBSTATION",
            group_name=AssetCategory.MV_FEEDER,
        )

    def _create_sample_df(self) -> pd.DataFrame:
        """Create a clean 4-timestep 15-min sample DataFrame."""
        ts = pd.date_range("2024-01-01 00:00:00", periods=4, freq="15min", tz="UTC")
        return pd.DataFrame({
            "timestamp": ts,
            "load": [500000.0, 520000.0, 510000.0, 490000.0],
            "available_at": ts,
        })

    def test_schema_validation_success(self) -> None:
        df = self._create_sample_df()
        res = validate_schema(df, self.config)
        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.missing_required_columns), 0)

    def test_schema_validation_missing_demand_col(self) -> None:
        df = self._create_sample_df().drop(columns=["load"])
        res = validate_schema(df, self.config)
        self.assertFalse(res.is_valid)
        self.assertIn("load", res.missing_required_columns)

    def test_timestamp_normalization_and_sorting(self) -> None:
        # Create un-sorted strings with different timezone
        raw_df = pd.DataFrame({
            "timestamp": [
                "2024-01-01 00:30:00+00:00",
                "2024-01-01 00:00:00+00:00",
                "2024-01-01 00:15:00+00:00",
            ],
            "load": [300.0, 100.0, 200.0],
        })
        df_norm, res = normalize_and_sort_timestamps(raw_df, self.config)
        self.assertEqual(len(df_norm), 3)
        self.assertTrue(res.is_monotonic)
        self.assertEqual(df_norm["load"].tolist(), [100.0, 200.0, 300.0])
        self.assertEqual(str(df_norm["timestamp"].dtype), "datetime64[ns, UTC]")

    def test_duplicate_detection_and_resolution(self) -> None:
        ts = pd.date_range("2024-01-01 00:00:00", periods=3, freq="15min", tz="UTC")
        raw_df = pd.DataFrame({
            "timestamp": [ts[0], ts[1], ts[1], ts[2]],  # ts[1] is duplicated
            "load": [10.0, 20.0, 25.0, 30.0],
        })
        df_dedup, res = detect_and_handle_duplicates(raw_df, self.config, keep="first")
        self.assertEqual(res.duplicate_count, 1)
        self.assertEqual(len(df_dedup), 3)
        self.assertEqual(df_dedup["load"].tolist(), [10.0, 20.0, 30.0])

    def test_missing_intervals_detection(self) -> None:
        # Missing the 00:15 interval
        ts = pd.to_datetime([
            "2024-01-01 00:00:00+00:00",
            "2024-01-01 00:30:00+00:00",  # gap: 30 min delta
            "2024-01-01 00:45:00+00:00",
        ])
        df = pd.DataFrame({"timestamp": ts, "load": [10.0, 20.0, 30.0]})
        res = detect_missing_intervals(df, self.config)
        self.assertEqual(res.expected_intervals, 4)
        self.assertEqual(res.actual_intervals, 3)
        self.assertEqual(res.missing_intervals_count, 1)
        self.assertAlmostEqual(res.missing_intervals_pct, 25.0)

    def test_missing_policy_leave_as_null(self) -> None:
        cfg = IngestionConfig(missing_policy=MissingValuePolicy.LEAVE_AS_NULL)
        df = self._create_sample_df()
        df.loc[1, "load"] = np.nan
        df_res, audit = handle_missing_demand(df, cfg)
        self.assertTrue(df_res.loc[1, "load"] is np.nan or np.isnan(df_res.loc[1, "load"]))
        self.assertEqual(audit.initial_missing_count, 1)
        self.assertEqual(audit.remaining_missing_count, 1)
        self.assertEqual(audit.imputed_count, 0)

    def test_missing_policy_forward_fill_max_gap(self) -> None:
        cfg = IngestionConfig(
            missing_policy=MissingValuePolicy.FORWARD_FILL_MAX_GAP,
            max_fill_gap_intervals=2,
        )
        df = self._create_sample_df()
        df.loc[1, "load"] = np.nan
        df_res, audit = handle_missing_demand(df, cfg)
        self.assertEqual(df_res.loc[1, "load"], 500000.0)  # ffilled from index 0
        self.assertTrue(df_res.loc[1, "is_imputed"])
        self.assertFalse(df_res.loc[0, "is_imputed"])
        self.assertEqual(audit.imputed_count, 1)
        self.assertEqual(audit.remaining_missing_count, 0)

    def test_missing_policy_drop(self) -> None:
        cfg = IngestionConfig(missing_policy=MissingValuePolicy.DROP)
        df = self._create_sample_df()
        df.loc[1, "load"] = np.nan
        df_res, audit = handle_missing_demand(df, cfg)
        self.assertEqual(len(df_res), 3)
        self.assertEqual(audit.dropped_rows_count, 1)

    def test_range_validation_and_reverse_flow(self) -> None:
        cfg = IngestionConfig(
            min_load_watts=-1000.0,
            max_load_watts=10000.0,
        )
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="15min", tz="UTC"),
            "load": [500.0, -200.0, 20000.0],  # normal, reverse-flow, out-of-range
        })
        df_res, res = validate_numeric_ranges(df, cfg)
        self.assertEqual(res.out_of_range_count, 1)
        self.assertEqual(res.negative_load_count, 1)
        self.assertFalse(df_res.loc[0, "is_out_of_range"])
        self.assertFalse(df_res.loc[0, "is_reverse_flow"])
        self.assertTrue(df_res.loc[1, "is_reverse_flow"])  # negative load
        self.assertTrue(df_res.loc[2, "is_out_of_range"])  # > 10000

    def test_end_to_end_pipeline_execution(self) -> None:
        pipeline = DemandIngestionPipeline(self.config)
        raw_df = self._create_sample_df()

        with tempfile.TemporaryDirectory() as tmpdir:
            out_parquet = Path(tmpdir) / "canonical.parquet"
            out_report = Path(tmpdir) / "report.json"

            df_clean, report = pipeline.process(
                raw_df,
                output_canonical_path=out_parquet,
                output_report_path=out_report,
            )

            # Check outputs exist
            self.assertTrue(out_parquet.exists())
            self.assertTrue(out_report.exists())

            # Verify canonical columns
            self.assertIn("demand_mw", df_clean.columns)
            self.assertIn("demand_kw", df_clean.columns)
            self.assertIn("asset_id", df_clean.columns)
            self.assertIn("group_name", df_clean.columns)

            # Verify report JSON content
            with open(out_report, "r", encoding="utf-8") as f:
                rep_data = json.load(f)
            self.assertEqual(rep_data["metadata"]["status"], "SUCCESS")
            self.assertEqual(rep_data["summary"]["rows_in"], 4)
            self.assertEqual(rep_data["summary"]["rows_out"], 4)


if __name__ == "__main__":
    unittest.main()
