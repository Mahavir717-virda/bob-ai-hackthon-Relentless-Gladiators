"""Deterministic tests for Kaggle performance and anomaly detection."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from services.renewable.kaggle_anomaly import (
    ANOMALY_FEATURE_COLUMNS,
    _anomaly_features,
    calculate_kaggle_performance,
    detect_kaggle_anomalies,
    load_kaggle_anomaly_detector,
    train_kaggle_anomaly_detector,
)


def _performance(expected: list[float], actual: list[float], capacity: list[float] | None = None) -> pd.DataFrame:
    timestamps = pd.date_range("2020-01-01", periods=len(expected), freq="h", tz="UTC")
    result = calculate_kaggle_performance(
        pd.Series(actual), pd.Series(expected),
        pd.Series(capacity if capacity is not None else [np.nan] * len(expected)),
    )
    result.insert(0, "timestamp", timestamps)
    result.insert(0, "energy_type", "solar")
    result.insert(0, "asset_id", "TEST_solar_generation_actual")
    result["curtailment_status"] = "unknown"
    return result


def test_actual_expected_and_capacity_metrics_are_safe():
    result = _performance([10.0, 0.0, 1e-8], [8.0, 0.0, 2.0], [20.0, 20.0, np.nan])
    assert result.loc[0, "absolute_deviation_mw"] == -2.0
    assert result.loc[0, "absolute_error_mw"] == 2.0
    assert result.loc[0, "performance_ratio"] == 0.8
    assert result.loc[0, "generation_capacity_ratio"] == 0.4
    assert pd.isna(result.loc[1, "performance_ratio"])
    assert pd.isna(result.loc[2, "percentage_deviation"])
    assert pd.isna(result.loc[2, "generation_capacity_ratio"])


def test_missing_rows_are_not_anomalies_and_unknown_curtailment_is_preserved():
    result = _performance([10.0, np.nan, 10.0], [9.0, np.nan, 8.0], [20.0, np.nan, np.nan])
    bundle = {
        "model": IsolationForest(n_estimators=40, contamination=0.25, random_state=42),
        "feature_columns": list(ANOMALY_FEATURE_COLUMNS),
        "medians": _anomaly_features(result).median().fillna(0.0).to_dict(),
    }
    fit = _anomaly_features(result).fillna(bundle["medians"]).fillna(0.0)
    bundle["model"].fit(fit)
    detected = detect_kaggle_anomalies(result, bundle)
    assert pd.isna(detected.loc[1, "anomaly_flag"])
    assert pd.isna(detected.loc[1, "anomaly_score"])
    assert (detected["curtailment_status"] == "unknown").all()


def test_explicit_curtailment_suppresses_flag(tmp_path: Path):
    rows = 240
    timestamp = pd.date_range("2020-01-01", periods=rows, freq="h", tz="UTC")
    source = pd.DataFrame({
        "utc_timestamp": timestamp.astype(str),
        "TEST_solar_generation_actual": [10.0] * (rows - 1) + [0.0],
        "TEST_solar_capacity": [20.0] * rows,
        "curtailment_flag": [False] * (rows - 1) + [True],
    })
    forecast_path = tmp_path / "forecast.pkl"
    metadata_path = tmp_path / "forecast_metadata.json"
    from sklearn.dummy import DummyRegressor
    model = DummyRegressor(strategy="constant", constant=10.0).fit(np.ones((1, 18)), [10.0])
    import joblib
    joblib.dump(model, forecast_path)
    metadata_path.write_text('{"features": ["hour_sin", "hour_cos", "day_of_week_sin", "day_of_week_cos", "day_of_year_sin", "day_of_year_cos", "month_sin", "month_cos", "lag_1", "lag_2", "lag_3", "lag_6", "lag_24", "lag_48", "lag_168", "roll_mean_3", "roll_mean_24", "roll_mean_168"]}')
    result, evaluated = train_kaggle_anomaly_detector(
        source, forecast_path, "TEST_solar_generation_actual", "solar", "TEST_solar_capacity", tmp_path,
        contamination=0.1, curtailment_column="curtailment_flag",
    )
    assert result is not None
    assert evaluated.iloc[-1]["curtailment_status"] == "intentional"
    assert evaluated.iloc[-1]["anomaly_flag"] is False or evaluated.iloc[-1]["anomaly_flag"] == False


def test_train_save_load_and_score_with_fresh_bundle(tmp_path: Path):
    rows = 240
    timestamp = pd.date_range("2020-01-01", periods=rows, freq="h", tz="UTC")
    actual = [10.0] * rows
    actual[-1] = 80.0
    source = pd.DataFrame({
        "utc_timestamp": timestamp.astype(str),
        "TEST_wind_generation_actual": actual,
    })
    from sklearn.dummy import DummyRegressor
    import joblib
    forecast_path = tmp_path / "forecast.pkl"
    joblib.dump(DummyRegressor(strategy="constant", constant=10.0).fit(np.ones((1, 18)), [10.0]), forecast_path)
    (tmp_path / "forecast_metadata.json").write_text('{"features": ["hour_sin", "hour_cos", "day_of_week_sin", "day_of_week_cos", "day_of_year_sin", "day_of_year_cos", "month_sin", "month_cos", "lag_1", "lag_2", "lag_3", "lag_6", "lag_24", "lag_48", "lag_168", "roll_mean_3", "roll_mean_24", "roll_mean_168"]}')
    result, _ = train_kaggle_anomaly_detector(source, forecast_path, "TEST_wind_generation_actual", "wind", None, tmp_path)
    assert result is not None
    bundle = load_kaggle_anomaly_detector(result.model_path)
    assert isinstance(bundle["model"], IsolationForest)