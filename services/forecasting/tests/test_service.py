"""
GridPilot AI — Demand Forecast Service Unit Tests
==================================================
Validates that DemandForecastService conforms strictly to the frozen DemandForecast contract,
loads pre-trained LightGBM models, handles error conditions with typed errors,
and prevents leakage of internal ML implementation details.
"""

from datetime import datetime, timedelta, timezone
import unittest
import numpy as np
import pandas as pd

from services.forecasting.errors import (
    ForecastServiceError,
    InsufficientHistoryError,
    InvalidZoneError,
    MissingFeatureError,
    UnsupportedHorizonError,
)
from services.forecasting.service import DemandForecastService


class TestDemandForecastService(unittest.TestCase):
    """Test suite for DemandForecastService."""

    @classmethod
    def setUpClass(cls) -> None:
        """Initialize service instance once for tests."""
        cls.service = DemandForecastService()

    def test_service_initialization(self) -> None:
        """Service loads all horizon models and sets correct version tags."""
        self.assertEqual(self.service.model_version, "demand-lgbm-v1")
        self.assertEqual(self.service.feature_version, "1.0.0")
        for h in [15, 30, 60]:
            self.assertIn(h, self.service.models, f"Model for horizon {h}m should be loaded")
        self.assertIn("OS Edam", self.service.known_zones)
        self.assertIn("NL_LIANDER_SUB_01", self.service.known_zones)

    def test_forecast_demand_60min_contract_structure(self) -> None:
        """Forecast at 60m horizon returns contract-compliant structure with 4 points."""
        start_time = "2024-11-15T12:00:00Z"
        result = self.service.forecast_demand(
            zone_id="OS Edam",
            start_time=start_time,
            horizon=60,
        )

        # 1. Top-level contract keys
        expected_keys = {"zoneId", "generatedAt", "horizonMinutes", "points", "spikeRisk", "modelVersion"}
        self.assertEqual(set(result.keys()), expected_keys)
        self.assertEqual(result["zoneId"], "OS Edam")
        self.assertEqual(result["horizonMinutes"], 60)
        self.assertEqual(result["modelVersion"], "demand-lgbm-v1")

        # 2. Points verification (4 points for 60m horizon at 15m intervals)
        points = result["points"]
        self.assertEqual(len(points), 4)

        base_dt = pd.to_datetime(start_time, utc=True)
        for i, pt in enumerate(points):
            # Keys
            self.assertIn("timestamp", pt)
            self.assertIn("demandMw", pt)
            self.assertIn("lowerBoundMw", pt)
            self.assertIn("upperBoundMw", pt)

            # Timestamps
            expected_pt_dt = base_dt + timedelta(minutes=(i + 1) * 15)
            self.assertEqual(pt["timestamp"], expected_pt_dt.isoformat())

            # Constraints: demand >= 0, lower <= upper, lower >= 0
            self.assertGreaterEqual(pt["demandMw"], 0.0)
            self.assertGreaterEqual(pt["lowerBoundMw"], 0.0)
            self.assertGreaterEqual(pt["upperBoundMw"], pt["lowerBoundMw"])

        # 3. SpikeRisk verification
        spike = result["spikeRisk"]
        self.assertIn("level", spike)
        self.assertIn("probability", spike)
        self.assertIn("predictedPeakMw", spike)
        self.assertIn(spike["level"], ["normal", "moderate", "severe"])
        self.assertGreaterEqual(spike["probability"], 0.0)
        self.assertLessEqual(spike["probability"], 1.0)
        self.assertGreaterEqual(spike["predictedPeakMw"], 0.0)

    def test_forecast_demand_15min_and_30min_horizons(self) -> None:
        """Tests 15m (1 point) and 30m (2 points) horizons."""
        start_time = "2024-11-15T12:00:00Z"

        # 15 min
        res_15 = self.service.forecast_demand("OS Edam", start_time, horizon=15)
        self.assertEqual(res_15["horizonMinutes"], 15)
        self.assertEqual(len(res_15["points"]), 1)
        self.assertEqual(res_15["points"][0]["timestamp"], "2024-11-15T12:15:00+00:00")

        # 30 min
        res_30 = self.service.forecast_demand("OS Edam", start_time, horizon=30)
        self.assertEqual(res_30["horizonMinutes"], 30)
        self.assertEqual(len(res_30["points"]), 2)
        self.assertEqual(res_30["points"][0]["timestamp"], "2024-11-15T12:15:00+00:00")
        self.assertEqual(res_30["points"][1]["timestamp"], "2024-11-15T12:30:00+00:00")

    def test_camel_case_alias(self) -> None:
        """forecastDemand() camelCase alias matches forecast_demand()."""
        res = self.service.forecastDemand(
            zoneId="NL_LIANDER_SUB_01",
            startTime="2024-11-15T12:00:00Z",
            horizon=30,
        )
        self.assertEqual(res["zoneId"], "NL_LIANDER_SUB_01")
        self.assertEqual(len(res["points"]), 2)

    def test_invalid_zone_raises_typed_error(self) -> None:
        """Querying an unknown zone raises InvalidZoneError with error_code and details."""
        with self.assertRaises(InvalidZoneError) as ctx:
            self.service.forecast_demand("NON_EXISTENT_SUBSTATION", "2024-11-15T12:00:00Z", horizon=15)

        err = ctx.exception
        self.assertEqual(err.error_code, "INVALID_ZONE")
        self.assertEqual(err.details["zone_id"], "NON_EXISTENT_SUBSTATION")
        err_dict = err.to_dict()
        self.assertFalse(err_dict["success"])
        self.assertEqual(err_dict["error"]["code"], "INVALID_ZONE")

    def test_unsupported_horizon_raises_typed_error(self) -> None:
        """Requesting horizon not in [15, 30, 60] raises UnsupportedHorizonError."""
        for invalid_h in [5, 45, 90, 120]:
            with self.assertRaises(UnsupportedHorizonError) as ctx:
                self.service.forecast_demand("OS Edam", "2024-11-15T12:00:00Z", horizon=invalid_h)
            err = ctx.exception
            self.assertEqual(err.error_code, "UNSUPPORTED_HORIZON")
            self.assertEqual(err.details["requested_horizon"], invalid_h)

    def test_insufficient_history_raises_typed_error(self) -> None:
        """Providing fewer than 96 steps of history raises InsufficientHistoryError."""
        # Create tiny history of 50 steps
        timestamps = pd.date_range("2024-11-15 00:00", periods=50, freq="15min", tz="UTC")
        short_history = pd.DataFrame({
            "timestamp": timestamps,
            "demand_mw": np.random.uniform(0.5, 1.0, size=50),
        })

        with self.assertRaises(InsufficientHistoryError) as ctx:
            self.service.forecast_demand(
                zone_id="OS Edam",
                start_time="2024-11-15T12:00:00Z",
                horizon=15,
                telemetry_history=short_history,
            )

        err = ctx.exception
        self.assertEqual(err.error_code, "INSUFFICIENT_HISTORY")
        self.assertEqual(err.details["available_steps"], 49)  # up to 12:00:00 (index 48 = 12:00:00, 49 steps)
        self.assertEqual(err.details["required_steps"], 96)

    def test_no_internal_leakage(self) -> None:
        """Service response does not leak LightGBM booster objects or file paths."""
        res = self.service.forecast_demand("OS Edam", "2024-11-15T12:00:00Z", horizon=60)
        res_str = str(res)
        self.assertNotIn("Booster", res_str)
        self.assertNotIn("ml/models", res_str)
        self.assertNotIn("joblib", res_str)
        self.assertNotIn("filepath", res_str)


if __name__ == "__main__":
    unittest.main()
