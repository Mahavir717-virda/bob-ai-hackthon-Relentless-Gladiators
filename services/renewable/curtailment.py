"""Curtailment-aware, evidence-limited renewable performance diagnostics.

OpenSTEF does not expose a curtailment, maintenance, or inverter-health flag.
Consequently, this module never infers intentional curtailment from reduced
generation.  It only reports that category when a caller supplies an explicit
indicator column.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .constants import (
    HIGH_CLOUD_COVER_PERCENT,
    LOW_WIND_SPEED_MPS,
    PERFORMANCE_RATIO_LOWER_WARN,
    PERFORMANCE_RATIO_NORMAL_LOWER,
    PERFORMANCE_RATIO_NORMAL_UPPER,
    PERSISTENT_LOW_PERFORMANCE_INTERVALS,
)

logger = logging.getLogger(__name__)

_REQUIRED_COLUMNS = {
    "asset_id",
    "asset_type",
    "timestamp",
    "actual_mw",
    "performance_ratio",
    "zero_expected_edge_case",
}


def _consecutive_low_count(values: pd.Series) -> pd.Series:
    """Count consecutive true values in one already time-sorted asset series."""
    groups = (~values).cumsum()
    return values.astype(int).groupby(groups).cumsum()


def _weather_for_performance(
    performance_df: pd.DataFrame, weather_df: pd.DataFrame | None
) -> pd.DataFrame:
    """Attach same-timestamp weather without changing the performance row count."""
    if weather_df is None:
        return performance_df.copy()
    if "timestamp" not in weather_df.columns:
        logger.warning("Weather data has no timestamp; weather evidence is unavailable.")
        return performance_df.copy()

    weather = weather_df.copy()
    weather["timestamp"] = pd.to_datetime(weather["timestamp"], utc=True)
    performance = performance_df.copy()
    performance["timestamp"] = pd.to_datetime(performance["timestamp"], utc=True)

    keys = ["timestamp"]
    if "asset_id" in weather.columns:
        keys.append("asset_id")
    # De-duplicate so a malformed weather input cannot multiply diagnostics.
    weather = weather.drop_duplicates(subset=keys, keep="last")
    return performance.merge(weather, how="left", on=keys, suffixes=("", "_weather"))


def classify_deviation(
    performance_df: pd.DataFrame,
    weather_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Classify generation deviations using only observable evidence.

    Low performance gets a physical-fault label only after persistent (four or
    more interval) evidence.  A single unexplained reduction remains uncertain.
    Explicit curtailment flags are intentionally handled separately by
    :func:`add_curtailment_flag_if_available`.
    """
    missing = _REQUIRED_COLUMNS.difference(performance_df.columns)
    if missing:
        raise ValueError(f"performance_df is missing required columns: {sorted(missing)}")

    input_columns = list(performance_df.columns)
    result = _weather_for_performance(performance_df, weather_df)
    result["_input_order"] = np.arange(len(result))
    result = result.sort_values(["asset_id", "timestamp", "_input_order"]).copy()

    ratio = pd.to_numeric(result["performance_ratio"], errors="coerce")
    actual = pd.to_numeric(result["actual_mw"], errors="coerce")
    invalid = (
        result["zero_expected_edge_case"].fillna(False).astype(bool)
        | ~np.isfinite(ratio)
        | (actual < 0)
    )
    low = (ratio < PERFORMANCE_RATIO_LOWER_WARN) & ~invalid
    result["_low_run"] = low.groupby(result["asset_id"], group_keys=False).transform(
        _consecutive_low_count
    )
    persistent_low = result["_low_run"] >= PERSISTENT_LOW_PERFORMANCE_INTERVALS

    category = pd.Series("uncertain", index=result.index, dtype="object")
    confidence = pd.Series(0.25, index=result.index, dtype=float)

    normal = ratio.between(PERFORMANCE_RATIO_NORMAL_LOWER, PERFORMANCE_RATIO_NORMAL_UPPER)
    category.loc[normal & ~invalid] = "normal_production"
    confidence.loc[normal & ~invalid] = 0.95

    weather_explained = pd.Series(False, index=result.index)
    weather_confidence = pd.Series(0.0, index=result.index)
    if "cloud_cover" in result.columns:
        cloud = pd.to_numeric(result["cloud_cover"], errors="coerce")
        solar_weather = (result["asset_type"] == "solar") & (cloud >= HIGH_CLOUD_COVER_PERCENT)
        weather_explained |= solar_weather
        weather_confidence = weather_confidence.where(~solar_weather, 0.80 + 0.15 * (cloud / 100.0))
    for wind_column in ("wind_speed_10m", "wind_speed"):
        if wind_column in result.columns:
            wind_speed = pd.to_numeric(result[wind_column], errors="coerce")
            wind_weather = (result["asset_type"] == "wind") & (wind_speed <= LOW_WIND_SPEED_MPS)
            weather_explained |= wind_weather
            weather_confidence = weather_confidence.where(~wind_weather, 0.90)
            break

    weather_reduction = low & weather_explained
    category.loc[weather_reduction] = "weather_driven_reduction"
    confidence.loc[weather_reduction] = weather_confidence.loc[weather_reduction]

    fault = persistent_low & ~weather_explained
    category.loc[fault] = "possible_physical_fault"
    confidence.loc[fault] = 0.70

    category.loc[invalid] = "data_quality_issue"
    confidence.loc[invalid] = 0.98

    result["diagnostic_category"] = category
    result["diagnostic_confidence"] = confidence.clip(0.0, 1.0)
    result = result.sort_values("_input_order")
    return result.loc[:, input_columns + ["diagnostic_category", "diagnostic_confidence"]]


def add_curtailment_flag_if_available(
    df: pd.DataFrame,
    curtailment_column: str | None = None,
) -> pd.DataFrame:
    """Apply explicit curtailment evidence, or visibly decline to infer it.

    A true flag overrides ratio-based diagnostics because it is direct
    operational evidence.  Missing flags leave every existing category intact.
    """
    if not curtailment_column or curtailment_column not in df.columns:
        logger.info(
            "Curtailment suppression unavailable: no explicit curtailment indicator column was supplied."
        )
        return df.copy()
    if "diagnostic_category" not in df.columns or "diagnostic_confidence" not in df.columns:
        raise ValueError("Run classify_deviation before applying a curtailment flag.")

    result = df.copy()
    values = result[curtailment_column]
    if pd.api.types.is_bool_dtype(values):
        flagged = values.fillna(False)
    elif pd.api.types.is_numeric_dtype(values):
        flagged = values.fillna(0).ne(0)
    else:
        flagged = values.astype("string").str.strip().str.lower().isin({"true", "1", "yes", "y", "flagged"})
    result.loc[flagged, "diagnostic_category"] = "intentional_curtailment"
    result.loc[flagged, "diagnostic_confidence"] = 0.98
    return result
