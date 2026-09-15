"""Deterministic tests for the isolated Kaggle renewable adapter."""

from pathlib import Path

import pandas as pd
import pytest

from services.renewable.kaggle_data_loader import (
    KaggleDataValidationError,
    load_kaggle_renewable_data,
    validate_kaggle_dataset,
)


def _write_fixture(tmp_path: Path, rows: list[dict]) -> Path:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    pd.DataFrame(rows).to_csv(dataset / "time_series_60min_singleindex.csv", index=False)
    return dataset


def test_loads_solar_wind_and_matches_capacity(tmp_path: Path):
    dataset = _write_fixture(
        tmp_path,
        [
            {
                "utc_timestamp": "2020-01-01T00:00:00Z",
                "DE_solar_generation_actual": 10.5,
                "DE_solar_capacity": 100.0,
                "AT_wind_onshore_generation_actual": 20.0,
            },
            {
                "utc_timestamp": "2020-01-01T01:00:00Z",
                "DE_solar_generation_actual": None,
                "DE_solar_capacity": 100.0,
                "AT_wind_onshore_generation_actual": 21.0,
            },
        ],
    )
    records, report = load_kaggle_renewable_data(dataset)

    assert set(records["asset_id"]) == {
        "DE_solar_generation_actual",
        "AT_wind_onshore_generation_actual",
    }
    solar = records[records.asset_id == "DE_solar_generation_actual"].sort_values("timestamp")
    wind = records[records.asset_id == "AT_wind_onshore_generation_actual"].sort_values("timestamp")
    assert solar.energy_type.tolist() == ["solar", "solar"]
    assert wind.energy_type.tolist() == ["wind", "wind"]
    assert solar.capacity_mw.tolist() == [100.0, 100.0]
    assert wind.capacity_mw.isna().all()
    assert pd.isna(solar.actual_mw.iloc[1])
    assert report.series_with_capacity == 1
    assert report.series_without_capacity == 1
    assert report.weather_available is False
    assert report.curtailment_available is False


def test_rejects_duplicate_timestamps(tmp_path: Path):
    dataset = _write_fixture(
        tmp_path,
        [
            {"utc_timestamp": "2020-01-01T00:00:00Z", "DE_solar_generation_actual": 1.0},
            {"utc_timestamp": "2020-01-01T00:00:00Z", "DE_solar_generation_actual": 2.0},
        ],
    )
    with pytest.raises(KaggleDataValidationError, match="Duplicate"):
        validate_kaggle_dataset(dataset)


def test_rejects_invalid_timestamp(tmp_path: Path):
    dataset = _write_fixture(
        tmp_path,
        [{"utc_timestamp": "not-a-timestamp", "DE_solar_generation_actual": 1.0}],
    )
    with pytest.raises(KaggleDataValidationError, match="Invalid UTC timestamps"):
        validate_kaggle_dataset(dataset)


def test_reports_missing_timestamp_without_filling_generation(tmp_path: Path):
    dataset = _write_fixture(
        tmp_path,
        [
            {"utc_timestamp": "2020-01-01T00:00:00Z", "DE_solar_generation_actual": 1.0},
            {"utc_timestamp": "2020-01-01T02:00:00Z", "DE_solar_generation_actual": None},
        ],
    )
    records, report = load_kaggle_renewable_data(dataset)

    assert report.missing_timestamp_count == 1
    assert report.missing_generation_value_count == 1
    assert len(records) == 2
    assert pd.isna(records.loc[records.actual_mw.isna(), "actual_mw"]).all()


def test_real_hourly_file_has_expected_adapter_shape():
    dataset = Path(__file__).resolve().parents[3] / "ml" / "datasets" / "kaggle_power_system"
    if not (dataset / "time_series_60min_singleindex.csv").exists():
        pytest.skip("Kaggle dataset is not available in this checkout")

    report = validate_kaggle_dataset(dataset)
    assert report.solar_series_count == 39
    assert report.wind_series_count == 82
    assert report.series_with_capacity == 20
    assert report.series_without_capacity == 101
    assert report.row_count == 50_401
    assert report.normalized_row_count == 50_401 * 121
    assert report.duplicate_timestamp_count == 0
    assert report.missing_timestamp_count == 0
    assert report.weather_available is False
    assert report.curtailment_available is False