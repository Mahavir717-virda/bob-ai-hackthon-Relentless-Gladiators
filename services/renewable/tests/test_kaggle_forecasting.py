"""Deterministic tests for aggregate Kaggle forecasting."""

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from services.renewable.kaggle_forecasting import (
    FEATURE_COLUMNS,
    _feature_frame,
    _metrics,
    chronological_split,
    load_kaggle_forecaster,
    train_kaggle_series,
)


def _fixture(rows: int = 240) -> pd.DataFrame:
    timestamp = pd.date_range("2020-01-01", periods=rows, freq="h", tz="UTC")
    hour = np.arange(rows)
    return pd.DataFrame({
        "utc_timestamp": timestamp.astype(str),
        "DE_solar_generation_actual": np.maximum(0.0, 10 + 5 * np.sin(hour / 24 * 2 * np.pi)),
        "DE_solar_capacity": np.full(rows, 20.0),
        "AT_wind_onshore_generation_actual": 30 + np.sin(hour / 8) * 4,
    })


def test_features_use_only_past_generation_and_split_is_chronological():
    frame = _feature_frame(_fixture(), "DE_solar_generation_actual", "DE_solar_capacity")
    assert pd.isna(frame.loc[0, "lag_1"])
    assert frame.loc[10, "lag_1"] == frame.loc[9, "target_mw"]
    train, validation, test, split = chronological_split(frame)
    assert train.timestamp.iloc[-1] < validation.timestamp.iloc[0]
    assert validation.timestamp.iloc[-1] < test.timestamp.iloc[0]
    assert split.train_rows + split.validation_rows + split.test_rows == len(frame)


def test_missing_target_is_excluded_without_becoming_zero():
    source = _fixture()
    source.loc[50, "DE_solar_generation_actual"] = np.nan
    frame = _feature_frame(source, "DE_solar_generation_actual", "DE_solar_capacity")
    train, validation, test, _ = chronological_split(frame)
    assert not pd.isna(pd.concat([train, validation, test])["target_mw"]).any()
    assert not (pd.concat([train, validation, test])["target_mw"] == 0).all()


def test_safe_mape_handles_all_zero_actuals():
    metrics = _metrics(pd.Series([0.0, 0.0]), np.array([1.0, 2.0]))
    assert metrics["mape_pct"] is None
    assert np.isfinite(metrics["mae_mw"])


def test_train_save_load_and_predict_in_mw(tmp_path: Path):
    source = _fixture(360)
    result = train_kaggle_series(
        source, "DE_solar_generation_actual", "solar", "DE_solar_capacity", tmp_path,
        min_valid_observations=100, lgb_params={"n_estimators": 20, "num_leaves": 7},
    )
    assert result is not None
    model = load_kaggle_forecaster(result.model_path)
    assert isinstance(model, lgb.LGBMRegressor)
    frame = _feature_frame(source, "DE_solar_generation_actual", "DE_solar_capacity").dropna(subset=list(FEATURE_COLUMNS))
    predictions = np.maximum(model.predict(frame[list(FEATURE_COLUMNS)]), 0.0)
    assert np.isfinite(predictions).all()
    assert (predictions >= 0).all()
    assert Path(result.metadata_path).exists()