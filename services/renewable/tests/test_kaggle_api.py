from pathlib import Path

import pytest
from fastapi import HTTPException

from services.renewable import kaggle_api


SOLAR = "DE_solar_generation_actual"
WIND = "AT_wind_onshore_generation_actual"
TIMESTAMP = "2019-06-01T12:00:00Z"


def test_status_exposes_actual_kaggle_solar_output_in_shared_contract_shape():
    result = kaggle_api.status(SOLAR, TIMESTAMP)
    assert len(result) == 1
    status = result[0]
    assert status["assetId"] == SOLAR
    assert status["assetType"] == "solar"
    assert status["actualMw"] >= 0
    assert status["expectedMw"] >= 0
    assert isinstance(status["anomaly"], bool)
    assert "anomalyScore" not in status


def test_status_exposes_actual_kaggle_wind_output_in_shared_contract_shape():
    result = kaggle_api.status(WIND, TIMESTAMP)
    assert result[0]["assetId"] == WIND
    assert result[0]["assetType"] == "wind"
    assert result[0]["performanceRatio"] >= 0


def test_healthy_and_anomalous_results_preserve_flags_without_fabricating_scores():
    healthy = kaggle_api.to_renewable_status({
        "asset_id": "DE_solar_generation_actual", "energy_type": "solar", "timestamp": TIMESTAMP,
        "actual_mw": 10.0, "expected_mw": 10.0, "performance_ratio": 1.0,
        "anomaly_flag": False, "anomaly_score": 0.2, "root_cause": "insufficient evidence", "confidence": None,
    })
    anomalous = kaggle_api.to_renewable_status({
        "asset_id": "AT_wind_onshore_generation_actual", "energy_type": "wind", "timestamp": TIMESTAMP,
        "actual_mw": 2.0, "expected_mw": 10.0, "performance_ratio": 0.2,
        "anomaly_flag": True, "anomaly_score": -0.2,
        "root_cause": "unusually low generation relative to expected", "confidence": None,
    })
    assert healthy["anomaly"] is False
    assert anomalous["anomaly"] is True
    assert "anomalyScore" not in healthy and "anomalyScore" not in anomalous
    assert "likelyRootCause" not in anomalous


def test_missing_inference_data_is_an_explicit_availability_error():
    with pytest.raises(HTTPException) as exc:
        kaggle_api.to_renewable_status({
            "asset_id": SOLAR, "energy_type": "solar", "timestamp": TIMESTAMP,
            "actual_mw": 1.0, "expected_mw": None, "performance_ratio": None, "anomaly_flag": False,
        })
    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "KAGGLE_INFERENCE_UNAVAILABLE"


def test_missing_root_cause_artifact_is_explicitly_unavailable(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(kaggle_api, "DEFAULT_ROOT_CAUSE_DIR", tmp_path)
    with pytest.raises(HTTPException) as exc:
        kaggle_api.status(SOLAR, TIMESTAMP)
    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "MISSING_ROOT_CAUSE_MODEL"
