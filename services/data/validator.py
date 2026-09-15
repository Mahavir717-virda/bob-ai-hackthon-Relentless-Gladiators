"""
GridPilot AI — Data Validation and Cleaning Module
==================================================
Performs:
  - Timestamp normalization to UTC
  - Monotonic sorting
  - Duplicate timestamp detection and resolution
  - Missing interval (grid gap) detection at 15-minute frequency
  - Physical numeric range validation and flagging
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from services.data.config import IngestionConfig


@dataclass
class TimestampValidationResult:
    """Audit metrics for timestamp normalization and sorting."""
    total_rows: int
    invalid_timestamps_count: int
    invalid_timestamps_pct: float
    min_timestamp: Optional[str] = None
    max_timestamp: Optional[str] = None
    is_monotonic: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "invalid_timestamps_count": self.invalid_timestamps_count,
            "invalid_timestamps_pct": round(self.invalid_timestamps_pct, 4),
            "min_timestamp": self.min_timestamp,
            "max_timestamp": self.max_timestamp,
            "is_monotonic": self.is_monotonic,
        }


@dataclass
class DuplicateValidationResult:
    """Audit metrics for duplicate timestamps."""
    duplicate_count: int
    duplicate_pct: float
    dropped_duplicates: int
    duplicate_timestamps_sample: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duplicate_count": self.duplicate_count,
            "duplicate_pct": round(self.duplicate_pct, 4),
            "dropped_duplicates": self.dropped_duplicates,
            "duplicate_timestamps_sample": self.duplicate_timestamps_sample,
        }


@dataclass
class MissingIntervalResult:
    """Audit metrics for missing intervals (sampling gaps)."""
    expected_freq: str
    expected_intervals: int
    actual_intervals: int
    missing_intervals_count: int
    missing_intervals_pct: float
    gap_events_count: int
    gap_timestamps_sample: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expected_freq": self.expected_freq,
            "expected_intervals": self.expected_intervals,
            "actual_intervals": self.actual_intervals,
            "missing_intervals_count": self.missing_intervals_count,
            "missing_intervals_pct": round(self.missing_intervals_pct, 4),
            "gap_events_count": self.gap_events_count,
            "gap_timestamps_sample": self.gap_timestamps_sample,
        }


@dataclass
class RangeValidationResult:
    """Audit metrics for physical numeric ranges."""
    total_evaluated: int
    min_allowed: float
    max_allowed: float
    min_observed: Optional[float]
    max_observed: Optional[float]
    out_of_range_count: int
    out_of_range_pct: float
    negative_load_count: int
    negative_load_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_evaluated": self.total_evaluated,
            "min_allowed": self.min_allowed,
            "max_allowed": self.max_allowed,
            "min_observed": self.min_observed,
            "max_observed": self.max_observed,
            "out_of_range_count": self.out_of_range_count,
            "out_of_range_pct": round(self.out_of_range_pct, 4),
            "negative_load_count": self.negative_load_count,
            "negative_load_pct": round(self.negative_load_pct, 4),
        }


def normalize_and_sort_timestamps(
    df: pd.DataFrame,
    config: IngestionConfig,
) -> Tuple[pd.DataFrame, TimestampValidationResult]:
    """
    Normalize timestamps to UTC, reject unparseables, and sort chronologically.
    """
    df = df.copy()
    ts_col = config.timestamp_col

    if ts_col not in df.columns and isinstance(df.index, pd.DatetimeIndex):
        df[ts_col] = df.index

    # Parse to datetime
    parsed_ts = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
    invalid_mask = parsed_ts.isna()
    invalid_count = int(invalid_mask.sum())
    total_rows = len(df)
    invalid_pct = (invalid_count / total_rows * 100.0) if total_rows > 0 else 0.0

    if invalid_count > 0:
        # Drop unparseable timestamp rows
        df = df[~invalid_mask].copy()
        parsed_ts = parsed_ts[~invalid_mask]

    df[ts_col] = parsed_ts

    # Sort chronologically
    df = df.sort_values(ts_col).reset_index(drop=True)

    min_ts = str(df[ts_col].min()) if len(df) > 0 else None
    max_ts = str(df[ts_col].max()) if len(df) > 0 else None
    is_monotonic = bool(df[ts_col].is_monotonic_increasing)

    result = TimestampValidationResult(
        total_rows=total_rows,
        invalid_timestamps_count=invalid_count,
        invalid_timestamps_pct=invalid_pct,
        min_timestamp=min_ts,
        max_timestamp=max_ts,
        is_monotonic=is_monotonic,
    )
    return df, result


def detect_and_handle_duplicates(
    df: pd.DataFrame,
    config: IngestionConfig,
    keep: str = "first",
) -> Tuple[pd.DataFrame, DuplicateValidationResult]:
    """
    Detect duplicate timestamps and deduplicate keeping the specified occurrence.
    """
    df = df.copy()
    ts_col = config.timestamp_col
    total_rows = len(df)

    duplicate_mask = df.duplicated(subset=[ts_col], keep=False)
    duplicate_count = int(df.duplicated(subset=[ts_col]).sum())
    duplicate_pct = (duplicate_count / total_rows * 100.0) if total_rows > 0 else 0.0

    dupe_samples: List[str] = []
    if duplicate_count > 0:
        dupe_samples = [str(ts) for ts in df.loc[duplicate_mask, ts_col].unique()[:10]]
        # Deduplicate
        df = df.drop_duplicates(subset=[ts_col], keep=keep).reset_index(drop=True)

    result = DuplicateValidationResult(
        duplicate_count=duplicate_count,
        duplicate_pct=duplicate_pct,
        dropped_duplicates=duplicate_count,
        duplicate_timestamps_sample=dupe_samples,
    )
    return df, result


def detect_missing_intervals(
    df: pd.DataFrame,
    config: IngestionConfig,
) -> MissingIntervalResult:
    """
    Detect missing intervals (gaps) against the expected uniform sampling frequency (15min).
    """
    ts_col = config.timestamp_col
    if len(df) < 2:
        return MissingIntervalResult(
            expected_freq=config.expected_freq,
            expected_intervals=len(df),
            actual_intervals=len(df),
            missing_intervals_count=0,
            missing_intervals_pct=0.0,
            gap_events_count=0,
        )

    ts_series = df[ts_col].sort_values()
    start_ts = ts_series.iloc[0]
    end_ts = ts_series.iloc[-1]

    # Generate complete reference grid
    expected_index = pd.date_range(
        start=start_ts,
        end=end_ts,
        freq=config.expected_freq,
        tz="UTC",
    )
    expected_count = len(expected_index)
    actual_count = len(ts_series)

    # Missing timestamps in grid
    missing_in_grid = expected_index.difference(pd.DatetimeIndex(ts_series))
    missing_count = len(missing_in_grid)
    missing_pct = (missing_count / expected_count * 100.0) if expected_count > 0 else 0.0

    # Irregular intervals (gaps > expected_freq)
    deltas = ts_series.diff().dropna()
    expected_delta = pd.Timedelta(minutes=config.expected_freq_minutes)
    gap_deltas = deltas[deltas != expected_delta]
    gap_events_count = len(gap_deltas)

    gap_samples = [str(ts) for ts in missing_in_grid[:10]]

    return MissingIntervalResult(
        expected_freq=config.expected_freq,
        expected_intervals=expected_count,
        actual_intervals=actual_count,
        missing_intervals_count=missing_count,
        missing_intervals_pct=missing_pct,
        gap_events_count=gap_events_count,
        gap_timestamps_sample=gap_samples,
    )


def validate_numeric_ranges(
    df: pd.DataFrame,
    config: IngestionConfig,
) -> Tuple[pd.DataFrame, RangeValidationResult]:
    """
    Validate physical numeric ranges for demand values and flag out-of-range rows.
    """
    df = df.copy()
    demand_col = config.demand_col

    # Ensure numeric series
    numeric_series = pd.to_numeric(df[demand_col], errors="coerce")
    valid_numeric = numeric_series.dropna()

    min_allowed = config.plausible_min
    max_allowed = config.plausible_max

    min_obs = float(valid_numeric.min()) if len(valid_numeric) > 0 else None
    max_obs = float(valid_numeric.max()) if len(valid_numeric) > 0 else None

    # Flag out of range
    out_of_range_mask = (numeric_series < min_allowed) | (numeric_series > max_allowed)
    out_of_range_count = int(out_of_range_mask.sum())
    total_evaluated = len(df)
    out_of_range_pct = (out_of_range_count / total_evaluated * 100.0) if total_evaluated > 0 else 0.0

    # Flag reverse power flow (negative load)
    negative_mask = numeric_series < 0.0
    negative_count = int(negative_mask.sum())
    negative_pct = (negative_count / total_evaluated * 100.0) if total_evaluated > 0 else 0.0

    # Append audit columns
    df["is_out_of_range"] = out_of_range_mask
    df["is_reverse_flow"] = negative_mask

    result = RangeValidationResult(
        total_evaluated=total_evaluated,
        min_allowed=min_allowed,
        max_allowed=max_allowed,
        min_observed=min_obs,
        max_observed=max_obs,
        out_of_range_count=out_of_range_count,
        out_of_range_pct=out_of_range_pct,
        negative_load_count=negative_count,
        negative_load_pct=negative_pct,
    )
    return df, result
