"""Adapter for the hourly Kaggle Power System Modelling time series.

The source contains aggregate country, control-area, and bidding-zone series,
not physical renewable-asset telemetry. This module deliberately remains
separate from the OpenSTEF loader and does not create forecasts, anomalies, or
root-cause labels.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd


SOURCE_NAME = "kaggle_power_system"
DEFAULT_RESOLUTION = "60min"
EXPECTED_FREQUENCIES = {
    "15min": pd.Timedelta(minutes=15),
    "30min": pd.Timedelta(minutes=30),
    "60min": pd.Timedelta(hours=1),
}
NORMALIZED_COLUMNS = ("timestamp", "asset_id", "energy_type", "actual_mw", "capacity_mw", "source")
GENERATION_PATTERN = re.compile(
    r"^(?P<region>.+)_(?P<energy_type>solar|wind)(?:_(?:onshore|offshore))?_generation_actual$"
)


class KaggleDataValidationError(ValueError):
    """Raised when source timestamps or renewable schema are unsafe to load."""


@dataclass(frozen=True)
class KaggleRenewableSchema:
    """Discovered generation and matching capacity columns."""

    generation_columns: tuple[str, ...]
    capacity_by_generation: dict[str, str | None]

    @property
    def solar_columns(self) -> tuple[str, ...]:
        return tuple(column for column in self.generation_columns if "_solar_" in column)

    @property
    def wind_columns(self) -> tuple[str, ...]:
        return tuple(column for column in self.generation_columns if "_wind" in column)


@dataclass
class KaggleValidationReport:
    """Quality facts collected while scanning one source CSV."""

    path: str
    resolution: str
    row_count: int = 0
    normalized_row_count: int = 0
    solar_series_count: int = 0
    wind_series_count: int = 0
    series_with_capacity: int = 0
    series_without_capacity: int = 0
    timestamp_start: str | None = None
    timestamp_end: str | None = None
    duplicate_timestamp_count: int = 0
    invalid_timestamp_count: int = 0
    missing_timestamp_count: int = 0
    irregular_interval_count: int = 0
    missing_generation_value_count: int = 0
    missing_capacity_value_count: int = 0
    weather_available: bool = False
    curtailment_available: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def kaggle_csv_path(dataset_dir: str | Path, resolution: str = DEFAULT_RESOLUTION) -> Path:
    """Return the extracted CSV path for a supported dataset resolution."""
    if resolution not in EXPECTED_FREQUENCIES:
        raise ValueError(f"Unsupported resolution {resolution!r}; choose one of {tuple(EXPECTED_FREQUENCIES)}")
    path = Path(dataset_dir) / f"time_series_{resolution}_singleindex.csv"
    if not path.exists():
        raise FileNotFoundError(f"Kaggle time-series file not found: {path}")
    return path


def discover_kaggle_schema(path: str | Path) -> KaggleRenewableSchema:
    """Discover all supported solar/wind generation and capacity columns."""
    columns = pd.read_csv(path, nrows=0).columns.tolist()
    generation_columns = tuple(column for column in columns if GENERATION_PATTERN.match(column))
    if not generation_columns:
        raise KaggleDataValidationError(f"No renewable generation columns found in {path}")
    capacity_columns = {column for column in columns if column.endswith("_capacity")}
    capacity_by_generation = {
        generation: generation.removesuffix("_generation_actual") + "_capacity"
        if generation.removesuffix("_generation_actual") + "_capacity" in capacity_columns
        else None
        for generation in generation_columns
    }
    return KaggleRenewableSchema(generation_columns, capacity_by_generation)


def _normalized_chunk(chunk: pd.DataFrame, schema: KaggleRenewableSchema) -> pd.DataFrame:
    """Convert one wide source chunk into normalized aggregate-series rows."""
    records: list[pd.DataFrame] = []
    timestamps = chunk["utc_timestamp"]
    for generation_column in schema.generation_columns:
        match = GENERATION_PATTERN.match(generation_column)
        assert match is not None
        capacity_column = schema.capacity_by_generation[generation_column]
        records.append(
            pd.DataFrame(
                {
                    "timestamp": timestamps.to_numpy(),
                    "asset_id": generation_column,
                    "energy_type": match.group("energy_type"),
                    "actual_mw": pd.to_numeric(chunk[generation_column], errors="coerce").to_numpy(),
                    "capacity_mw": (
                        pd.to_numeric(chunk[capacity_column], errors="coerce").to_numpy()
                        if capacity_column is not None
                        else np.nan
                    ),
                    "source": SOURCE_NAME,
                }
            )
        )
    return pd.concat(records, ignore_index=True)[list(NORMALIZED_COLUMNS)]


def iter_kaggle_renewable_chunks(
    dataset_dir: str | Path,
    resolution: str = DEFAULT_RESOLUTION,
    chunksize: int = 10_000,
) -> Iterator[pd.DataFrame]:
    """Yield normalized renewable records while streaming the wide CSV."""
    if chunksize < 1:
        raise ValueError("chunksize must be a positive integer")
    path = kaggle_csv_path(dataset_dir, resolution)
    schema = discover_kaggle_schema(path)
    seen_timestamps: set[pd.Timestamp] = set()
    previous_timestamp: pd.Timestamp | None = None

    for chunk in pd.read_csv(path, chunksize=chunksize):
        if "utc_timestamp" not in chunk.columns:
            raise KaggleDataValidationError(f"Missing utc_timestamp column in {path}")
        timestamps = pd.to_datetime(chunk["utc_timestamp"], utc=True, errors="coerce")
        if timestamps.isna().any():
            raise KaggleDataValidationError(
                f"Invalid UTC timestamps in {path}: {int(timestamps.isna().sum())} rows"
            )
        timestamp_values = list(timestamps)
        duplicate_count = int(timestamps.duplicated().sum()) + sum(
            timestamp in seen_timestamps for timestamp in timestamp_values
        )
        if duplicate_count:
            raise KaggleDataValidationError(f"Duplicate UTC timestamps in {path}: {duplicate_count}")
        seen_timestamps.update(timestamp_values)
        if previous_timestamp is not None and timestamps.iloc[0] <= previous_timestamp:
            raise KaggleDataValidationError(f"Timestamps are not strictly increasing in {path}")
        previous_timestamp = timestamps.iloc[-1]
        chunk = chunk.copy()
        chunk["utc_timestamp"] = timestamps
        yield _normalized_chunk(chunk, schema)


def validate_kaggle_dataset(
    dataset_dir: str | Path,
    resolution: str = DEFAULT_RESOLUTION,
    chunksize: int = 10_000,
) -> KaggleValidationReport:
    """Scan source quality without materializing the normalized dataset."""
    path = kaggle_csv_path(dataset_dir, resolution)
    schema = discover_kaggle_schema(path)
    report = KaggleValidationReport(
        path=str(path),
        resolution=resolution,
        solar_series_count=len(schema.solar_columns),
        wind_series_count=len(schema.wind_columns),
        series_with_capacity=sum(value is not None for value in schema.capacity_by_generation.values()),
        series_without_capacity=sum(value is None for value in schema.capacity_by_generation.values()),
    )
    expected_frequency = EXPECTED_FREQUENCIES[resolution]
    previous_timestamp: pd.Timestamp | None = None
    seen_timestamps: set[pd.Timestamp] = set()
    matched_capacity = [column for column in schema.capacity_by_generation.values() if column is not None]

    for chunk in pd.read_csv(path, chunksize=chunksize):
        if "utc_timestamp" not in chunk.columns:
            raise KaggleDataValidationError(f"Missing utc_timestamp column in {path}")
        timestamps = pd.to_datetime(chunk["utc_timestamp"], utc=True, errors="coerce")
        report.row_count += len(chunk)
        report.invalid_timestamp_count += int(timestamps.isna().sum())
        if timestamps.isna().any():
            raise KaggleDataValidationError(f"Invalid UTC timestamps in {path}")
        report.duplicate_timestamp_count += int(timestamps.duplicated().sum())
        report.duplicate_timestamp_count += sum(timestamp in seen_timestamps for timestamp in timestamps)
        seen_timestamps.update(timestamps)
        if report.duplicate_timestamp_count:
            raise KaggleDataValidationError(
                f"Duplicate UTC timestamps in {path}: {report.duplicate_timestamp_count}"
            )
        if previous_timestamp is not None:
            delta = timestamps.iloc[0] - previous_timestamp
            if delta != expected_frequency:
                report.irregular_interval_count += 1
                if delta > expected_frequency:
                    report.missing_timestamp_count += max(int(delta / expected_frequency) - 1, 0)
        deltas = timestamps.diff().dropna()
        irregular = deltas[deltas != expected_frequency]
        report.irregular_interval_count += len(irregular)
        report.missing_timestamp_count += sum(
            max(int(delta / expected_frequency) - 1, 0) for delta in irregular if delta > expected_frequency
        )
        previous_timestamp = timestamps.iloc[-1]
        report.timestamp_start = report.timestamp_start or timestamps.iloc[0].isoformat()
        report.timestamp_end = timestamps.iloc[-1].isoformat()
        report.missing_generation_value_count += int(chunk[list(schema.generation_columns)].isna().sum().sum())
        report.missing_capacity_value_count += int(chunk[matched_capacity].isna().sum().sum()) if matched_capacity else 0

    report.normalized_row_count = report.row_count * len(schema.generation_columns)
    return report


def load_kaggle_renewable_data(
    dataset_dir: str | Path,
    resolution: str = DEFAULT_RESOLUTION,
    chunksize: int = 10_000,
) -> tuple[pd.DataFrame, KaggleValidationReport]:
    """Load normalized aggregate renewable rows and their quality report."""
    report = validate_kaggle_dataset(dataset_dir, resolution, chunksize)
    chunks = list(iter_kaggle_renewable_chunks(dataset_dir, resolution, chunksize))
    records = pd.concat(chunks, ignore_index=True)
    records["timestamp"] = pd.to_datetime(records["timestamp"], utc=True)
    records = records.sort_values(["timestamp", "asset_id"], kind="stable").reset_index(drop=True)
    return records, report