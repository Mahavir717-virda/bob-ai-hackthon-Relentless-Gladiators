"""
GridPilot AI — Missing Demand Value Policies
============================================
Implements explicit, audited policies for handling missing demand values.
Silent interpolation is strictly forbidden.
Every modification or imputation is tracked with an `is_imputed` indicator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
import pandas as pd

from services.data.config import IngestionConfig, MissingValuePolicy


@dataclass
class MissingHandlingResult:
    """Detailed audit metrics of the missing value policy execution."""
    policy: MissingValuePolicy
    initial_missing_count: int
    initial_missing_pct: float
    imputed_count: int
    remaining_missing_count: int
    dropped_rows_count: int
    imputed_timestamps: List[str] = field(default_factory=list)
    unresolved_timestamps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy": self.policy.value,
            "initial_missing_count": self.initial_missing_count,
            "initial_missing_pct": round(self.initial_missing_pct, 4),
            "imputed_count": self.imputed_count,
            "remaining_missing_count": self.remaining_missing_count,
            "dropped_rows_count": self.dropped_rows_count,
            "imputed_timestamps": self.imputed_timestamps,
            "unresolved_timestamps": self.unresolved_timestamps,
        }


def handle_missing_demand(
    df: pd.DataFrame,
    config: IngestionConfig,
) -> Tuple[pd.DataFrame, MissingHandlingResult]:
    """
    Explicitly handle missing demand values according to the configured policy.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with normalized 'timestamp' and numeric 'load' column.
    config : IngestionConfig
        Pipeline configuration containing missing_policy and max_fill_gap_intervals.

    Returns
    -------
    Tuple[pd.DataFrame, MissingHandlingResult]
        Cleaned/handled DataFrame with 'is_imputed' column and audit metrics.
    """
    df = df.copy()
    demand_col = config.demand_col
    timestamp_col = config.timestamp_col

    # Initialize is_imputed column
    if "is_imputed" not in df.columns:
        df["is_imputed"] = False

    initial_missing_mask = df[demand_col].isna()
    initial_missing_count = int(initial_missing_mask.sum())
    total_rows = len(df)
    initial_missing_pct = (initial_missing_count / total_rows * 100.0) if total_rows > 0 else 0.0

    if initial_missing_count == 0:
        return df, MissingHandlingResult(
            policy=config.missing_policy,
            initial_missing_count=0,
            initial_missing_pct=0.0,
            imputed_count=0,
            remaining_missing_count=0,
            dropped_rows_count=0,
        )

    policy = config.missing_policy
    imputed_timestamps: List[str] = []
    unresolved_timestamps: List[str] = []
    dropped_count = 0

    if policy == MissingValuePolicy.LEAVE_AS_NULL:
        # Keep NaNs explicitly, no imputation, flag timestamps
        unresolved_mask = df[demand_col].isna()
        unresolved_timestamps = [
            str(ts) for ts in df.loc[unresolved_mask, timestamp_col]
        ]
        return df, MissingHandlingResult(
            policy=policy,
            initial_missing_count=initial_missing_count,
            initial_missing_pct=initial_missing_pct,
            imputed_count=0,
            remaining_missing_count=initial_missing_count,
            dropped_rows_count=0,
            unresolved_timestamps=unresolved_timestamps,
        )

    elif policy == MissingValuePolicy.DROP:
        # Explicitly drop rows with NaN demand
        dropped_timestamps = [
            str(ts) for ts in df.loc[initial_missing_mask, timestamp_col]
        ]
        dropped_count = initial_missing_count
        df_cleaned = df[~initial_missing_mask].reset_index(drop=True)
        return df_cleaned, MissingHandlingResult(
            policy=policy,
            initial_missing_count=initial_missing_count,
            initial_missing_pct=initial_missing_pct,
            imputed_count=0,
            remaining_missing_count=0,
            dropped_rows_count=dropped_count,
            unresolved_timestamps=dropped_timestamps,
        )

    elif policy == MissingValuePolicy.FORWARD_FILL_MAX_GAP:
        # Forward fill within max_fill_gap_intervals
        max_gap = config.max_fill_gap_intervals
        # Track which rows are filled by ffill with limit
        ffilled = df[demand_col].ffill(limit=max_gap)
        imputed_mask = initial_missing_mask & ffilled.notna()

        df[demand_col] = ffilled
        df.loc[imputed_mask, "is_imputed"] = True

        imputed_count = int(imputed_mask.sum())
        imputed_timestamps = [
            str(ts) for ts in df.loc[imputed_mask, timestamp_col]
        ]

        remaining_missing = df[demand_col].isna()
        remaining_count = int(remaining_missing.sum())
        if remaining_count > 0:
            unresolved_timestamps = [
                str(ts) for ts in df.loc[remaining_missing, timestamp_col]
            ]

        return df, MissingHandlingResult(
            policy=policy,
            initial_missing_count=initial_missing_count,
            initial_missing_pct=initial_missing_pct,
            imputed_count=imputed_count,
            remaining_missing_count=remaining_count,
            dropped_rows_count=0,
            imputed_timestamps=imputed_timestamps,
            unresolved_timestamps=unresolved_timestamps,
        )

    else:
        raise ValueError(f"Unsupported missing value policy: {policy}")
