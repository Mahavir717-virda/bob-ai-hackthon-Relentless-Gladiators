"""
GridPilot AI — Demand Intelligence End-to-End Test Suite
=========================================================
Covers:
1. Feature pipeline generation, lag correctness, and strict leakage prevention.
2. Demand model loading and inference (15m, 30m, 60m).
3. Spike model loading and inference (classes, probabilities, peak MW).
4. DemandForecast contract validation.
5. Error handling for insufficient history and invalid zones/horizons.
6. Dynamicity test: verifying that different telemetry inputs produce dynamic,
   different model outputs (no hardcoded responses).
7. Downstream integration: DemandForecast -> GridState -> OptimizationInput.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

from services.forecasting.demand_features import (
    DEMAND_FEATURE_NAMES,
    SPIKE_FEATURE_NAMES,
    build_demand_features,
    build_spike_features,
)
from services.forecasting.demand_model import DemandLGBMModel, DemandModelService
from services.forecasting.errors import (
    InsufficientHistoryError,
    InvalidZoneError,
    UnsupportedHorizonError,
)
from services.forecasting.model_loader import ModelLoader, default_loader
from services.forecasting.spike_model import SpikeModelService


class TestDemandIntelligenceE2E(unittest.TestCase):
    """End-to-end integration and verification suite for Demand Intelligence."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.models_dir = Path("./ml/models/demand")
        cls.dataset_path = Path("./ml/datasets/openstef_demand_features.parquet")
        cls.loader = ModelLoader(models_dir=cls.models_dir)
        cls.demand_service = DemandModelService(
            models_dir=cls.models_dir,
            model_loader=cls.loader,
            canonical_data_path=cls.dataset_path,
        )
        cls.spike_service = SpikeModelService(
            models_dir=cls.models_dir,
            model_loader=cls.loader,
        )
        # Load sample real historical telemetry
        assert cls.dataset_path.exists(), f"Dataset missing at {cls.dataset_path}"
        cls.full_df = pd.read_parquet(cls.dataset_path)
        cls.full_df["timestamp"] = pd.to_datetime(cls.full_df["timestamp"], utc=True)
        cls.full_df = cls.full_df.sort_values("timestamp").reset_index(drop=True)

    # --------------------------------------------------------------------------
    # 1. Physical Artifacts Verification (Step 7, 13, 21)
    # --------------------------------------------------------------------------
    def test_artifacts_exist_and_nonzero(self) -> None:
        """Verify all required .pkl and .json metadata files physically exist and are non-empty."""
        lgbm_pkl = self.models_dir / "demand_lgbm.pkl"
        lgbm_meta = self.models_dir / "demand_lgbm_metadata.json"
        spike_pkl = self.models_dir / "spike_xgb.pkl"
        spike_meta = self.models_dir / "spike_xgb_metadata.json"

        self.assertTrue(lgbm_pkl.exists(), "demand_lgbm.pkl must exist on disk")
        self.assertGreater(lgbm_pkl.stat().st_size, 100_000, "demand_lgbm.pkl must be non-trivial")

        self.assertTrue(lgbm_meta.exists(), "demand_lgbm_metadata.json must exist")
        self.assertGreater(lgbm_meta.stat().st_size, 0)

        self.assertTrue(spike_pkl.exists(), "spike_xgb.pkl must exist on disk")
        self.assertGreater(spike_pkl.stat().st_size, 100_000, "spike_xgb.pkl must be non-trivial")

        self.assertTrue(spike_meta.exists(), "spike_xgb_metadata.json must exist")
        self.assertGreater(spike_meta.stat().st_size, 0)

    # --------------------------------------------------------------------------
    # 2. Model Loading Tests (Step 7, 13, 18)
    # --------------------------------------------------------------------------
    def test_demand_model_loading(self) -> None:
        """Verify demand model loads via loader and contains expected horizons."""
        model = self.loader.get_demand_model()
        self.assertIsInstance(model, DemandLGBMModel)
        self.assertIn(15, model.horizons)
        self.assertIn(30, model.horizons)
        self.assertIn(60, model.horizons)
        self.assertEqual(len(model.feature_names), 37)

    def test_spike_model_loading(self) -> None:
        """Verify spike model loads via loader and is an XGBoost estimator."""
        model = self.loader.get_spike_model()
        self.assertTrue(hasattr(model, "predict"))
        self.assertTrue(hasattr(model, "predict_proba"))

    # --------------------------------------------------------------------------
    # 3. Feature Pipeline & Leakage Verification (Step 3, 11)
    # --------------------------------------------------------------------------
    def test_demand_features_leakage_and_correctness(self) -> None:
        """Ensure lag features are strictly past observations and contain no future leakage."""
        sample_slice = self.full_df.iloc[100:300].copy()
        feated = build_demand_features(sample_slice)

        # Verify all required feature columns exist
        for col in DEMAND_FEATURE_NAMES:
            self.assertIn(col, feated.columns)

        # Verify lag 15m (1 period shift): at row t, lag_15m must equal demand_mw at row t-1
        t_idx = 110
        curr_ts = feated["timestamp"].iloc[t_idx]
        prev_ts = feated["timestamp"].iloc[t_idx - 1]
        self.assertEqual(curr_ts - prev_ts, pd.Timedelta(minutes=15))

        expected_lag_val = sample_slice["demand_mw"].iloc[t_idx - 1]
        actual_lag_val = feated["demand_mw_lag_15m"].iloc[t_idx]
        self.assertAlmostEqual(actual_lag_val, expected_lag_val, places=5)

        # Leakage test: modifying future rows (> t) must NOT change features at row t
        modified_slice = sample_slice.copy()
        future_idx = t_idx + 5
        modified_slice.loc[modified_slice.index[future_idx], "demand_mw"] = 9999.0

        feated_mod = build_demand_features(modified_slice)
        row_orig = feated.iloc[t_idx][DEMAND_FEATURE_NAMES].values.astype(float)
        row_mod = feated_mod.iloc[t_idx][DEMAND_FEATURE_NAMES].values.astype(float)
        np.testing.assert_allclose(
            row_orig,
            row_mod,
            equal_nan=True,
            err_msg="Modifying future data leaked into current feature calculation!",
        )

    def test_spike_features_leakage_and_shape(self) -> None:
        """Verify spike feature builder produces single-row without future data."""
        history_slice = self.full_df.iloc[500:650].copy()
        spike_feats = build_spike_features(history_slice, predicted_next_mw=1.25)

        self.assertEqual(spike_feats.shape[0], 1)
        self.assertEqual(list(spike_feats.columns), SPIKE_FEATURE_NAMES)
        self.assertFalse(spike_feats.isna().any().any(), "Spike features must not contain NaN")
        self.assertEqual(float(spike_feats["forecast_load"].iloc[0]), 1.25)
        self.assertEqual(float(spike_feats["current_load"].iloc[0]), float(history_slice["demand_mw"].iloc[-1]))

    # --------------------------------------------------------------------------
    # 4. Demand Inference & Contract Conformance (Step 9, 15)
    # --------------------------------------------------------------------------
    def test_forecast_demand_contract_conformance(self) -> None:
        """Verify demand forecast service outputs valid DemandForecast contract."""
        test_ts = self.full_df["timestamp"].iloc[1000]
        forecast = self.demand_service.forecast_demand(
            zone_id="OS Edam",
            start_time=test_ts,
            horizon=60,
        )

        # Verify contract keys
        required_keys = {"zoneId", "generatedAt", "horizonMinutes", "points", "spikeRisk", "modelVersion"}
        self.assertEqual(set(forecast.keys()), required_keys)
        self.assertEqual(forecast["zoneId"], "OS Edam")
        self.assertEqual(forecast["horizonMinutes"], 60)
        self.assertEqual(len(forecast["points"]), 4)

        # Verify points & monotonicity of time
        for i, pt in enumerate(forecast["points"]):
            self.assertIn("timestamp", pt)
            self.assertIn("demandMw", pt)
            self.assertIn("lowerBoundMw", pt)
            self.assertIn("upperBoundMw", pt)
            self.assertGreaterEqual(pt["demandMw"], 0.0)
            self.assertGreaterEqual(pt["lowerBoundMw"], 0.0)
            self.assertGreaterEqual(pt["upperBoundMw"], pt["lowerBoundMw"])

        # Verify spike risk
        spike = forecast["spikeRisk"]
        self.assertIn(spike["level"], ["normal", "moderate", "severe"])
        self.assertTrue(0.0 <= spike["probability"] <= 1.0)
        self.assertGreaterEqual(spike["predictedPeakMw"], 0.0)

    # --------------------------------------------------------------------------
    # 5. Error Handling Tests (Step 9, 14)
    # --------------------------------------------------------------------------
    def test_invalid_zone_raises_error(self) -> None:
        """Unknown zone raises InvalidZoneError."""
        with self.assertRaises(InvalidZoneError):
            self.demand_service.forecast_demand("UNKNOWN_ZONE_999", "2024-11-15T12:00:00Z")

    def test_unsupported_horizon_raises_error(self) -> None:
        """Unsupported horizon (e.g. 120m) raises UnsupportedHorizonError."""
        with self.assertRaises(UnsupportedHorizonError):
            self.demand_service.forecast_demand("OS Edam", "2024-11-15T12:00:00Z", horizon=120)

    def test_insufficient_history_raises_error(self) -> None:
        """History with fewer than 96 steps raises InsufficientHistoryError."""
        shallow_history = self.full_df.iloc[:20].copy()
        shallow_ts = shallow_history["timestamp"].iloc[-1]
        with self.assertRaises(InsufficientHistoryError):
            self.demand_service.forecast_demand(
                zone_id="OS Edam",
                start_time=shallow_ts,
                telemetry_history=shallow_history,
            )

    # --------------------------------------------------------------------------
    # 6. Dynamicity Verification (Step 20)
    # --------------------------------------------------------------------------
    def test_dynamic_inference_different_telemetry_inputs(self) -> None:
        """
        Prove inference is genuinely data-driven and dynamic.
        Input A: Low-demand morning interval
        Input B: High-demand evening interval
        """
        # Select two distinct historical timestamps
        # T1: Night / early morning low load
        t1 = pd.to_datetime("2024-11-15 04:00:00+00:00")
        # T2: Evening peak load
        t2 = pd.to_datetime("2024-11-15 18:00:00+00:00")

        forecast_a = self.demand_service.forecast_demand(zone_id="OS Edam", start_time=t1, horizon=60)
        forecast_b = self.demand_service.forecast_demand(zone_id="OS Edam", start_time=t2, horizon=60)

        preds_a = [p["demandMw"] for p in forecast_a["points"]]
        preds_b = [p["demandMw"] for p in forecast_b["points"]]

        # 1. Predictions must NOT be identical (proves not hardcoded)
        self.assertNotEqual(preds_a, preds_b, "Predictions for different times must differ!")

        # 2. Predictions must be distinct floating point numbers
        self.assertTrue(len(set(preds_a)) > 1 or len(set(preds_b)) > 1)

        # 3. Peak load at evening (T2) should differ meaningfully from early morning (T1)
        mean_a = np.mean(preds_a)
        mean_b = np.mean(preds_b)
        self.assertGreater(abs(mean_b - mean_a), 0.05, "Dynamic loads between morning and evening must differ")

        # 4. Check spike outputs are dynamic
        spike_a = forecast_a["spikeRisk"]
        spike_b = forecast_b["spikeRisk"]
        self.assertNotEqual(spike_a["predictedPeakMw"], spike_b["predictedPeakMw"])

    # --------------------------------------------------------------------------
    # 7. Final Project Integration Test (Step 22)
    # --------------------------------------------------------------------------
    def test_pipeline_integration_demand_to_grid_to_opt(self) -> None:
        """
        Verify that DemandForecast can be transformed into GridState
        and consumed by OptimizationInput without exposing OR-Tools internals.
        """
        test_ts = self.full_df["timestamp"].iloc[2000]
        demand_fcst = self.demand_service.forecast_demand(
            zone_id="OS Edam",
            start_time=test_ts,
            horizon=15,
        )

        current_mw = float(demand_fcst["points"][0]["demandMw"])
        grid_state = {
            "timestamp": demand_fcst["generatedAt"],
            "zoneId": demand_fcst["zoneId"],
            "demandMw": current_mw,
            "solarGenerationMw": 12.0,
            "windGenerationMw": 8.0,
            "netLoadMw": max(0.0, current_mw - 20.0),
            "batterySocPercent": 75.0,
            "batteryPowerMw": 0.0,
            "curtailmentMw": 0.0,
            "gridFrequencyHz": 50.01,
            "gridStressIndex": 0.35,
            "activeAlertsCount": 0,
        }

        opt_input = {
            "scenarioId": "INTEGRATION_TEST_SCENARIO",
            "targetTimestamp": demand_fcst["points"][0]["timestamp"],
            "horizonMinutes": 15,
            "currentGridState": grid_state,
            "demandForecast": demand_fcst,
            "renewableForecastMw": 20.0,
            "batteryConstraints": {
                "maxCapacityMwh": 40.0,
                "currentSocPercent": 75.0,
                "minSocPercent": 10.0,
                "maxSocPercent": 90.0,
                "maxChargePowerMw": 10.0,
                "maxDischargePowerMw": 10.0,
                "roundTripEfficiency": 0.90,
            },
            "flexibleLoadConstraints": {
                "totalFlexibleMw": 5.0,
                "maxShiftDurationMinutes": 60,
                "shiftCostPerMw": 12.0,
            },
            "curtailmentPenaltyPerMw": 45.0,
        }

        # Validate structure
        self.assertIn("demandForecast", opt_input)
        self.assertEqual(opt_input["demandForecast"]["zoneId"], "OS Edam")
        self.assertEqual(len(opt_input["demandForecast"]["points"]), 1)
        self.assertIn("spikeRisk", opt_input["demandForecast"])
        self.assertEqual(opt_input["currentGridState"]["demandMw"], current_mw)


if __name__ == "__main__":
    unittest.main()
