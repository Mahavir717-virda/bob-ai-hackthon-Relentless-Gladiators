"""
services/renewable/tests/test_performance.py
============================================
Unit tests for calculate_performance and get_renewable_status_partial.
"""

import numpy as np
import pandas as pd
import pytest

from services.renewable.performance import (
    calculate_performance,
    get_renewable_status_partial,
    PERFORMANCE_COLUMNS,
)


def test_1_normal_daytime_solar():
    """Case 1: Normal daytime solar (expected > 0, actual close to expected)."""
    ts = pd.date_range("2026-06-01 12:00", periods=3, freq="15min", tz="UTC")
    expected = pd.Series([5.0, 5.2, 4.8])
    actual = pd.Series([4.9, 5.1, 4.7])

    df = calculate_performance("solar_park_01", "solar", ts, expected, actual)

    # Check schema
    assert list(df.columns) == list(PERFORMANCE_COLUMNS)
    assert len(df) == 3

    # Check math
    np.testing.assert_allclose(df["absolute_deviation"], [-0.1, -0.1, -0.1], atol=1e-6)
    np.testing.assert_allclose(df["performance_ratio"], [4.9 / 5.0, 5.1 / 5.2, 4.7 / 4.8], atol=1e-6)
    np.testing.assert_allclose(
        df["percentage_deviation"],
        [(-0.1 / 5.0) * 100, (-0.1 / 5.2) * 100, (-0.1 / 4.8) * 100],
        atol=1e-6,
    )
    assert not df["zero_expected_edge_case"].any()


def test_2_nighttime_solar():
    """Case 2: Night-time solar (expected ~0, actual ~0) -> performance_ratio = 1.0."""
    ts = pd.date_range("2026-06-01 02:00", periods=3, freq="15min", tz="UTC")
    expected = pd.Series([0.0, 1e-6, 5e-5])
    actual = pd.Series([0.0, 0.0, 1e-5])

    df = calculate_performance("solar_park_01", "solar", ts, expected, actual)

    # All should be nominal non-events: ratio = 1.0, pct_dev = 0.0, edge_case = False
    assert (df["performance_ratio"] == 1.0).all()
    assert (df["percentage_deviation"] == 0.0).all()
    assert not df["zero_expected_edge_case"].any()


def test_3_sensor_glitch_zero_expected():
    """Case 3: Sensor glitch (expected ~0, actual > 0) -> performance_ratio = NaN, zero_expected_edge_case = True."""
    ts = pd.date_range("2026-06-01 01:00", periods=2, freq="15min", tz="UTC")
    expected = pd.Series([0.0, 5e-5])      # both < 1e-4 MW
    actual = pd.Series([2.5, 3.0])          # meaningfully positive (unexpected)

    df = calculate_performance("solar_park_01", "solar", ts, expected, actual)

    assert df["performance_ratio"].isna().all()
    assert df["percentage_deviation"].isna().all()
    assert df["zero_expected_edge_case"].all()
    np.testing.assert_allclose(df["absolute_deviation"], [2.5, 3.0 - 5e-5], atol=1e-6)


def test_4_wind_calm_period():
    """Case 4: Wind calm period (expected ~0, actual ~0) -> performance_ratio = 1.0."""
    ts = pd.date_range("2026-06-01 06:00", periods=3, freq="15min", tz="UTC")
    expected = pd.Series([0.0, 2e-5, 0.0])
    actual = pd.Series([0.0, 0.0, 3e-5])

    df = calculate_performance("wind_park_01", "wind", ts, expected, actual)

    assert (df["performance_ratio"] == 1.0).all()
    assert (df["percentage_deviation"] == 0.0).all()
    assert not df["zero_expected_edge_case"].any()


def test_5_underperformance_pure_calculation():
    """Case 5: Underperformance (actual well below expected) -> correct ratio, no crash, no classification."""
    ts = pd.date_range("2026-06-01 14:00", periods=2, freq="15min", tz="UTC")
    expected = pd.Series([10.0, 8.0])
    actual = pd.Series([3.0, 2.0])

    df = calculate_performance("wind_park_01", "wind", ts, expected, actual)

    np.testing.assert_allclose(df["performance_ratio"], [0.3, 0.25], atol=1e-6)
    np.testing.assert_allclose(df["absolute_deviation"], [-7.0, -6.0], atol=1e-6)
    np.testing.assert_allclose(df["percentage_deviation"], [-70.0, -75.0], atol=1e-6)
    assert not df["zero_expected_edge_case"].any()
    # Ensure no classification columns are added by this pure layer
    assert "anomaly" not in df.columns
    assert "diagnostic_category" not in df.columns


def test_input_validation_mismatched_lengths():
    """Verify ValueError is raised on mismatched input lengths."""
    ts = pd.date_range("2026-01-01", periods=3, freq="15min")
    exp = pd.Series([1.0, 2.0])
    act = pd.Series([1.0, 2.0, 3.0])

    with pytest.raises(ValueError, match="Input length mismatch"):
        calculate_performance("asset_01", "solar", ts, exp, act)


def test_input_validation_invalid_asset_type():
    """Verify ValueError is raised on invalid asset type."""
    ts = pd.date_range("2026-01-01", periods=1, freq="15min")
    with pytest.raises(ValueError, match="Invalid asset_type"):
        calculate_performance("asset_01", "nuclear", ts, pd.Series([1.0]), pd.Series([1.0]))


def test_empty_series():
    """Verify calculate_performance handles empty input series gracefully."""
    df = calculate_performance(
        "asset_01",
        "solar",
        pd.Series([], dtype="datetime64[ns]"),
        pd.Series([], dtype=float),
        pd.Series([], dtype=float),
    )
    assert list(df.columns) == list(PERFORMANCE_COLUMNS)
    assert len(df) == 0


def test_get_renewable_status_partial():
    """Verify get_renewable_status_partial maps fields correctly to RenewableStatus shape."""
    ts = pd.Timestamp("2026-06-01 12:00:00+00:00")
    row = pd.Series({
        "asset_id": "solar_01",
        "asset_type": "solar",
        "timestamp": ts,
        "expected_mw": 5.0,
        "actual_mw": 4.5,
        "performance_ratio": 0.9,
    })

    partial = get_renewable_status_partial(row)

    assert partial["assetId"] == "solar_01"
    assert partial["assetType"] == "solar"
    assert partial["expectedMw"] == 5.0
    assert partial["actualMw"] == 4.5
    assert partial["performanceRatio"] == 0.9
    assert partial["anomaly"] is None
    assert partial["likelyRootCause"] is None


def test_get_renewable_status_partial_with_nan_ratio():
    """Verify get_renewable_status_partial converts NaN ratio to None."""
    row = pd.Series({
        "asset_id": "solar_01",
        "asset_type": "solar",
        "timestamp": "2026-06-01T01:00:00Z",
        "expected_mw": 0.0,
        "actual_mw": 2.0,
        "performance_ratio": np.nan,
    })
    partial = get_renewable_status_partial(row)
    assert partial["performanceRatio"] is None
