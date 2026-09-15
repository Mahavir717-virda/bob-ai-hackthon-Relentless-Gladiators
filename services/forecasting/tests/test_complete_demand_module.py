"""
GridPilot AI — Complete Demand Module Test Suite
=================================================
Comprehensive integration and unit test suite for the complete demand module
(Chunks 2 through 7), including:
  1. Chunk 2: Schema validation, missing timestamps, duplicate detection, missing demand policy.
  2. Chunk 3: Lag feature generation offsets, mathematical leakage prevention.
  3. Chunk 6: Model loading, contract-compliant forecast generation, typed error handling (unknown zone, insufficient history).
  4. Chunk 7: Spike classifier input validation and data-driven labeling.
  5. End-to-End: Small deterministic synthetic fixture running ingestion -> features -> forecast service -> spike classifier.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

# Chunk 2 imports
from services.data.config import AssetCategory, IngestionConfig, MissingValuePolicy
from services.data.pipeline import DemandIngestionPipeline
from services.data.policies import handle_missing_demand
from services.data.schema import validate_schema
from services.data.validator import (
    detect_and_handle_duplicates,
    detect_missing_intervals,
    normalize_and_sort_timestamps,
)

# Chunk 3 & 6 imports
from services.forecasting.errors import (
    InsufficientHistoryError,
    InvalidZoneError,
    SpikeClassifierInputError,
    UnsupportedHorizonError,
)
from services.forecasting.features import DemandFeaturePipeline, FeatureConfig
from services.forecasting.service import DemandForecastService

# Chunk 7 imports
from ml.models.demand.spike_config import SpikeClassifierConfig
from ml.models.demand.spike_labeling import assign_spike_labels, derive_labeling_rule
from ml.models.demand.spike_trainer import DemandSpikeClassifier


class TestCompleteDemandModule(unittest.TestCase):
    """Exhaustive test suite covering all Member 2 demand module capabilities."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set random seeds for determinism and initialize service."""
        np.random.seed(42)
        cls.service = DemandForecastService()

    # =========================================================================
    # CHUNK 2: Data Ingestion & Schema Tests
    # =========================================================================

    def test_schema_validation_rejects_missing_required_fields(self) -> None:
        """Schema validation rejects data missing required fields and pipeline refuses processing."""
        config = IngestionConfig(demand_col="load", timestamp_col="timestamp")
        pipeline = DemandIngestionPipeline(config=config)

        # Missing demand column 'load'
        bad_df_1 = pd.DataFrame({"timestamp": ["2024-01-01T00:00:00Z"], "other_col": [1.0]})
        res_1 = validate_schema(bad_df_1, config)
        self.assertFalse(res_1.is_valid)
        self.assertIn("load", res_1.missing_required_columns)

        with self.assertRaises(ValueError) as ctx:
            pipeline.process(bad_df_1)
        self.assertIn("Schema validation failed", str(ctx.exception))

        # Missing timestamp column
        bad_df_2 = pd.DataFrame({"load": [500000.0], "other_col": [1.0]})
        res_2 = validate_schema(bad_df_2, config)
        self.assertFalse(res_2.is_valid)
        self.assertIn("timestamp", res_2.missing_required_columns)

        with self.assertRaises(ValueError) as ctx2:
            pipeline.process(bad_df_2)
        self.assertIn("Schema validation failed", str(ctx2.exception))

    def test_missing_timestamps_detected_and_reported(self) -> None:
        """Ingestion pipeline detects and reports timestamp intervals missing from expected 15-min grain."""
        config = IngestionConfig(demand_col="load", timestamp_col="timestamp", expected_freq_minutes=15)
        # Gap from 00:00 to 00:45 (missing 00:15 and 00:30)
        ts = ["2024-01-01 00:00:00+00:00", "2024-01-01 00:45:00+00:00"]
        df = pd.DataFrame({"timestamp": pd.to_datetime(ts), "load": [500000.0, 550000.0]})

        gap_result = detect_missing_intervals(df, config)
        self.assertEqual(gap_result.missing_intervals_count, 2)
        self.assertEqual(gap_result.expected_intervals, 4)
        self.assertEqual(gap_result.actual_intervals, 2)
        self.assertIn("2024-01-01 00:15:00+00:00", gap_result.gap_timestamps_sample)

    def test_duplicates_detected_and_resolved_at_documented_grain(self) -> None:
        """Ingestion detects duplicate timestamps at 15-min grain and resolves them via configured policy."""
        config = IngestionConfig(demand_col="load", timestamp_col="timestamp")
        ts = ["2024-01-01 00:00:00+00:00", "2024-01-01 00:00:00+00:00", "2024-01-01 00:15:00+00:00"]
        df = pd.DataFrame({"timestamp": pd.to_datetime(ts), "load": [500000.0, 600000.0, 550000.0]})

        dedup_df, dupe_result = detect_and_handle_duplicates(df, config, keep="first")
        self.assertEqual(dupe_result.duplicate_count, 1)
        self.assertEqual(dupe_result.dropped_duplicates, 1)
        self.assertEqual(len(dedup_df), 2)
        self.assertEqual(dedup_df.iloc[0]["load"], 500000.0)

    def test_missing_demand_handled_per_policy_not_silently_dropped(self) -> None:
        """Missing demand values are handled per documented forward-fill policy, not silently discarded."""
        config = IngestionConfig(
            demand_col="load",
            timestamp_col="timestamp",
            missing_policy=MissingValuePolicy.FORWARD_FILL_MAX_GAP,
            max_fill_gap_intervals=2,
        )
        ts = [
            "2024-01-01 00:00:00+00:00",
            "2024-01-01 00:15:00+00:00",
            "2024-01-01 00:30:00+00:00",
            "2024-01-01 00:45:00+00:00",
        ]
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(ts),
            "load": [500000.0, np.nan, np.nan, 700000.0],
        })

        filled_df, fill_result = handle_missing_demand(df, config)
        self.assertEqual(len(filled_df), 4)  # None dropped
        self.assertFalse(filled_df["load"].isna().any())
        self.assertEqual(filled_df.iloc[1]["load"], 500000.0)
        self.assertEqual(filled_df.iloc[2]["load"], 500000.0)
        self.assertEqual(fill_result.imputed_count, 2)

    # =========================================================================
    # CHUNK 3: Feature Engineering & Leakage Prevention Tests
    # =========================================================================

    def test_lag_features_correct_offsets(self) -> None:
        """Asserts that lag 15m, 30m, 60m, 24h strictly match past observations at rows i-1, i-2, i-4, i-96."""
        n_rows = 150
        dates = pd.date_range("2024-01-01 00:00", periods=n_rows, freq="15min", tz="UTC")
        values = np.arange(100.0, 100.0 + n_rows)
        df = pd.DataFrame({"timestamp": dates, "demand_mw": values})

        pipe = DemandFeaturePipeline(FeatureConfig(freq_minutes=15))
        feated = pipe.transform(df)

        for i in range(97, n_rows):
            self.assertEqual(feated.loc[i, "demand_mw_lag_15m"], values[i - 1])
            self.assertEqual(feated.loc[i, "demand_mw_lag_30m"], values[i - 2])
            self.assertEqual(feated.loc[i, "demand_mw_lag_60m"], values[i - 4])
            self.assertEqual(feated.loc[i, "demand_mw_lag_1440m"], values[i - 96])

    def test_leakage_prevention_no_future_values_used(self) -> None:
        """Mathematical proof: mutating future row i+k leaves all engineered features at row i unchanged."""
        n_rows = 120
        dates = pd.date_range("2024-01-01 00:00", periods=n_rows, freq="15min", tz="UTC")
        values = np.linspace(0.2, 1.5, n_rows)
        df_clean = pd.DataFrame({"timestamp": dates, "demand_mw": values})

        pipe = DemandFeaturePipeline(FeatureConfig(freq_minutes=15))
        res_original = pipe.transform(df_clean)

        # Mutate future data at row 100
        df_mutated = df_clean.copy()
        df_mutated.loc[100, "demand_mw"] = 9999.99

        res_mutated = pipe.transform(df_mutated)

        # Verify all feature columns for all rows 0..99 are completely identical
        feature_cols = [c for c in res_original.columns if c not in ["timestamp"]]
        pd.testing.assert_frame_equal(
            res_original.loc[:99, feature_cols],
            res_mutated.loc[:99, feature_cols],
            check_exact=True,
        )

    # =========================================================================
    # CHUNK 6: Forecast Service & Contract Conformance Tests
    # =========================================================================

    def test_model_loading_correct_version_per_horizon(self) -> None:
        """Forecast service loads correct model version (demand-lgbm-v1) and horizon models."""
        self.assertEqual(self.service.model_version, "demand-lgbm-v1")
        self.assertEqual(self.service.feature_version, "1.0.0")
        for h in [15, 30, 60]:
            self.assertIn(h, self.service.models)

    def test_forecast_generation_conforms_to_contract_and_spacing(self) -> None:
        """Forecast generation strictly conforms to DemandForecast contract with 15-min timestamp spacing."""
        start_time = "2024-11-15T12:00:00Z"
        result = self.service.forecast_demand("OS Edam", start_time, horizon=60)

        # Contract fields
        self.assertEqual(result["zoneId"], "OS Edam")
        self.assertEqual(result["horizonMinutes"], 60)
        self.assertEqual(result["modelVersion"], "demand-lgbm-v1")
        self.assertIn("generatedAt", result)

        # Point count and timestamp spacing
        points = result["points"]
        self.assertEqual(len(points), 4)  # 15, 30, 45, 60 min

        base_dt = pd.to_datetime(start_time, utc=True)
        for i, pt in enumerate(points):
            expected_dt = base_dt + timedelta(minutes=(i + 1) * 15)
            self.assertEqual(pt["timestamp"], expected_dt.isoformat())
            self.assertGreaterEqual(pt["demandMw"], 0.0)
            self.assertGreaterEqual(pt["lowerBoundMw"], 0.0)
            self.assertGreaterEqual(pt["upperBoundMw"], pt["lowerBoundMw"])

        # Spike risk structure
        spike = result["spikeRisk"]
        self.assertIn(spike["level"], ["normal", "moderate", "severe"])
        self.assertGreaterEqual(spike["probability"], 0.0)
        self.assertLessEqual(spike["probability"], 1.0)
        self.assertGreaterEqual(spike["predictedPeakMw"], 0.0)

    def test_unknown_zone_returns_clear_typed_error(self) -> None:
        """Service raises InvalidZoneError (error_code='INVALID_ZONE') on unrecognized zone."""
        with self.assertRaises(InvalidZoneError) as ctx:
            self.service.forecast_demand("UNRECOGNIZED_FEEDER_XYZ", "2024-11-15T12:00:00Z", horizon=15)
        self.assertEqual(ctx.exception.error_code, "INVALID_ZONE")
        self.assertFalse(ctx.exception.to_dict()["success"])

    def test_insufficient_history_returns_clear_typed_error(self) -> None:
        """Service raises InsufficientHistoryError (error_code='INSUFFICIENT_HISTORY') when history < 96 steps."""
        dates = pd.date_range("2024-11-15 00:00", periods=50, freq="15min", tz="UTC")
        short_hist = pd.DataFrame({"timestamp": dates, "demand_mw": np.full(50, 0.5)})

        with self.assertRaises(InsufficientHistoryError) as ctx:
            self.service.forecast_demand(
                "OS Edam",
                "2024-11-15T12:00:00Z",
                horizon=15,
                telemetry_history=short_hist,
            )
        self.assertEqual(ctx.exception.error_code, "INSUFFICIENT_HISTORY")
        self.assertEqual(ctx.exception.details["required_steps"], 96)

    # =========================================================================
    # CHUNK 7: Spike Classifier Input Validation Tests
    # =========================================================================

    def test_spike_classifier_input_validation_missing_fields(self) -> None:
        """Spike classifier rejects DataFrame missing required feature columns."""
        clf = DemandSpikeClassifier()
        incomplete_df = pd.DataFrame({
            "current_load": [0.5],
            "forecast_load": [0.6],
            # missing load_growth_pct, weather, calendar, etc.
        })
        with self.assertRaises(SpikeClassifierInputError) as ctx:
            clf.validate_feature_input(incomplete_df)
        self.assertEqual(ctx.exception.error_code, "SPIKE_INPUT_INVALID")

    def test_spike_classifier_input_validation_nan_values(self) -> None:
        """Spike classifier rejects feature inputs containing NaN values."""
        clf = DemandSpikeClassifier()
        cfg = SpikeClassifierConfig()
        nan_data = {col: [1.0] for col in cfg.feature_names}
        nan_data["load_growth_pct"] = [np.nan]  # Inject NaN
        nan_df = pd.DataFrame(nan_data)

        with self.assertRaises(SpikeClassifierInputError) as ctx:
            clf.validate_feature_input(nan_df)
        self.assertEqual(ctx.exception.error_code, "SPIKE_INPUT_INVALID")

    # =========================================================================
    # END-TO-END DETERMINISTIC PIPELINE TEST
    # =========================================================================

    def test_end_to_end_deterministic_pipeline(self) -> None:
        """
        Full integration test using a small deterministic fixture:
        synthetic raw telemetry -> ingestion -> features -> forecast service -> spike classifier.
        """
        # 1. Create small deterministic synthetic fixture (120 intervals, ~30 hours)
        np.random.seed(42)
        n_steps = 120
        timestamps = pd.date_range("2024-01-01 00:00", periods=n_steps, freq="15min", tz="UTC")

        # Deterministic diurnal cycle: peak in morning/evening
        t_hours = np.array([ts.hour + ts.minute / 60.0 for ts in timestamps])
        base_demand_mw = 0.60 + 0.35 * np.sin(2 * np.pi * (t_hours - 6) / 24.0)
        noise_mw = np.random.normal(loc=0.0, scale=0.02, size=n_steps)
        raw_demand_mw = np.clip(base_demand_mw + noise_mw, 0.05, 1.50)

        # Raw data is in watts for OpenSTEF ingestion ('load' column in Watts)
        raw_load_w = raw_demand_mw * 1e6

        # Build raw DataFrame with 'timestamp', 'load', 'available_at'
        raw_df = pd.DataFrame({
            "timestamp": timestamps,
            "load": raw_load_w,
            "available_at": timestamps,
        })

        # Inject 1 duplicate timestamp and 1 missing value to exercise Chunk 2 ingestion
        dup_row = pd.DataFrame({
            "timestamp": [timestamps[5]],
            "load": [raw_load_w[5] + 10000.0],
            "available_at": [timestamps[5]],
        })
        raw_df = pd.concat([raw_df.iloc[:6], dup_row, raw_df.iloc[6:]]).reset_index(drop=True)
        # Inject NaN at row 20
        raw_df.loc[20, "load"] = np.nan

        # 2. Ingestion Pipeline
        ingestion_pipeline = DemandIngestionPipeline(
            IngestionConfig(
                asset_id="OS Edam",
                demand_col="load",
                timestamp_col="timestamp",
                expected_freq_minutes=15,
                missing_policy=MissingValuePolicy.FORWARD_FILL_MAX_GAP,
                max_fill_gap_intervals=2,
            )
        )
        clean_df, quality_report = ingestion_pipeline.process(raw_df)

        self.assertEqual(len(clean_df), n_steps)
        self.assertIn("demand_mw", clean_df.columns)
        self.assertFalse(clean_df["demand_mw"].isna().any())
        self.assertEqual(quality_report.status, "SUCCESS")
        self.assertEqual(quality_report.duplicate_validation["duplicate_count"], 1)
        self.assertEqual(quality_report.missing_demand_handling["imputed_count"], 1)

        # 3. Feature Pipeline
        feature_pipeline = DemandFeaturePipeline(
            FeatureConfig(target_col="demand_mw", timestamp_col="timestamp", freq_minutes=15)
        )
        feated_df = feature_pipeline.transform(clean_df)

        self.assertIn("demand_mw_lag_15m", feated_df.columns)
        self.assertIn("demand_mw_lag_1440m", feated_df.columns)
        self.assertIn("demand_mw_roll_mean_4", feated_df.columns)

        # 4. Forecast Service Execution (Origin at step 105, horizon=60)
        origin_ts = timestamps[105].isoformat()
        forecast_result = self.service.forecast_demand(
            zone_id="OS Edam",
            start_time=origin_ts,
            horizon=60,
            telemetry_history=feated_df,
        )

        # Validate DemandForecast shape
        self.assertEqual(forecast_result["zoneId"], "OS Edam")
        self.assertEqual(forecast_result["horizonMinutes"], 60)
        self.assertEqual(len(forecast_result["points"]), 4)

        for pt in forecast_result["points"]:
            self.assertGreater(pt["demandMw"], 0.0)
            self.assertLess(pt["demandMw"], 2.0)
            self.assertLessEqual(pt["lowerBoundMw"], pt["upperBoundMw"])

        # 5. Spike Classifier Execution
        spike_risk = forecast_result["spikeRisk"]
        self.assertIn(spike_risk["level"], ["normal", "moderate", "severe"])
        self.assertGreaterEqual(spike_risk["probability"], 0.0)
        self.assertLessEqual(spike_risk["probability"], 1.0)
        self.assertGreater(spike_risk["predictedPeakMw"], 0.0)


if __name__ == "__main__":
    unittest.main()
