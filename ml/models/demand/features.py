"""
GridPilot AI — Demand Features Interface
=========================================
Re-exports the versioned DemandFeaturePipeline from services.forecasting.features
for ML models and experiments (Chunk 5 LightGBM, Chunk 7 Spike Classifier).
"""

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

__all__ = [
    "FEATURE_PIPELINE_VERSION",
    "DemandFeaturePipeline",
    "FeatureConfig",
    "is_dutch_holiday",
    "get_holiday_name",
    "DUTCH_HOLIDAYS_2024",
    "DUTCH_HOLIDAY_DATES_2024",
]
