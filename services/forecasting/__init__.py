"""
GridPilot AI — Forecasting Service Module
=========================================
Member 2 ownership: Demand Forecasting & Spike Detection.
"""

from services.forecasting.baselines import (
    PersistenceForecaster,
    SeasonalNaiveForecaster,
    evaluate_baselines_on_split,
)
from services.forecasting.errors import (
    ForecastServiceError,
    InsufficientHistoryError,
    InvalidZoneError,
    MissingFeatureError,
    SpikeClassifierInputError,
    UnsupportedHorizonError,
)
from services.forecasting.evaluate import (
    ChronologicalSplitResult,
    calculate_metrics,
    chronological_split,
)
from services.forecasting.features import (
    FEATURE_PIPELINE_VERSION,
    DemandFeaturePipeline,
    FeatureConfig,
)
from services.forecasting.holidays import (
    DUTCH_HOLIDAYS_2024,
    DUTCH_HOLIDAY_DATES_2024,
    get_holiday_name,
    is_dutch_holiday,
)
from services.forecasting.models import (
    DemandForecast,
    DemandForecastPoint,
    SpikeRisk,
)
from services.forecasting.service import DemandForecastService

__all__ = [
    "FEATURE_PIPELINE_VERSION",
    "DemandFeaturePipeline",
    "FeatureConfig",
    "PersistenceForecaster",
    "SeasonalNaiveForecaster",
    "evaluate_baselines_on_split",
    "chronological_split",
    "calculate_metrics",
    "ChronologicalSplitResult",
    "is_dutch_holiday",
    "get_holiday_name",
    "DUTCH_HOLIDAYS_2024",
    "DUTCH_HOLIDAY_DATES_2024",
    "DemandForecastService",
    "DemandForecast",
    "DemandForecastPoint",
    "SpikeRisk",
    "ForecastServiceError",
    "InvalidZoneError",
    "InsufficientHistoryError",
    "UnsupportedHorizonError",
    "MissingFeatureError",
    "SpikeClassifierInputError",
]

