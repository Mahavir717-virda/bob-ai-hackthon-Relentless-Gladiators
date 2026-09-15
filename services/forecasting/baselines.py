"""
GridPilot AI — Demand Forecasting Baselines
============================================
Implements standard time-series benchmark baselines:
  1. Persistence (Last-Value): y_hat(t+h) = y(t)
  2. Seasonal Naive: y_hat(t+h) = y(t + h - S)
"""

from __future__ import annotations

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from services.forecasting.evaluate import calculate_metrics


class PersistenceForecaster:
    """
    Persistence (Last-Value) Baseline:
    Forecast at horizon t+h is the most recent observed demand at time t.
    """

    def __init__(self, freq_minutes: int = 15) -> None:
        self.freq_minutes = freq_minutes
        self.name = "persistence"

    def predict_series(
        self,
        series: pd.Series,
        horizon_minutes: int,
    ) -> pd.Series:
        """
        Generate persistence predictions aligned with series index.

        For target at index i, the prediction made horizon_minutes earlier
        is the observation at index (i - steps).

        Parameters
        ----------
        series : pd.Series
            Full sequential demand series (or test series with history).
        horizon_minutes : int
            Forecast horizon in minutes (e.g. 15, 30, 60).

        Returns
        -------
        pd.Series
            Persistence predictions aligned to target index.
        """
        steps = int(horizon_minutes / self.freq_minutes)
        return series.shift(steps)


class SeasonalNaiveForecaster:
    """
    Seasonal Naive Baseline:
    Forecast at horizon t+h is the observation from the same time in the
    previous seasonal cycle (default: 24-hour daily cycle S = 1440 min = 96 steps).
    """

    def __init__(
        self,
        freq_minutes: int = 15,
        seasonal_cycle_minutes: int = 1440,
    ) -> None:
        self.freq_minutes = freq_minutes
        self.seasonal_cycle_minutes = seasonal_cycle_minutes
        self.seasonal_steps = int(seasonal_cycle_minutes / freq_minutes)
        self.name = "seasonal_naive"

    def predict_series(
        self,
        series: pd.Series,
        horizon_minutes: int = 15,
    ) -> pd.Series:
        """
        Generate seasonal naive predictions aligned with series index.

        For target at index i, the seasonal prediction from the previous cycle
        is the observation at index (i - seasonal_steps).

        Parameters
        ----------
        series : pd.Series
            Full sequential demand series (or test series with history).
        horizon_minutes : int
            Forecast horizon in minutes (15, 30, 60).

        Returns
        -------
        pd.Series
            Seasonal naive predictions aligned to target index.
        """
        # For predicting time i, seasonal naive uses the value at the same time in previous cycle:
        # i - seasonal_steps (e.g. i - 96 for 24h cycle)
        return series.shift(self.seasonal_steps)


def evaluate_baselines_on_split(
    full_series: pd.Series,
    test_start_idx: int,
    horizons_minutes: List[int] = [15, 30, 60],
    freq_minutes: int = 15,
) -> pd.DataFrame:
    """
    Evaluate persistence and seasonal naive baselines on the test split.

    Using full_series ensures that the leading rows of the test set have
    access to the required past context (e.g. 96 steps prior from validation/train)
    without any future data leakage.

    Parameters
    ----------
    full_series : pd.Series
        Complete sequential target series across train+val+test.
    test_start_idx : int
        Starting index of the test partition in full_series.
    horizons_minutes : List[int]
        Horizons to evaluate (e.g. [15, 30, 60]).
    freq_minutes : int
        Sampling interval in minutes.

    Returns
    -------
    pd.DataFrame
        Summary table with columns [model, horizon_minutes, mae, rmse, mape, n].
    """
    persistence = PersistenceForecaster(freq_minutes=freq_minutes)
    seasonal = SeasonalNaiveForecaster(freq_minutes=freq_minutes)

    y_test = full_series.iloc[test_start_idx:].copy().reset_index(drop=True)
    results = []

    # 1. Evaluate Persistence across all horizons
    for h in horizons_minutes:
        y_pred_full = persistence.predict_series(full_series, horizon_minutes=h)
        y_pred_test = y_pred_full.iloc[test_start_idx:].copy().reset_index(drop=True)

        metrics = calculate_metrics(y_test, y_pred_test)
        results.append({
            "model": "persistence",
            "horizon_minutes": h,
            **metrics,
        })

    # 2. Evaluate Seasonal Naive across all horizons
    for h in horizons_minutes:
        y_pred_full = seasonal.predict_series(full_series, horizon_minutes=h)
        y_pred_test = y_pred_full.iloc[test_start_idx:].copy().reset_index(drop=True)

        metrics = calculate_metrics(y_test, y_pred_test)
        results.append({
            "model": "seasonal_naive",
            "horizon_minutes": h,
            **metrics,
        })

    return pd.DataFrame(results)
