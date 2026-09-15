"""Deterministic end-to-end renewable service scenarios.

These tests exercise the public service functions over explicit registry
fixtures.  They intentionally do not call individual pipeline stages.
"""

import json

import pandas as pd
import pytest

from services.renewable import renewable_service as service


TIMESTAMPS = pd.date_range("2026-06-01 12:00", periods=8, freq="15min", tz="UTC")


def _record(
    asset_type,
    expected,
    actual,
    *,
    cloud_cover=5.0,
    wind_speed=None,
    curtailment=None,
):
    weather = {"timestamp": TIMESTAMPS, "cloud_cover": [cloud_cover] * len(TIMESTAMPS)}
    if wind_speed is not None:
        weather["wind_speed_10m"] = [wind_speed] * len(TIMESTAMPS)
    data = {
        "timestamp": TIMESTAMPS,
        "expected_mw": expected,
        "actual_mw": actual,
    }
    if curtailment is not None:
        data["curtailment_flag"] = curtailment
    return {
        "asset_type": asset_type,
        "data": pd.DataFrame(data),
        "weather_df": pd.DataFrame(weather),
    }


def _status(asset_id, index=-1):
    return service.getRenewableStatus(asset_id, TIMESTAMPS[index])


@pytest.fixture(autouse=True)
def registry(monkeypatch):
    normal = [10.0] * 8
    low = [4.0] * 8
    monkeypatch.setattr(
        service,
        "_ASSET_REGISTRY",
        {
            "healthy-solar": _record("solar", normal, normal),
            "cloud-solar": _record("solar", normal, low, cloud_cover=95.0),
            "degraded-solar": _record("solar", normal, normal[:4] + [4.0] * 4),
            "corrupt-solar": _record("solar", normal, [10.0] * 4 + [-1.0] + [10.0] * 3),
            "curtailed-solar": _record(
                "solar",
                normal,
                [10.0] * 4 + [2.0] * 4,
                curtailment=[False] * 4 + [True] * 4,
            ),
            "low-wind": _record("wind", normal, low, wind_speed=2.0),
            "batch-cloud": _record("solar", normal, low, cloud_cover=95.0),
            "batch-fault": _record("solar", normal, [10.0] * 4 + [4.0] * 4),
            "batch-corrupt": _record("solar", normal, [10.0] * 4 + [-1.0] + [10.0] * 3),
        },
    )
    monkeypatch.setattr(service, "_MODEL_CACHE", {})


def _report(name, value):
    print(f"{name}: {json.dumps(value, sort_keys=True, default=str)}")
    return value


def test_healthy_solar_end_to_end():
    result = _report("HEALTHY_SOLAR", _status("healthy-solar"))

    assert set(result) == {
        "assetId", "assetType", "timestamp", "expectedMw", "actualMw",
        "performanceRatio", "anomaly",
    }
    assert result["assetType"] == "solar"
    assert result["performanceRatio"] == pytest.approx(1.0)
    assert result["anomaly"] is False
    assert "likelyRootCause" not in result


def test_cloud_driven_reduction_is_not_a_fault():
    result = _report("CLOUD_DRIVEN_REDUCTION", _status("cloud-solar"))

    assert result["performanceRatio"] == pytest.approx(0.4)
    assert result["anomaly"] is False
    if "likelyRootCause" in result:
        assert result["likelyRootCause"]["category"].startswith("weather_")


def test_persistent_clear_sky_reduction_is_an_anomaly():
    result = _report("INVERTER_PERFORMANCE_DEGRADATION", _status("degraded-solar"))

    assert result["performanceRatio"] == pytest.approx(0.4)
    assert result["anomaly"] is True
    if "likelyRootCause" in result:
        assert result["likelyRootCause"]["category"] not in {
            "weather_cloud_cover", "weather_wind_speed",
        }


def test_sensor_corruption_is_a_data_quality_anomaly():
    result = _report("SENSOR_DATA_CORRUPTION", _status("corrupt-solar", index=4))

    assert result["actualMw"] == pytest.approx(-1.0)
    assert result["performanceRatio"] == pytest.approx(-0.1)
    assert result["anomaly"] is True
    if "likelyRootCause" in result:
        assert result["likelyRootCause"]["category"] == "data_quality_signal"


@pytest.mark.xfail(
    reason="renewable_service._pipeline drops curtailment_flag and never applies explicit curtailment suppression",
    strict=True,
)
def test_intentional_curtailment_survives_the_service_layer():
    result = _report("INTENTIONAL_CURTAILMENT", _status("curtailed-solar"))

    assert result["anomaly"] is False
    if "likelyRootCause" in result:
        assert result["likelyRootCause"]["category"] != "possible_physical_fault"


def test_low_wind_is_weather_explained_and_uses_wind_status_shape():
    result = _report("WIND_GENERATION_REDUCTION", _status("low-wind"))

    assert result["assetType"] == "wind"
    assert result["performanceRatio"] == pytest.approx(0.4)
    assert result["anomaly"] is False
    if "likelyRootCause" in result:
        assert result["likelyRootCause"]["category"] == "weather_wind_speed"


def test_multiple_anomalies_are_independent_in_one_batch(monkeypatch):
    categories = {
        "batch-fault": "persistent_pattern",
        "batch-corrupt": "data_quality_signal",
    }

    def root_cause(asset_id, timestamp):
        return {"category": categories[asset_id], "confidence": 0.8}

    monkeypatch.setattr(service, "_root_cause_analysis", root_cause)
    monkeypatch.setattr(
        service,
        "_ASSET_REGISTRY",
        {asset_id: service._ASSET_REGISTRY[asset_id] for asset_id in (
            "batch-cloud", "batch-fault", "batch-corrupt",
        )},
    )
    results = _report(
        "MULTIPLE_SIMULTANEOUS_ANOMALIES",
        service.detectAnomalies({"start": TIMESTAMPS[0], "end": TIMESTAMPS[-1]}),
    )

    by_asset = {result["assetId"]: result for result in results}
    assert set(by_asset) == {"batch-fault", "batch-corrupt"}
    assert all(result["anomaly"] is True for result in results)
    assert by_asset["batch-fault"]["likelyRootCause"]["category"] == "persistent_pattern"
    assert by_asset["batch-corrupt"]["likelyRootCause"]["category"] == "data_quality_signal"
    assert by_asset["batch-fault"]["likelyRootCause"] != by_asset["batch-corrupt"]["likelyRootCause"]