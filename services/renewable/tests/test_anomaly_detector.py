import pandas as pd

from services.renewable.anomaly_detector import detect_anomalies
from services.renewable.curtailment import add_curtailment_flag_if_available, classify_deviation
from services.renewable.performance import calculate_performance


def _performance(actual, expected=None):
    expected = expected or [10.0] * len(actual)
    timestamps = pd.Series(pd.date_range("2026-06-01 12:00", periods=len(actual), freq="15min", tz="UTC"))
    return calculate_performance("solar-1", "solar", timestamps, pd.Series(expected), pd.Series(actual))


def _diagnostic(performance, cloud_cover=None):
    weather = None
    if cloud_cover is not None:
        weather = performance[["timestamp"]].assign(cloud_cover=cloud_cover)
    return classify_deviation(performance, weather), weather


def test_normal_operation_has_no_anomalies():
    performance = _performance([10.0] * 24)
    diagnostic, _ = _diagnostic(performance)
    result = detect_anomalies(performance, diagnostic)
    assert not result["anomaly"].any()


def test_clear_sky_zero_output_is_flagged():
    performance = _performance([10.0] * 24 + [0.0])
    diagnostic, weather = _diagnostic(performance, [5.0] * len(performance))
    result = detect_anomalies(performance, diagnostic, weather)
    assert bool(result.iloc[-1]["anomaly"])
    assert result.iloc[-1]["anomaly_score"] < 0.0


def test_weather_explained_reduction_is_not_an_unexplained_anomaly():
    performance = _performance([10.0] * 24 + [4.0])
    diagnostic, weather = _diagnostic(performance, [10.0] * 24 + [95.0])
    result = detect_anomalies(performance, diagnostic, weather)
    assert result.iloc[-1]["diagnostic_category"] == "weather_driven_reduction"
    assert not bool(result.iloc[-1]["anomaly"])


def test_curtailment_is_suppressed_by_default_and_can_be_enabled():
    performance = _performance([10.0] * 24 + [0.0])
    diagnostic, _ = _diagnostic(performance)
    diagnostic["curtailment_flag"] = [False] * 24 + [True]
    diagnostic = add_curtailment_flag_if_available(diagnostic, "curtailment_flag")
    suppressed = detect_anomalies(performance, diagnostic)
    enabled = detect_anomalies(performance, diagnostic, suppress_curtailment=False)
    assert not bool(suppressed.iloc[-1]["anomaly"])
    assert suppressed.iloc[-1]["anomaly_suppressed_reason"] == "intentional_curtailment"
    assert bool(enabled.iloc[-1]["anomaly"])
    assert pd.isna(enabled.iloc[-1]["anomaly_suppressed_reason"])


def test_data_quality_row_is_returned_and_flagged_without_fitting_on_nan():
    performance = _performance([10.0] * 24 + [1.0], expected=[10.0] * 24 + [0.0])
    diagnostic, _ = _diagnostic(performance)
    result = detect_anomalies(performance, diagnostic)
    assert bool(result.iloc[-1]["anomaly"])
    assert result.iloc[-1]["diagnostic_category"] == "data_quality_issue"
