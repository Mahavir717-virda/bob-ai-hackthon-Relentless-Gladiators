"""Deterministic tests for uncertainty-first Kaggle root-cause association."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor

from services.renewable.kaggle_root_cause import (
    ROOT_FEATURE_COLUMNS,
    _root_frame,
    explain_kaggle_row,
    load_kaggle_root_cause_model,
    train_kaggle_root_cause_model,
)


def _rows(n: int = 240) -> pd.DataFrame:
    timestamp = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    hour = np.arange(n)
    actual = 10 + np.sin(hour / 12) * 2
    frame = pd.DataFrame({
        "timestamp": timestamp, "asset_id": "TEST_solar_generation_actual", "energy_type": "solar",
        "target_mw": actual, "actual_mw": actual, "expected_mw": 10.0, "capacity_mw": 20.0,
        "expected_capacity_ratio": 0.5,
    })
    for name in ("hour_sin", "hour_cos", "day_of_week_sin", "day_of_week_cos", "day_of_year_sin", "day_of_year_cos", "month_sin", "month_cos"):
        frame[name] = 0.0
    for lag in (1, 2, 3, 6, 24, 48, 168):
        frame[f"lag_{lag}"] = pd.Series(actual).shift(lag)
    for window in (3, 24, 168):
        frame[f"roll_mean_{window}"] = pd.Series(actual).shift(1).rolling(window, min_periods=1).mean()
    frame["percentage_deviation"] = (frame["target_mw"] - frame["expected_mw"]) / frame["expected_mw"] * 100
    return frame


def test_insufficient_evidence_does_not_claim_physical_cause():
    row = _rows(1).iloc[0]
    result = explain_kaggle_row(row, {"model": None, "feature_columns": list(ROOT_FEATURE_COLUMNS), "medians": {}}, anomaly_flag=False)
    assert result["root_cause"] == "insufficient evidence"
    assert result["confidence"] is None
    assert result["curtailment_status"] == "unknown"


def test_model_trains_saves_loads_and_generates_shap(tmp_path: Path):
    result = train_kaggle_root_cause_model(_rows(), "solar", tmp_path, min_rows=100)
    assert result is not None
    bundle = load_kaggle_root_cause_model("solar", tmp_path)
    row = _rows().iloc[-1]
    row["percentage_deviation"] = -50.0
    explanation = explain_kaggle_row(row, bundle, anomaly_flag=True)
    assert explanation["root_cause"] == "unusually low generation relative to expected"
    assert explanation["confidence"] is None
    assert explanation["curtailment_status"] == "unknown"
    assert len(explanation["evidence"]) == 5
    assert all("shap_contribution" in item for item in explanation["evidence"])


def test_missing_values_return_insufficient_evidence(tmp_path: Path):
    result = train_kaggle_root_cause_model(_rows(), "solar", tmp_path, min_rows=100)
    bundle = load_kaggle_root_cause_model("solar", tmp_path)
    row = _rows().iloc[-1].copy()
    row["expected_mw"] = np.nan
    row["percentage_deviation"] = np.nan
    explanation = explain_kaggle_row(row, bundle, anomaly_flag=True)
    assert explanation["root_cause"] == "insufficient evidence"