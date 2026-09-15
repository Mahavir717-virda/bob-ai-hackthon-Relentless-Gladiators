"""Integration tests for the Kaggle Renewable Intelligence service."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from services.renewable.kaggle_service import (
    KaggleRenewableServiceError,
    analyzeRootCause,
    clear_kaggle_service_cache,
    detectAnomalies,
    getRenewableStatus,
)


SOLAR = "DE_solar_generation_actual"
WIND = "AT_wind_onshore_generation_actual"
TIMESTAMP = "2019-06-01T12:00:00Z"


@pytest.fixture(autouse=True)
def clear_cache():
    clear_kaggle_service_cache()
    yield
    clear_kaggle_service_cache()


def test_valid_solar_status_contains_consistent_metrics_and_shap_evidence():
    result = getRenewableStatus(SOLAR, TIMESTAMP)
    assert result["asset_id"] == SOLAR
    assert result["energy_type"] == "solar"
    assert result["actual_mw"] is not None
    assert result["expected_mw"] is not None
    assert result["absolute_deviation_mw"] == pytest.approx(result["actual_mw"] - result["expected_mw"])
    assert result["curtailment_status"] == "unknown"
    assert result["weather_available"] is False
    if result["anomaly_flag"]:
        assert len(result["evidence"]) == 5
        assert result["confidence"] is None


def test_valid_wind_status_preserves_missing_capacity():
    result = getRenewableStatus(WIND, TIMESTAMP)
    assert result["asset_id"] == WIND
    assert result["energy_type"] == "wind"
    assert result["capacity_mw"] is None
    assert result["capacity_ratio"] is None
    assert result["curtailment_status"] == "unknown"


def test_unknown_asset_and_invalid_timestamp_are_explicit_errors():
    with pytest.raises(KaggleRenewableServiceError, match="Unknown Kaggle aggregate") as unknown:
        getRenewableStatus("not_a_real_series", TIMESTAMP)
    assert unknown.value.code == "UNKNOWN_ASSET"
    with pytest.raises(KaggleRenewableServiceError) as invalid:
        getRenewableStatus(SOLAR, "not-a-timestamp")
    assert invalid.value.code == "INVALID_TIMESTAMP"


def test_timestamp_outside_dataset_is_explicit_error():
    with pytest.raises(KaggleRenewableServiceError) as exc:
        getRenewableStatus(SOLAR, "2035-01-01T00:00:00Z")
    assert exc.value.code == "TIMESTAMP_OUT_OF_RANGE"


def test_root_cause_interface_preserves_uncertainty_or_shap_association():
    result = analyzeRootCause(SOLAR, TIMESTAMP)
    assert result["asset_id"] == SOLAR
    assert result["curtailment_status"] == "unknown"
    assert result["confidence"] is None
    assert result["root_cause"] in {
        "insufficient evidence",
        "unusually low generation relative to expected",
        "unusually high generation relative to expected",
        "expected/normal temporal variation",
    }
    assert "failure" not in result["root_cause"]


def test_anomaly_range_is_valid_and_uses_aggregate_ids():
    results = detectAnomalies({"asset_id": SOLAR, "start": "2019-06-01T12:00:00Z", "end": "2019-06-01T15:00:00Z"})
    assert isinstance(results, list)
    for result in results:
        assert result["asset_id"] == SOLAR
        assert result["energy_type"] == "solar"
        assert result["curtailment_status"] == "unknown"
        assert result["weather_available"] is False


def test_invalid_time_range_is_explicit_error():
    with pytest.raises(KaggleRenewableServiceError) as exc:
        detectAnomalies({"start": "2019-06-02T00:00:00Z", "end": "2019-06-01T00:00:00Z"})
    assert exc.value.code == "INVALID_TIME_RANGE"


def test_repeated_status_request_is_deterministic():
    first = getRenewableStatus(SOLAR, TIMESTAMP)
    second = getRenewableStatus(SOLAR, TIMESTAMP)
    assert first == second


def test_safe_missing_and_zero_expected_status_fields():
    from services.renewable.kaggle_service import _status

    row = pd.Series({
        "asset_id": "TEST_solar_generation_actual", "timestamp": pd.Timestamp("2020-01-01", tz="UTC"),
        "energy_type": "solar", "actual_mw": np.nan, "expected_mw": 0.0,
        "absolute_deviation_mw": np.nan, "percentage_deviation": np.nan,
        "performance_ratio": np.nan, "capacity_mw": np.nan, "capacity_ratio": np.nan,
    })
    anomaly = pd.Series({"anomaly_flag": pd.NA, "anomaly_score": np.nan})
    result = _status(row, anomaly, {"root_cause": "insufficient evidence", "confidence": None, "evidence": []})
    assert result["actual_mw"] is None
    assert result["expected_mw"] == 0.0
    assert result["performance_ratio"] is None
    assert result["capacity_mw"] is None
    assert result["anomaly_flag"] is None