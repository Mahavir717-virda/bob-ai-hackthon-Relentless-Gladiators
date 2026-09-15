"""
GridPilot AI — Demand Forecast Service
======================================
Production inference service implementing the forecastDemand interface.
Loads pre-trained LightGBM multi-horizon models from ml/models/demand/
and strictly returns the frozen DemandForecast contract shape.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml

from services.forecasting.errors import (
    ForecastServiceError,
    InsufficientHistoryError,
    InvalidZoneError,
    MissingFeatureError,
    SpikeClassifierInputError,
    UnsupportedHorizonError,
)
from services.forecasting.features import DemandFeaturePipeline, FeatureConfig
from services.forecasting.models import DemandForecast, DemandForecastPoint, SpikeRisk

try:
    from ml.models.demand.spike_trainer import DemandSpikeClassifier
except ImportError:
    DemandSpikeClassifier = None  # type: ignore


class DemandForecastService:
    """
    Public service interface for electricity demand forecasting.

    Usage:
      service = DemandForecastService()
      forecast = service.forecast_demand(zone_id="OS Edam", start_time="2024-11-15T12:00:00Z", horizon=60)
    """

    SUPPORTED_HORIZONS = [15, 30, 60]
    REQUIRED_HISTORY_STEPS = 96  # 24 hours of 15-min intervals
    FREQ_MINUTES = 15

    def __init__(
        self,
        models_dir: Path | str = "./ml/models/demand",
        targets_yaml_path: Optional[Path | str] = None,
        canonical_data_path: Optional[Path | str] = "./ml/datasets/openstef_demand_features.parquet",
    ) -> None:
        self.models_dir = Path(models_dir)
        self.canonical_data_path = Path(canonical_data_path) if canonical_data_path else None
        self.models: Dict[int, lgb.Booster] = {}
        self.training_metadata: Dict[str, Any] = {}
        self.model_version = "demand-lgbm-v1"
        self.feature_version = "1.0.0"
        self.horizon_rmse: Dict[int, float] = {15: 0.0829, 30: 0.0972, 60: 0.1257}
        self.known_zones: set[str] = set()

        # 1. Load known zones catalog
        self._load_known_zones(targets_yaml_path)

        # 2. Load trained models & metadata
        self._load_models()

        # 3. Initialize feature pipeline
        self.feature_pipeline = DemandFeaturePipeline(
            FeatureConfig(
                target_col="demand_mw",
                timestamp_col="timestamp",
                freq_minutes=self.FREQ_MINUTES,
            )
        )

        # 4. In-memory history cache
        self._history_cache: Optional[pd.DataFrame] = None

        # 5. Initialize spike classifier (XGBoost)
        self.spike_classifier = None
        if DemandSpikeClassifier is not None:
            try:
                clf = DemandSpikeClassifier(models_dir=self.models_dir)
                clf.load_model()
                if clf.model is not None:
                    self.spike_classifier = clf
            except Exception:
                self.spike_classifier = None

    def _load_known_zones(self, targets_yaml_path: Optional[Path | str]) -> None:
        """Load known asset identifiers from targets YAML or default catalog."""
        # Default confirmed assets from Task 1 inspection
        default_zones = {
            "OS Edam",
            "OS Eibergen",
            "OS Gorredijk",
            "OS Almere",
            "OS Apeldoorn",
            "OS Bergum",
            "OS Amsterdam Hemweg",
            "OS Doetinchem",
            "NL_LIANDER_SUB_01",  # Canonical default test zone
        }
        self.known_zones = set(default_zones)

        # Check local targets yaml if available
        yaml_candidates = [
            Path(targets_yaml_path) if targets_yaml_path else None,
            Path("./liander2024_targets.yaml"),
            Path("./ml/datasets/liander2024_targets.yaml"),
        ]
        for p in yaml_candidates:
            if p and p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        targets = yaml.safe_load(f)
                    if isinstance(targets, list):
                        for t in targets:
                            if isinstance(t, dict) and "name" in t:
                                self.known_zones.add(t["name"])
                except Exception:
                    pass

    def _load_models(self) -> None:
        """Load trained LightGBM model boosters and metadata."""
        meta_file = self.models_dir / "demand-lgbm-v1_training_metadata.json"
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                self.training_metadata = json.load(f)
            self.model_version = self.training_metadata.get("model_version", "demand-lgbm-v1")
            self.feature_version = self.training_metadata.get("feature_version", "1.0.0")

            # Extract test RMSE per horizon for uncertainty intervals
            horizons_meta = self.training_metadata.get("horizons", {})
            for h_key, h_data in horizons_meta.items():
                h_min = h_data.get("horizon_minutes")
                rmse = h_data.get("test_metrics", {}).get("rmse")
                if h_min and rmse:
                    self.horizon_rmse[h_min] = float(rmse)

        # Load each horizon model booster
        for h in self.SUPPORTED_HORIZONS:
            txt_p = self.models_dir / f"{self.model_version}_h{h}min.txt"
            joblib_p = self.models_dir / f"{self.model_version}_h{h}min.joblib"

            if joblib_p.exists():
                self.models[h] = joblib.load(joblib_p)
            elif txt_p.exists():
                self.models[h] = lgb.Booster(model_file=str(txt_p))

    def _get_history(self, zone_id: str) -> pd.DataFrame:
        """Fetch or load historical telemetry for feature calculation."""
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
        Produce a demand forecast strictly conforming to the DemandForecast contract.

        Parameters
        ----------
        zone_id : str
            Target substation or feeder identifier.
        start_time : str | datetime
            Forecast origin timestamp (UTC ISO format).
        horizon : int
            Forecast horizon in minutes (15, 30, or 60).
        telemetry_history : pd.DataFrame, optional
            Historical 15-min telemetry. If None, retrieves from historical feature store.
        weather_forecast : pd.DataFrame, optional
            Optional weather forecast to align with future intervals.

        Returns
        -------
        Dict[str, Any]
            Dictionary matching shared/contracts/DemandForecast exactly.
        """
        # 1. Validate requested zone
        if zone_id not in self.known_zones:
            # Map canonical default to benchmark asset if needed
            if zone_id != "NL_LIANDER_SUB_01":
                raise InvalidZoneError(zone_id, list(self.known_zones))

        # 2. Validate requested horizon
        if horizon not in self.SUPPORTED_HORIZONS:
            raise UnsupportedHorizonError(horizon, self.SUPPORTED_HORIZONS)

        # 3. Parse and normalize start_time
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

        # 4. Validate history depth
        hist_df = telemetry_history if telemetry_history is not None else self._get_history(zone_id)
        if hist_df.empty:
            raise InsufficientHistoryError(zone_id, available_steps=0, required_steps=self.REQUIRED_HISTORY_STEPS)

        # Filter strictly to history <= start_dt
        hist_df = hist_df.copy()
        hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"], utc=True)
        prior_history = hist_df[hist_df["timestamp"] <= start_dt].sort_values("timestamp").reset_index(drop=True)

        if len(prior_history) < self.REQUIRED_HISTORY_STEPS:
            raise InsufficientHistoryError(
                zone_id,
                available_steps=len(prior_history),
                required_steps=self.REQUIRED_HISTORY_STEPS,
            )

        # 5. Extract latest row with features
        # If features already computed in prior_history, use directly; otherwise transform
        feature_cols = self.training_metadata.get("feature_names", [])
        has_features = all(c in prior_history.columns for c in feature_cols)

        if not has_features:
            feated_df = self.feature_pipeline.transform(prior_history, weather_df=weather_forecast)
        else:
            feated_df = prior_history.copy()

        # Ensure all expected feature columns exist (e.g. weather features if not provided)
        for c in feature_cols:
            if c not in feated_df.columns:
                feated_df[c] = 0.0

        latest_feature_row = feated_df.iloc[-1:].copy()

        # 6. Handle missing features explicitly (no silent zeroes for existing features)
        missing_in_row = [c for c in feature_cols if c in latest_feature_row.columns and latest_feature_row[c].isna().any()]
        if missing_in_row:
            # Documented fallback: try forward-filling from recent past steps (max 2 steps)
            recent_context = feated_df.iloc[-3:][feature_cols].ffill()
            latest_feature_row[feature_cols] = recent_context.iloc[-1:]
            still_missing = [c for c in missing_in_row if latest_feature_row[c].isna().any()]
            if still_missing:
                raise MissingFeatureError(still_missing, str(start_dt.isoformat()))

        X_input = latest_feature_row[feature_cols]

        # 7. Generate forecast points for all 15-min intervals up to horizon
        # Steps needed: horizon / 15
        steps = int(horizon / self.FREQ_MINUTES)
        points: List[DemandForecastPoint] = []

        for step in range(1, steps + 1):
            step_horizon_min = step * self.FREQ_MINUTES
            step_ts = start_dt + timedelta(minutes=step_horizon_min)
            step_ts_iso = step_ts.isoformat()

            # Select appropriate model:
            # If model for step_horizon_min is directly trained (15, 30, 60), use it
            # For 45 min, interpolate between 30 and 60 models
            if step_horizon_min in self.models:
                pred_mw = float(self.models[step_horizon_min].predict(X_input)[0])
                rmse = self.horizon_rmse.get(step_horizon_min, 0.10)
            elif step_horizon_min == 45:
                pred_30 = float(self.models[30].predict(X_input)[0]) if 30 in self.models else 0.0
                pred_60 = float(self.models[60].predict(X_input)[0]) if 60 in self.models else 0.0
                pred_mw = (pred_30 + pred_60) / 2.0
                rmse = (self.horizon_rmse.get(30, 0.10) + self.horizon_rmse.get(60, 0.12)) / 2.0
            else:
                pred_mw = float(self.models[min(self.SUPPORTED_HORIZONS, key=lambda x: abs(x - step_horizon_min))].predict(X_input)[0])
                rmse = 0.12

            # Compute confidence bounds (95% confidence ~ 1.96 * RMSE)
            pred_mw = max(0.0, pred_mw)
            lower_bound = max(0.0, pred_mw - 1.96 * rmse)
            upper_bound = pred_mw + 1.96 * rmse

            points.append(
                DemandForecastPoint(
                    timestamp=step_ts_iso,
                    demandMw=pred_mw,
                    lowerBoundMw=lower_bound,
                    upperBoundMw=upper_bound,
                )
            )

        # 8. Compute Spike Risk (conforms to SpikeRisk contract)
        peak_pred = max(p.demandMw for p in points)
        spike_level = "normal"
        spike_prob = 0.05

        if self.spike_classifier is not None and len(points) > 0:
            try:
                # Construct feature vector for classifier
                curr_mw = float(prior_history["demand_mw"].iloc[-1])
                fcst_mw = float(points[0].demandMw)
                eps = 0.10
                growth_pct = ((fcst_mw - curr_mw) / max(curr_mw, eps)) * 100.0
                peak_24h = float(prior_history["demand_mw"].tail(96).max())

                row_feat = {
                    "current_load": curr_mw,
                    "forecast_load": fcst_mw,
                    "load_growth_pct": growth_pct,
                    "historical_peak_24h": peak_24h,
                    "temp_c": float(latest_feature_row["temp_c"].iloc[0]) if "temp_c" in latest_feature_row.columns else 15.0,
                    "humidity": float(latest_feature_row["humidity"].iloc[0]) if "humidity" in latest_feature_row.columns else 70.0,
                    "cloud_cover": float(latest_feature_row["cloud_cover"].iloc[0]) if "cloud_cover" in latest_feature_row.columns else 50.0,
                    "wind_speed": float(latest_feature_row["wind_speed"].iloc[0]) if "wind_speed" in latest_feature_row.columns else 10.0,
                    "solar_radiation": float(latest_feature_row["solar_radiation"].iloc[0]) if "solar_radiation" in latest_feature_row.columns else 0.0,
                    "hour": int(start_dt.hour),
                    "hour_sin": float(np.sin(2 * np.pi * start_dt.hour / 24.0)),
                    "hour_cos": float(np.cos(2 * np.pi * start_dt.hour / 24.0)),
                    "day_of_week": int(start_dt.weekday()),
                    "is_weekend": int(start_dt.weekday() >= 5),
                }
                spike_input_df = pd.DataFrame([row_feat])
                preds, probas = self.spike_classifier.predict(spike_input_df)
                c_idx = int(preds[0])
                c_names = ["normal", "moderate", "severe"]
                spike_level = c_names[c_idx]
                spike_prob = float(probas[0][c_idx])
            except Exception:
                # Documented fallback if dynamic feature calculation encounters an edge condition
                upper_threshold = 1.40
                if peak_pred > upper_threshold * 1.2:
                    spike_level = "severe"
                    spike_prob = 0.85
                elif peak_pred > upper_threshold:
                    spike_level = "moderate"
                    spike_prob = 0.45
                else:
                    spike_level = "normal"
                    spike_prob = 0.05
        else:
            # Fallback based on historical quantile threshold
            upper_threshold = 1.40
            if peak_pred > upper_threshold * 1.2:
                spike_level = "severe"
                spike_prob = 0.85
            elif peak_pred > upper_threshold:
                spike_level = "moderate"
                spike_prob = 0.45
            else:
                spike_level = "normal"
                spike_prob = 0.05

        spike_risk = SpikeRisk(
            level=spike_level,
            probability=spike_prob,
            predictedPeakMw=peak_pred,
        )

        # 9. Assemble frozen DemandForecast contract
        forecast_response = DemandForecast(
            zoneId=zone_id,
            generatedAt=datetime.now(timezone.utc).isoformat(),
            horizonMinutes=horizon,
            points=points,
            spikeRisk=spike_risk,
            modelVersion=self.model_version,
        )

        return forecast_response.to_dict()

    # CamelCase alias matching TypeScript client conventions
    def forecastDemand(
        self,
        zoneId: str,
        startTime: Union[str, datetime],
        horizon: int = 60,
    ) -> Dict[str, Any]:
        """TypeScript-style camelCase invocation alias."""
        return self.forecast_demand(zone_id=zoneId, start_time=startTime, horizon=horizon)
