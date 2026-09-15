"""
GridPilot AI — Forecasting Service Typed Errors
================================================
Typed error hierarchy for the demand forecast service.
Ensures errors are explicitly typed and structured rather than raw exceptions.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ForecastServiceError(Exception):
    """Base exception for all forecasting service errors."""

    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Return structured machine-readable error dictionary."""
        return {
            "success": False,
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
            },
        }


class InvalidZoneError(ForecastServiceError):
    """Raised when the requested zone/substation is not recognized."""

    def __init__(self, zone_id: str, known_zones: Optional[list[str]] = None) -> None:
        super().__init__(
            message=f"Zone '{zone_id}' is not recognized or active in the grid topology.",
            error_code="INVALID_ZONE",
            details={"zone_id": zone_id, "known_zones_sample": (known_zones or [])[:5]},
        )


class InsufficientHistoryError(ForecastServiceError):
    """Raised when available historical telemetry is insufficient to compute lag/rolling features."""

    def __init__(self, zone_id: str, available_steps: int, required_steps: int = 96) -> None:
        super().__init__(
            message=(
                f"Insufficient historical data for zone '{zone_id}'. "
                f"Available: {available_steps} steps, required: {required_steps} steps (24 hours at 15-min frequency)."
            ),
            error_code="INSUFFICIENT_HISTORY",
            details={
                "zone_id": zone_id,
                "available_steps": available_steps,
                "required_steps": required_steps,
            },
        )


class UnsupportedHorizonError(ForecastServiceError):
    """Raised when an unsupported forecast horizon is requested."""

    def __init__(self, horizon_minutes: int, supported_horizons: Optional[list[int]] = None) -> None:
        supported = supported_horizons or [15, 30, 60]
        super().__init__(
            message=f"Horizon {horizon_minutes}m is unsupported. Supported horizons: {supported} minutes.",
            error_code="UNSUPPORTED_HORIZON",
            details={
                "requested_horizon": horizon_minutes,
                "supported_horizons": supported,
            },
        )


class MissingFeatureError(ForecastServiceError):
    """Raised when critical required predictor features cannot be computed or resolved."""

    def __init__(self, missing_features: list[str], timestamp: str) -> None:
        super().__init__(
            message=f"Missing required predictors at timestamp {timestamp}: {missing_features}.",
            error_code="MISSING_FEATURE",
            details={
                "missing_features": missing_features,
                "timestamp": timestamp,
            },
        )


class SpikeClassifierInputError(ForecastServiceError):
    """Raised when the spike classifier receives malformed or missing feature inputs."""

    def __init__(self, message: str, missing_or_invalid_fields: Optional[list[str]] = None) -> None:
        super().__init__(
            message=message,
            error_code="SPIKE_INPUT_INVALID",
            details={"fields": missing_or_invalid_fields or []},
        )

