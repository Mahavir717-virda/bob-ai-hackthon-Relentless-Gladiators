"""
GridPilot AI — Demand Forecasting Inference Service
===================================================
Inference service implementing multi-horizon electricity demand forecasting.
Loads the trained LightGBM model from ml/models/demand/demand_lgbm.pkl,
extracts past-only features via DemandFeaturePipeline, calculates prediction
uncertainty intervals, computes dynamic spike risk via SpikeModelService,
and returns the shared DemandForecast contract shape.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from services.forecasting.demand_features import DEMAND_FEATURE_NAMES, build_demand_features
from services.forecasting.errors import (
    ForecastServiceError,
    InsufficientHistoryError,
    InvalidZoneError,
    MissingFeatureError,
    UnsupportedHorizonError,
)
from services.forecasting.model_loader import ModelLoader, default_loader
from services.forecasting.models import DemandForecast, DemandForecastPoint, SpikeRisk
from services.forecasting.spike_model import SpikeModelService

logger = logging.getLogger("gridpilot.forecasting.demand")


class DemandLGBMModel:
    """
    Production container and multi-horizon predictor for LightGBM models.
    Supports single-horizon and multi-horizon predictions with column alignment.
    """

    def __init__(
        self,
        models: Dict[int, Any],
        feature_names: List[str],
        horizon_rmse: Optional[Dict[int, float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.models = models
        self.feature_names = feature_names
        self.horizon_rmse = horizon_rmse or {15: 0.0829, 30: 0.0972, 60: 0.1257}
        self.metadata = metadata or {}
        self.horizons = sorted(list(models.keys()))

    def predict(self, X: Any, horizon: int = 15) -> np.ndarray:
        """Run prediction for a specific horizon (15, 30, or 60 min)."""
        if horizon in self.models:
            booster = self.models[horizon]
        elif horizon == 45 and 30 in self.models and 60 in self.models:
            pred_30 = self.predict(X, horizon=30)
            pred_60 = self.predict(X, horizon=60)
            return (pred_30 + pred_60) / 2.0
        else:
            closest_h = min(self.horizons, key=lambda h: abs(h - horizon))
            booster = self.models[closest_h]

        if isinstance(X, pd.DataFrame):
            X_input = X.copy()
            for col in self.feature_names:
                if col not in X_input.columns:
                    X_input[col] = 0.0
            return booster.predict(X_input[self.feature_names])
        return booster.predict(X)

    def __getitem__(self, horizon: int) -> Any:
        return self.models[horizon]

    def __contains__(self, horizon: int) -> bool:
        return horizon in self.models


class DemandModelService:
    """
    Public inference service conforming strictly to the DemandForecast contract.
    """

    SUPPORTED_HORIZONS = [15, 30, 60]
    REQUIRED_HISTORY_STEPS = 96  # 24 hours of 15-minute intervals
    FREQ_MINUTES = 15

    def __init__(
        self,
        models_dir: Path | str = "./ml/models/demand",
        model_loader: Optional[ModelLoader] = None,
        canonical_data_path: Optional[Path | str] = "./ml/datasets/openstef_demand_features.parquet",
    ) -> None:
        self.models_dir = Path(models_dir)
        self.loader = model_loader or default_loader
        self.canonical_data_path = Path(canonical_data_path) if canonical_data_path else None
        self._history_cache: Optional[pd.DataFrame] = None
        self.model_version = "demand-lgbm-v1"

        # Known zone catalog
        self.known_zones: set[str] = {
            "OS Edam",
            "OS Eibergen",
            "OS Gorredijk",
            "OS Almere",
            "OS Apeldoorn",
            "OS Bergum",
            "OS Amsterdam Hemweg",
            "OS Doetinchem",
            "NL_LIANDER_SUB_01",
        }

        # Spike inference service
        self.spike_service = SpikeModelService(models_dir=self.models_dir, model_loader=self.loader)

    @property
    def model(self) -> DemandLGBMModel:
        """Lazily load cached model."""
        return self.loader.get_demand_model()

    def _get_history(self, zone_id: str) -> pd.DataFrame:
        """Fetch historical telemetry from feature store if available."""
        if self._history_cache is None and self.canonical_data_path and self.canonical_data_path.exists():
            self._history_cache = pd.read_parquet(self.canonical_data_path)
            self._history_cache["timestamp"] = pd.to_datetime(self._history_cache["timestamp"], utc=True)
            self._history_cache = self._history_cache.sort_values("timestamp").reset_index(drop=True)

        return self._history_cache if self._history_cache is not None else pd.DataFrame()

    def forecast_demand(
        self,
        zone_id: str,
        start_time: Union[str, datetime],
        horizon: int = 60,
        telemetry_history: Optional[pd.DataFrame] = None,
        weather_forecast: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Generate demand forecast conforming to DemandForecast contract.
        """
        # 1. Validate requested zone
        if zone_id not in self.known_zones and zone_id != "NL_LIANDER_SUB_01":
            raise InvalidZoneError(zone_id, list(self.known_zones))

        # 2. Validate horizon
        if horizon not in self.SUPPORTED_HORIZONS:
            raise UnsupportedHorizonError(horizon, self.SUPPORTED_HORIZONS)

        # 3. Parse timestamp
        if isinstance(start_time, str):
            try:
                start_dt = pd.to_datetime(start_time, utc=True).to_pydatetime()
            except Exception:
                raise ForecastServiceError(
                    message=f"Invalid start_time format: '{start_time}'. Must be valid ISO 8601 string.",
                    error_code="INVALID_TIMESTAMP",
                )
        elif isinstance(start_time, datetime):
            start_dt = start_time.astimezone(timezone.utc) if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        else:
            raise ForecastServiceError(
                message="start_time must be an ISO string or datetime object.",
                error_code="INVALID_TIMESTAMP",
            )

        # 4. Validate telemetry history
        hist_df = telemetry_history if telemetry_history is not None else self._get_history(zone_id)
        if hist_df.empty:
            raise InsufficientHistoryError(zone_id, available_steps=0, required_steps=self.REQUIRED_HISTORY_STEPS)

        hist_df = hist_df.copy()
        hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"], utc=True)
        prior_history = hist_df[hist_df["timestamp"] <= start_dt].sort_values("timestamp").reset_index(drop=True)

        if len(prior_history) < self.REQUIRED_HISTORY_STEPS:
            raise InsufficientHistoryError(
                zone_id,
                available_steps=len(prior_history),
                required_steps=self.REQUIRED_HISTORY_STEPS,
            )

        # 5. Extract feature vector
        lgbm_model = self.model
        feature_cols = getattr(lgbm_model, "feature_names", DEMAND_FEATURE_NAMES)
        has_features = all(c in prior_history.columns for c in feature_cols)

        if not has_features:
            feated_df = build_demand_features(prior_history, weather_df=weather_forecast)
        else:
            feated_df = prior_history.copy()

        for c in feature_cols:
            if c not in feated_df.columns:
                feated_df[c] = 0.0

        latest_feature_row = feated_df.iloc[-1:].copy()

        # Check for missing values
        missing_in_row = [c for c in feature_cols if latest_feature_row[c].isna().any()]
        if missing_in_row:
            recent_context = feated_df.iloc[-3:][feature_cols].ffill()
            latest_feature_row[feature_cols] = recent_context.iloc[-1:]
            still_missing = [c for c in missing_in_row if latest_feature_row[c].isna().any()]
            if still_missing:
                raise MissingFeatureError(still_missing, str(start_dt.isoformat()))

        X_input = latest_feature_row[feature_cols]

        # 6. Generate forecast points
        steps = int(horizon / self.FREQ_MINUTES)
        points: List[DemandForecastPoint] = []
        horizon_rmse = getattr(lgbm_model, "horizon_rmse", {15: 0.0829, 30: 0.0972, 60: 0.1257})

        for step in range(1, steps + 1):
            step_horizon_min = step * self.FREQ_MINUTES
            step_ts = start_dt + timedelta(minutes=step_horizon_min)
            step_ts_iso = step_ts.isoformat()

            pred_arr = lgbm_model.predict(X_input, horizon=step_horizon_min)
            pred_mw = float(pred_arr[0]) if isinstance(pred_arr, (np.ndarray, list)) else float(pred_arr)
            rmse = horizon_rmse.get(step_horizon_min, 0.10)

            # Confidence bounds: 95% (~ 1.96 * RMSE)
            pred_mw = max(0.0, pred_mw)
            lower_bound = max(0.0, pred_mw - 1.96 * rmse)
            upper_bound = pred_mw + 1.96 * rmse

            points.append(
                DemandForecastPoint(
                    timestamp=step_ts_iso,
                    demandMw=round(pred_mw, 3),
                    lowerBoundMw=round(lower_bound, 3),
                    upperBoundMw=round(upper_bound, 3),
                )
            )

        # 7. Evaluate Spike Risk
        peak_pred = max(p.demandMw for p in points)
        pred_15m = points[0].demandMw if points else None

        spike_risk_dict = self.spike_service.evaluate_telemetry(
            history_df=prior_history,
            predicted_next_mw=pred_15m,
            latest_feature_row=latest_feature_row,
            peak_forecast_mw=peak_pred,
        )

        spike_risk = SpikeRisk(
            level=spike_risk_dict["level"],
            probability=spike_risk_dict["probability"],
            predictedPeakMw=spike_risk_dict["predictedPeakMw"],
        )

        # 8. Assemble DemandForecast response
        forecast_response = DemandForecast(
            zoneId=zone_id,
            generatedAt=datetime.now(timezone.utc).isoformat(),
            horizonMinutes=horizon,
            points=points,
            spikeRisk=spike_risk,
            modelVersion=self.model_version,
        )

        return forecast_response.to_dict()

    def forecastDemand(
        self,
        zoneId: str,
        startTime: Union[str, datetime],
        horizon: int = 60,
    ) -> Dict[str, Any]:
        """TypeScript camelCase alias."""
        return self.forecast_demand(zone_id=zoneId, start_time=startTime, horizon=horizon)
