"""
GridPilot AI — Forecasting Evaluation & Splitting Utilities
===========================================================
Provides:
  - Strict chronological train / validation / test time-series splitting (NO SHUFFLE)
  - Standardized regression evaluation metrics (MAE, RMSE, MAPE)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple
import numpy as np
import pandas as pd


@dataclass
class ChronologicalSplitResult:
    """Stores train, validation, and test subsets with split bounds."""
    train_df: pd.DataFrame
    val_df: pd.DataFrame
    test_df: pd.DataFrame
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    test_start: str
    test_end: str
    n_train: int
    n_val: int
    n_test: int


def chronological_split(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> ChronologicalSplitResult:
    """
    Split time series data strictly chronologically without any random shuffling.

    Parameters
    ----------
    df : pd.DataFrame
        Input time series DataFrame.
    timestamp_col : str
        Column used to verify chronological ordering.
    train_ratio : float
        Proportion of earliest data allocated to training (default 0.70).
    val_ratio : float
        Proportion allocated to validation (default 0.15).

    Returns
    -------
    ChronologicalSplitResult
        Train, validation, and test DataFrames.
    """
    df = df.sort_values(timestamp_col).reset_index(drop=True)
    n = len(df)

    train_end_idx = int(n * train_ratio)
    val_end_idx = int(n * (train_ratio + val_ratio))

    train_df = df.iloc[:train_end_idx].copy().reset_index(drop=True)
    val_df = df.iloc[train_end_idx:val_end_idx].copy().reset_index(drop=True)
    test_df = df.iloc[val_end_idx:].copy().reset_index(drop=True)

    return ChronologicalSplitResult(
        train_df=train_df,
        val_df=val_df,
        test_df=test_df,
        train_start=str(train_df[timestamp_col].iloc[0]),
        train_end=str(train_df[timestamp_col].iloc[-1]),
        val_start=str(val_df[timestamp_col].iloc[0]),
        val_end=str(val_df[timestamp_col].iloc[-1]),
        test_start=str(test_df[timestamp_col].iloc[0]),
        test_end=str(test_df[timestamp_col].iloc[-1]),
        n_train=len(train_df),
        n_val=len(val_df),
        n_test=len(test_df),
    )


def calculate_metrics(
    y_true: pd.Series | np.ndarray,
    y_pred: pd.Series | np.ndarray,
    epsilon: float = 1e-4,
) -> Dict[str, Any]:
    """
    Calculate MAE, RMSE, and MAPE across valid non-null prediction pairs.

    Parameters
    ----------
    y_true : Series or ndarray
        Ground truth observations.
    y_pred : Series or ndarray
        Predicted values.
    epsilon : float
        Small constant to avoid division by zero in MAPE for near-zero values.

    Returns
    -------
    Dict[str, Any]
        Dictionary with mae, rmse, mape, and sample size n.
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)

    # Valid mask where neither value is NaN
    valid_mask = ~np.isnan(y_t) & ~np.isnan(y_p)
    if not np.any(valid_mask):
        return {"mae": None, "rmse": None, "mape": None, "n": 0}

    y_t_valid = y_t[valid_mask]
    y_p_valid = y_p[valid_mask]
    n_samples = int(np.sum(valid_mask))

    errors = y_t_valid - y_p_valid
    abs_errors = np.abs(errors)

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    # For MAPE, filter out points where ground truth is very close to zero
    nonzero_mask = np.abs(y_t_valid) > epsilon
    if np.any(nonzero_mask):
        mape = float(np.mean(abs_errors[nonzero_mask] / np.abs(y_t_valid[nonzero_mask])) * 100.0)
    else:
        mape = None

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 4) if mape is not None else None,
        "n": n_samples,
    }
