"""
GridPilot AI — Services: Data Ingestion & Cleansing Module
==========================================================
Member 2 ownership: Data + Demand Forecasting.

Conforms to schema, units, frequencies, and policies documented in
docs/data/openstef-demand.md.
"""

from services.data.config import AssetCategory, IngestionConfig, MissingValuePolicy
from services.data.pipeline import DemandIngestionPipeline
from services.data.policies import MissingHandlingResult, handle_missing_demand
from services.data.quality_reporter import DataQualityReport
from services.data.schema import SchemaValidationResult, validate_schema
from services.data.validator import (
    DuplicateValidationResult,
    MissingIntervalResult,
    RangeValidationResult,
    TimestampValidationResult,
    detect_and_handle_duplicates,
    detect_missing_intervals,
    normalize_and_sort_timestamps,
    validate_numeric_ranges,
)

__all__ = [
    "IngestionConfig",
    "MissingValuePolicy",
    "AssetCategory",
    "DemandIngestionPipeline",
    "DataQualityReport",
    "SchemaValidationResult",
    "validate_schema",
    "handle_missing_demand",
    "MissingHandlingResult",
    "normalize_and_sort_timestamps",
    "TimestampValidationResult",
    "detect_and_handle_duplicates",
    "DuplicateValidationResult",
    "detect_missing_intervals",
    "MissingIntervalResult",
    "validate_numeric_ranges",
    "RangeValidationResult",
]
