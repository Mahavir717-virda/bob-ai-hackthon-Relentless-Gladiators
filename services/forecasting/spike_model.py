"""
GridPilot AI — Spike Inference Service
======================================
Inference service for upcoming demand spike classification using XGBoost.
Loads ml/models/demand/spike_xgb.pkl, computes leakage-free spike features,
validates inputs, and returns strictly typed SpikeRisk contracts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from services.forecasting.demand_features import SPIKE_FEATURE_NAMES, build_spike_features
from services.forecasting.errors import ForecastServiceError, SpikeClassifierInputError
from services.forecasting.model_loader import ModelLoader, default_loader
from services.forecasting.models import SpikeRisk

logger = logging.getLogger("gridpilot.forecasting.spike")


class SpikeModelService:
    """
    Inference service for demand spike detection.
    """

    CLASS_NAMES = ["normal", "moderate", "severe"]

    def __init__(
        self,
        models_dir: Path | str = "./ml/models/demand",
        model_loader: Optional[ModelLoader] = None,
    ) -> None:
        self.models_dir = Path(models_dir)
        self.loader = model_loader or default_loader
        self._model = None

    @property
    def model(self) -> Any:
        """Lazily retrieve cached trained model from loader."""
        if self._model is None:
            self._model = self.loader.get_spike_model()
        return self._model

    def validate_features(self, X: pd.DataFrame) -> None:
        """Validate that all required spike features exist and have no NaNs."""
        missing = [col for col in SPIKE_FEATURE_NAMES if col not in X.columns]
        if missing:
            raise SpikeClassifierInputError(
                message=f"Missing required feature columns for spike classifier: {missing}",
                missing_or_invalid_fields=missing,
            )

        nan_cols = [col for col in SPIKE_FEATURE_NAMES if X[col].isna().any()]
        if nan_cols:
            raise SpikeClassifierInputError(
                message=f"Spike features contain NaN values in: {nan_cols}",
                missing_or_invalid_fields=nan_cols,
            )

    def predict_spike(
        self,
        spike_features: pd.DataFrame,
        peak_forecast_mw: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Run inference using the trained XGBoost model.

        Parameters
        ----------
        spike_features : pd.DataFrame
            DataFrame containing rows matching SPIKE_FEATURE_NAMES.
        peak_forecast_mw : float, optional
            Predicted peak load in MW. If None, derived from features.

        Returns
        -------
        Dict[str, Any]
            SpikeRisk dictionary conforming to shared contract:
            {"level": "normal" | "moderate" | "severe", "probability": float, "predictedPeakMw": float}
        """
        self.validate_features(spike_features)

        X = spike_features[SPIKE_FEATURE_NAMES]
        model = self.model

        # Run model inference
        preds = model.predict(X)
        probs = model.predict_proba(X) if hasattr(model, "predict_proba") else None

        c_idx = int(preds[0])
        level = self.CLASS_NAMES[c_idx]

        if probs is not None:
            prob = float(probs[0][c_idx])
        else:
            prob = 1.0 if level != "normal" else 0.0

        if peak_forecast_mw is not None:
            peak_mw = float(peak_forecast_mw)
        else:
            peak_mw = float(spike_features["forecast_load"].iloc[0])

        risk = SpikeRisk(
            level=level,
            probability=round(prob, 4),
            predictedPeakMw=round(peak_mw, 2),
        )

        return risk.to_dict()

    def evaluate_telemetry(
        self,
        history_df: pd.DataFrame,
        predicted_next_mw: Optional[float] = None,
        latest_feature_row: Optional[pd.DataFrame] = None,
        peak_forecast_mw: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Full inference helper from telemetry history.
        """
        spike_feats = build_spike_features(
            history_df=history_df,
            predicted_next_mw=predicted_next_mw,
            latest_feature_row=latest_feature_row,
        )
        return self.predict_spike(spike_feats, peak_forecast_mw=peak_forecast_mw)
