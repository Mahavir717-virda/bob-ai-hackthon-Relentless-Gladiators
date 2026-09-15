import pandas as pd
import pytest

from services.renewable import renewable_service as service


def _record(actuals, asset_type="solar", model_path=None):
    timestamps = pd.date_range("2026-01-01", periods=len(actuals), freq="15min", tz="UTC")
    record = {
        "asset_type": asset_type,
        "data": pd.DataFrame({"timestamp": timestamps, "expected_mw": [10.0] * len(actuals), "actual_mw": actuals}),
        "weather_df": pd.DataFrame({"timestamp": timestamps, "cloud_cover": [10.0] * len(actuals)}),
    }
    if model_path:
        record["model_path"] = model_path
    return record


@pytest.fixture(autouse=True)
def registry(monkeypatch):
    monkeypatch.setattr(service, "_ASSET_REGISTRY", {
        "solar-normal": _record([10.0] * 20),
        "solar-anomaly": _record([10.0] * 24 + [0.0]),
        "hydro-1": _record([10.0] * 20, asset_type="hydro"),
    })
    monkeypatch.setattr(service, "_MODEL_CACHE", {})


def test_status_for_normal_asset_has_contract_shape_without_root_analysis():
    result = service.getRenewableStatus("solar-normal", "2026-01-01T04:45:00Z")
    assert set(result) == {"assetId", "assetType", "timestamp", "expectedMw", "actualMw", "performanceRatio", "anomaly"}
    assert not result["anomaly"]


def test_status_for_anomaly_includes_public_root_analysis(monkeypatch):
    monkeypatch.setattr(service, "_root_cause_analysis", lambda *_: {"category": "unexplained_anomaly", "confidence": 0.8, "evidence": {"hidden": True}})
    result = service.getRenewableStatus("solar-anomaly", "2026-01-01T06:00:00Z")
    assert result["anomaly"]
    assert result["likelyRootCause"] == {"category": "unexplained_anomaly", "confidence": 0.8}


def test_unknown_asset_raises_typed_error():
    with pytest.raises(service.RenewableDataError, match="No renewable data") as exc:
        service.getRenewableStatus("missing", "2026-01-01T00:00:00Z")
    assert exc.value.code == "UNKNOWN_ASSET"


def test_hydro_is_explicitly_unsupported():
    with pytest.raises(service.RenewableDataError) as exc:
        service.getRenewableStatus("hydro-1", "2026-01-01T04:45:00Z")
    assert exc.value.code == "UNSUPPORTED_ASSET_TYPE"


def test_detect_anomalies_returns_only_anomalous_contract_rows(monkeypatch):
    monkeypatch.setattr(service, "_root_cause_analysis", lambda *_: {"category": "uncertain", "confidence": 0.0, "evidence": {}})
    result = service.detectAnomalies({"asset_id": "solar-anomaly", "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T06:00:00Z"})
    assert len(result) == 1
    assert result[0]["anomaly"] is True
    assert "likelyRootCause" not in result[0]


def test_detect_anomalies_for_normal_range_is_empty():
    result = service.detectAnomalies({"asset_id": "solar-normal", "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T04:45:00Z"})
    assert result == []


def test_public_root_analysis_hides_evidence(monkeypatch):
    monkeypatch.setattr(service, "_root_cause_analysis", lambda *_: {"category": "weather_cloud_cover", "confidence": 0.7, "evidence": {"top_features": ["cloud_cover"]}})
    result = service.analyzeRootCause("solar-normal", "2026-01-01T04:45:00Z")
    assert result == {"category": "weather_cloud_cover", "confidence": 0.7}


def test_model_is_loaded_once_per_asset_type(monkeypatch):
    service._ASSET_REGISTRY["solar-normal"]["model_path"] = "solar.pkl"
    loads = {"count": 0}
    monkeypatch.setattr(service, "load_solar_model", lambda _: loads.__setitem__("count", loads["count"] + 1) or object())
    service.getRenewableStatus("solar-normal", "2026-01-01T04:45:00Z")
    service.getRenewableStatus("solar-normal", "2026-01-01T04:45:00Z")
    assert loads["count"] == 1
