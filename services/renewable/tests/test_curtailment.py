import pandas as pd

from services.renewable.curtailment import (
    add_curtailment_flag_if_available,
    classify_deviation,
)


def _performance(ratios, asset_type="solar", actuals=None, edge_cases=None):
    actuals = actuals if actuals is not None else [ratio * 10 for ratio in ratios]
    edge_cases = edge_cases if edge_cases is not None else [False] * len(ratios)
    return pd.DataFrame({
        "asset_id": ["asset-1"] * len(ratios),
        "asset_type": [asset_type] * len(ratios),
        "timestamp": pd.date_range("2026-01-01", periods=len(ratios), freq="15min", tz="UTC"),
        "expected_mw": [10.0] * len(ratios),
        "actual_mw": actuals,
        "absolute_deviation": [actual - 10 for actual in actuals],
        "percentage_deviation": [(ratio - 1) * 100 for ratio in ratios],
        "performance_ratio": ratios,
        "zero_expected_edge_case": edge_cases,
    })


def test_normal_production():
    result = classify_deviation(_performance([1.0]))
    assert result.loc[0, "diagnostic_category"] == "normal_production"


def test_heavy_cloud_cover_explains_low_solar_ratio():
    performance = _performance([0.4])
    weather = performance[["timestamp"]].assign(cloud_cover=90.0)
    result = classify_deviation(performance, weather)
    assert result.loc[0, "diagnostic_category"] == "weather_driven_reduction"
    assert result.loc[0, "diagnostic_confidence"] >= 0.9


def test_persistently_low_ratio_is_possible_physical_fault_without_weather_explanation():
    result = classify_deviation(_performance([0.4, 0.4, 0.4, 0.4]))
    assert result.loc[3, "diagnostic_category"] == "possible_physical_fault"
    assert set(result.loc[:2, "diagnostic_category"]) == {"uncertain"}


def test_single_low_interval_without_weather_is_uncertain():
    result = classify_deviation(_performance([0.4]))
    assert result.loc[0, "diagnostic_category"] == "uncertain"


def test_zero_expected_edge_case_is_data_quality_issue():
    result = classify_deviation(_performance([float("nan")], edge_cases=[True]))
    assert result.loc[0, "diagnostic_category"] == "data_quality_issue"


def test_negative_actual_is_data_quality_issue():
    result = classify_deviation(_performance([0.4], actuals=[-1.0]))
    assert result.loc[0, "diagnostic_category"] == "data_quality_issue"


def test_explicit_curtailment_flag_overrides_ratio_diagnostic():
    performance = _performance([0.4, 0.4, 0.4, 0.4])
    performance["curtailed"] = [False, False, False, True]
    diagnosed = classify_deviation(performance)
    result = add_curtailment_flag_if_available(diagnosed, "curtailed")
    assert result.loc[3, "diagnostic_category"] == "intentional_curtailment"


def test_no_explicit_curtailment_column_never_generates_curtailment():
    result = add_curtailment_flag_if_available(classify_deviation(_performance([0.4])))
    assert result.loc[0, "diagnostic_category"] == "uncertain"
    assert "intentional_curtailment" not in result["diagnostic_category"].tolist()
