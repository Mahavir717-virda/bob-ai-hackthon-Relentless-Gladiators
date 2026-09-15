"""
GridPilot AI — Demand Data Ingestion Configuration
===================================================
Defines field contracts, physical numeric limits, sampling frequencies,
and missing value policies based strictly on confirmed findings in
docs/data/openstef-demand.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MissingValuePolicy(str, Enum):
    """
    Explicit policies for handling missing demand values.
    Silent interpolation is strictly forbidden.
    """
    LEAVE_AS_NULL = "leave_as_null"
    FORWARD_FILL_MAX_GAP = "forward_fill_max_gap"
    DROP = "drop"


class AssetCategory(str, Enum):
    """Confirmed asset groups from liander2024_targets.yaml."""
    MV_FEEDER = "mv_feeder"
    STATION_INSTALLATION = "station_installation"
    TRANSFORMER = "transformer"
    SOLAR_PARK = "solar_park"
    WIND_PARK = "wind_park"


@dataclass(frozen=True)
class IngestionConfig:
    """
    Configuration parameters for demand data ingestion pipeline.
    """
    # Temporal contracts
    expected_freq: str = "15min"
    expected_freq_minutes: int = 15
    expected_timezone: str = "UTC"

    # Confirmed core columns (docs/data/openstef-demand.md)
    timestamp_col: str = "timestamp"
    demand_col: str = "load"
    available_at_col: str = "available_at"

    # Plausible physical limits (Watts for substations/feeders/transformers)
    # Allows reverse power flow up to -500 MW and forward consumption up to +500 MW
    min_load_watts: float = -500e6
    max_load_watts: float = 500e6

    # Normalized limits for solar_park / wind_park (normalized capacity ratio)
    min_normalized_load: float = -1.05
    max_normalized_load: float = 0.05

    # Missing value policy configuration
    missing_policy: MissingValuePolicy = MissingValuePolicy.FORWARD_FILL_MAX_GAP
    max_fill_gap_intervals: int = 4  # max 1 hour gap (4 x 15-min)

    # Asset context
    asset_id: Optional[str] = None
    group_name: AssetCategory = AssetCategory.MV_FEEDER
    upper_limit_watts: Optional[float] = None
    lower_limit_watts: Optional[float] = None

    @property
    def is_normalized_renewable(self) -> bool:
        """Returns True if the asset is a normalized solar or wind park."""
        return self.group_name in (AssetCategory.SOLAR_PARK, AssetCategory.WIND_PARK)

    @property
    def plausible_min(self) -> float:
        return self.min_normalized_load if self.is_normalized_renewable else self.min_load_watts

    @property
    def plausible_max(self) -> float:
        return self.max_normalized_load if self.is_normalized_renewable else self.max_load_watts
