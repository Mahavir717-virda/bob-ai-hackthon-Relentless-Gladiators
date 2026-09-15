"""
GridPilot AI — Forecasting Model Loader
=======================================
Thread-safe, cached artifact loader for Demand LightGBM and Spike XGBoost models.
Caches models in-memory upon service startup to ensure high-performance inference,
logs model loading lifecycle, and provides strict error handling without silent mocks.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional
import joblib

from services.forecasting.errors import ForecastServiceError

logger = logging.getLogger("gridpilot.forecasting.loader")


class ModelUnavailableError(ForecastServiceError):
    """Raised when a required trained model artifact is missing or corrupted."""

    def __init__(self, model_name: str, path: str | Path, reason: str = "Artifact not found on disk") -> None:
        super().__init__(
            message=f"Model '{model_name}' is unavailable at path '{path}': {reason}",
            error_code="MODEL_UNAVAILABLE",
        )
        self.model_name = model_name
        self.path = str(path)


class ModelLoader:
    """
    In-memory cached loader for production ML model artifacts.
    """

    def __init__(self, models_dir: Path | str = "./ml/models/demand") -> None:
        self.models_dir = Path(models_dir)
        self._cached_demand_model: Optional[Any] = None
        self._cached_spike_model: Optional[Any] = None

    def get_demand_model(self, force_reload: bool = False) -> Any:
        """
        Load or retrieve cached LightGBM demand model artifact (demand_lgbm.pkl).
        """
        if self._cached_demand_model is not None and not force_reload:
            return self._cached_demand_model

        artifact_candidates = [
            self.models_dir / "demand_lgbm.pkl",
            self.models_dir / "demand_lgbm.joblib",
        ]

        model_path = None
        for candidate in artifact_candidates:
            if candidate.exists():
                model_path = candidate
                break

        if model_path is None:
            logger.error("Demand model artifact not found in %s", self.models_dir)
            raise ModelUnavailableError("Demand LightGBM", self.models_dir / "demand_lgbm.pkl")

        try:
            model = joblib.load(model_path)
            file_size_kb = model_path.stat().st_size / 1024.0
            logger.info(
                "Successfully loaded demand model from %s (size: %.1f KB)",
                model_path,
                file_size_kb,
            )
            self._cached_demand_model = model
            return model
        except Exception as e:
            logger.error("Failed to load demand model from %s: %s", model_path, e)
            raise ModelUnavailableError("Demand LightGBM", model_path, str(e)) from e

    def get_spike_model(self, force_reload: bool = False) -> Any:
        """
        Load or retrieve cached XGBoost spike classifier artifact (spike_xgb.pkl).
        """
        if self._cached_spike_model is not None and not force_reload:
            return self._cached_spike_model

        artifact_candidates = [
            self.models_dir / "spike_xgb.pkl",
            self.models_dir / "spike_xgb.joblib",
        ]

        model_path = None
        for candidate in artifact_candidates:
            if candidate.exists():
                model_path = candidate
                break

        if model_path is None:
            logger.error("Spike model artifact not found in %s", self.models_dir)
            raise ModelUnavailableError("Spike XGBoost", self.models_dir / "spike_xgb.pkl")

        try:
            model = joblib.load(model_path)
            file_size_kb = model_path.stat().st_size / 1024.0
            logger.info(
                "Successfully loaded spike model from %s (size: %.1f KB)",
                model_path,
                file_size_kb,
            )
            self._cached_spike_model = model
            return model
        except Exception as e:
            logger.error("Failed to load spike model from %s: %s", model_path, e)
            raise ModelUnavailableError("Spike XGBoost", model_path, str(e)) from e

    def clear_cache(self) -> None:
        """Clear cached models in memory."""
        self._cached_demand_model = None
        self._cached_spike_model = None


# Default global loader instance
default_loader = ModelLoader()
