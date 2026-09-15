"""
services/renewable/performance.py
=================================
Expected-vs-Actual Performance Calculation Layer.

Responsibilities:
- Compute absolute deviation (MW), percentage deviation (%), and performance ratio.
- Handle zero/near-zero expected generation safely without division by zero.
- Flag zero-expected edge cases (where expected is ~0 but actual > 0) for downstream diagnosis.
- Expose `calculate_performance()` returning a standardized DataFrame.
- Expose `get_renewable_status_partial()` mapping a row to the canonical `RenewableStatus` shape.

PURE CALCULATION LAYER:
This function is a pure calculation layer with no anomaly or fault opinions.
It does NOT classify events as weather-driven, equipment faults, or curtailment.
Classification and root-cause diagnostics are handled downstream (Chunk 5 & 6).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Threshold below which expected or actual generation is considered near-zero (MW)
# 1e-4 MW = 100 W (filters noise, night solar, calm wind)
NEAR_ZERO_MW_THRESHOLD: float = 1e-4

VALID_ASSET_TYPES: tuple[str, ...] = ("solar", "wind", "hydro")

PERFORMANCE_COLUMNS: tuple[str, ...] = (
    "asset_id",
    "asset_type",
    "timestamp",
    "expected_mw",
    "actual_mw",
    "absolute_deviation",
    "percentage_deviation",
    "performance_ratio",
    "zero_expected_edge_case",
)


def calculate_performance(
    asset_id: str,
    asset_type: str,
    timestamps: pd.Series,
    expected_mw: pd.Series,
    actual_mw: pd.Series,
) -> pd.DataFrame:
    """
    Calculate expected-vs-actual generation performance metrics.

    This function is a pure calculation layer with no anomaly or fault opinions.
    It computes deviations and ratios deterministically and vectorially.

    Parameters
    ----------
    asset_id : str
        Unique asset identifier.
    asset_type : str
        Asset type: 'solar', 'wind', or 'hydro'.
    timestamps : pd.Series
        Timestamps corresponding to the generation intervals.
    expected_mw : pd.Series
        Model-expected generation in Megawatts (MW).
    actual_mw : pd.Series
        Actual observed generation in Megawatts (MW).

    Returns
    -------
    pd.DataFrame with columns:
        - asset_id (str)
        - asset_type (str)
        - timestamp (pd.Series)
        - expected_mw (float)
        - actual_mw (float)
        - absolute_deviation (float: actual_mw - expected_mw)
        - percentage_deviation (float: (actual_mw - expected_mw) / expected_mw * 100)
        - performance_ratio (float: actual_mw / expected_mw)
        - zero_expected_edge_case (bool: True if expected is ~0 but actual is > 0)

    Raises
    ------
    ValueError
        If inputs are missing, mismatched in length, or if asset_type is invalid.
    """
    # ── Input validation ─────────────────────────────────────────────────────
    if not isinstance(asset_id, str) or not asset_id.strip():
        raise ValueError(f"asset_id must be a non-empty string, got {asset_id!r}")

    if asset_type not in VALID_ASSET_TYPES:
        raise ValueError(
            f"Invalid asset_type: {asset_type!r}. Must be one of {VALID_ASSET_TYPES}"
        )

    for name, s in (("timestamps", timestamps), ("expected_mw", expected_mw), ("actual_mw", actual_mw)):
        if not isinstance(s, (pd.Series, pd.Index, np.ndarray, list, tuple)):
            raise ValueError(f"{name} must be a pd.Series or 1D array-like, got {type(s).__name__}")

    n_ts = len(timestamps)
    n_exp = len(expected_mw)
    n_act = len(actual_mw)
    if not (n_ts == n_exp == n_act):
        raise ValueError(
            f"Input length mismatch: timestamps={n_ts}, expected_mw={n_exp}, actual_mw={n_act}. "
            "All input series must have identical length and alignment."
        )

    # Convert to 1D numpy arrays for fast vectorized operations
    ts_series = pd.Series(timestamps).reset_index(drop=True)
    exp_arr = np.asarray(expected_mw, dtype=float).ravel()
    act_arr = np.asarray(actual_mw, dtype=float).ravel()

    # Empty input handling
    if n_ts == 0:
        return pd.DataFrame(columns=PERFORMANCE_COLUMNS)

    # ── Vectorized deviations ────────────────────────────────────────────────
    # absolute_deviation: actual_mw - expected_mw
    abs_dev = act_arr - exp_arr

    # Near-zero classification (noise / night solar / calm wind)
    expected_near_zero = exp_arr < NEAR_ZERO_MW_THRESHOLD
    actual_near_zero = act_arr < NEAR_ZERO_MW_THRESHOLD

    # Condition 1: Both expected and actual are near-zero (e.g. night solar, calm wind)
    # Expected non-event -> nominal performance ratio = 1.0, deviation = 0%
    both_near_zero = expected_near_zero & actual_near_zero

    # Condition 2: Expected ~0, but actual is meaningfully > 0 (sensor glitch / unpredicted generation)
    # Undefined ratio -> NaN, flagged as zero_expected_edge_case
    unexpected_generation = expected_near_zero & (~actual_near_zero)

    # Condition 3: Expected is positive (normal operating regime)
    normal_operating = ~expected_near_zero

    # Compute performance_ratio safely
    ratio = np.full(n_ts, np.nan, dtype=float)
    ratio[both_near_zero] = 1.0
    ratio[normal_operating] = act_arr[normal_operating] / exp_arr[normal_operating]

    # Compute percentage_deviation safely: ((actual - expected) / expected) * 100
    pct_dev = np.full(n_ts, np.nan, dtype=float)
    pct_dev[both_near_zero] = 0.0
    pct_dev[normal_operating] = (abs_dev[normal_operating] / exp_arr[normal_operating]) * 100.0

    # Flag zero-expected edge case
    zero_edge_case = np.zeros(n_ts, dtype=bool)
    zero_edge_case[unexpected_generation] = True

    # ── Construct result DataFrame ───────────────────────────────────────────
    result = pd.DataFrame({
        "asset_id": [asset_id] * n_ts,
        "asset_type": [asset_type] * n_ts,
        "timestamp": ts_series,
        "expected_mw": exp_arr,
        "actual_mw": act_arr,
        "absolute_deviation": abs_dev,
        "percentage_deviation": pct_dev,
        "performance_ratio": ratio,
        "zero_expected_edge_case": zero_edge_case,
    })

    return result


def get_renewable_status_partial(row: pd.Series | dict[str, Any]) -> dict[str, Any]:
    """
    Map a performance row to the fields of RenewableStatus populated by this calculation layer.

    Fields populated:
    - assetId: str
    - assetType: 'solar' | 'wind' | 'hydro'
    - timestamp: ISO 8601 string or original timestamp representation
    - expectedMw: float
    - actualMw: float
    - performanceRatio: float | None

    Fields left None (populated downstream):
    - anomaly: None (evaluated by Isolation Forest in Chunk 6)
    - likelyRootCause: None (diagnosed in Chunk 7)

    Parameters
    ----------
    row : pd.Series or dict with performance columns

    Returns
    -------
    dict conforming to the populated fields of RenewableStatus contract
    """
    ts = row["timestamp"]
    if hasattr(ts, "isoformat"):
        ts_str = ts.isoformat()
    else:
        ts_str = str(ts)

    ratio_val = row["performance_ratio"]
    if pd.isna(ratio_val):
        perf_ratio = None
    else:
        perf_ratio = float(ratio_val)

    return {
        "assetId": str(row["asset_id"]),
        "assetType": str(row["asset_type"]),
        "timestamp": ts_str,
        "expectedMw": float(row["expected_mw"]),
        "actualMw": float(row["actual_mw"]),
        "performanceRatio": perf_ratio,
        "anomaly": None,
        "likelyRootCause": None,
    }
