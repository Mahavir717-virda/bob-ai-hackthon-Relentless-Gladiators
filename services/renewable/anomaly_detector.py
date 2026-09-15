"""Isolation Forest anomaly detection for renewable performance telemetry.

The detector uses ``IsolationForest.decision_function`` as its score: values
below zero fall on the fitted contamination boundary and are more anomalous;
larger values are more typical.  The default 5% contamination is a
conservative operational starting point for a system where genuine outages
should be uncommon.  It remains a caller-tunable parameter.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from .constants import PERSISTENT_LOW_PERFORMANCE_INTERVALS, RANDOM_SEED
from .curtailment import classify_deviation

logger = logging.getLogger(__name__)

DEFAULT_ANOMALY_CONTAMINATION: float = 0.05
"""Expected proportion of unexplained anomalous observations (5%)."""

_PERFORMANCE_COLUMNS = {
    "asset_id", "asset_type", "timestamp", "actual_mw", "expected_mw",
    "absolute_deviation", "percentage_deviation", "performance_ratio",
    "zero_expected_edge_case",
}
_DIAGNOSTIC_COLUMNS = {"diagnostic_category", "diagnostic_confidence"}


def _attach_weather(df: pd.DataFrame, weather_df: pd.DataFrame | None) -> pd.DataFrame:
    """Attach optional weather data for feature construction without row growth."""
    if weather_df is None or "timestamp" not in weather_df.columns:
        return df.copy()
    left = df.copy()
    weather = weather_df.copy()
    left["timestamp"] = pd.to_datetime(left["timestamp"], utc=True)
    weather["timestamp"] = pd.to_datetime(weather["timestamp"], utc=True)
    keys = ["timestamp"] + (["asset_id"] if "asset_id" in weather.columns else [])
    weather = weather.drop_duplicates(keys, keep="last")
    return left.merge(weather, on=keys, how="left", suffixes=("", "_weather"))


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build model features only from performance metrics and optional weather."""
    work = df.sort_values(["asset_id", "timestamp", "_input_order"]).copy()
    ratio = pd.to_numeric(work["performance_ratio"], errors="coerce")
    ratio = ratio.where(np.isfinite(ratio))
    work["rolling_performance_ratio"] = ratio.groupby(work["asset_id"], group_keys=False).transform(
        lambda values: values.rolling(PERSISTENT_LOW_PERFORMANCE_INTERVALS, min_periods=1).mean()
    )
    features = pd.DataFrame(index=work.index)
    for column in (
        "actual_mw", "expected_mw", "absolute_deviation", "percentage_deviation", "performance_ratio",
        "rolling_performance_ratio",
    ):
        values = pd.to_numeric(work[column], errors="coerce")
        features[column] = values.where(np.isfinite(values))

    # Weather features are populated only for the asset type they physically
    # describe; missing values are median-imputed from fitting observations.
    if "cloud_cover" in work.columns:
        cloud = pd.to_numeric(work["cloud_cover"], errors="coerce")
        features["solar_cloud_cover"] = cloud.where(work["asset_type"].eq("solar"))
    for wind_column in ("wind_speed_10m", "wind_speed"):
        if wind_column in work.columns:
            speed = pd.to_numeric(work[wind_column], errors="coerce")
            features["wind_speed"] = speed.where(work["asset_type"].eq("wind"))
            break
    return features.reindex(df.index)


def _median_impute(features: pd.DataFrame, fit_mask: pd.Series) -> pd.DataFrame:
    """Impute finite numeric feature values without allowing bad rows into fit."""
    clean = features.replace([np.inf, -np.inf], np.nan).copy()
    medians = clean.loc[fit_mask].median(axis=0).fillna(0.0)
    return clean.fillna(medians).fillna(0.0)


def detect_anomalies(
    performance_df: pd.DataFrame,
    diagnostic_df: pd.DataFrame,
    weather_df: pd.DataFrame | None = None,
    contamination: float = DEFAULT_ANOMALY_CONTAMINATION,
    suppress_curtailment: bool = True,
) -> pd.DataFrame:
    """Detect unexplained operational anomalies with a deterministic forest.

    Data-quality rows remain present and are force-flagged, but are excluded
    from model fitting.  Explicitly curtailed rows are excluded and marked
    with a suppression reason by default; set ``suppress_curtailment=False``
    to include and evaluate them normally.
    """
    missing_perf = _PERFORMANCE_COLUMNS.difference(performance_df.columns)
    missing_diag = _PERFORMANCE_COLUMNS.union(_DIAGNOSTIC_COLUMNS).difference(diagnostic_df.columns)
    if missing_perf:
        raise ValueError(f"performance_df is missing required columns: {sorted(missing_perf)}")
    if missing_diag:
        raise ValueError(f"diagnostic_df is missing required columns: {sorted(missing_diag)}")
    if not 0.0 < contamination <= 0.5:
        raise ValueError("contamination must be greater than 0 and no greater than 0.5")
    if len(performance_df) != len(diagnostic_df):
        raise ValueError("performance_df and diagnostic_df must contain the same number of rows")

    key_columns = ["asset_id", "asset_type", "timestamp"]
    if not performance_df[key_columns].reset_index(drop=True).equals(
        diagnostic_df[key_columns].reset_index(drop=True)
    ):
        raise ValueError("performance_df and diagnostic_df must be row-aligned outputs of the same calculation")

    input_columns = list(diagnostic_df.columns)
    working = _attach_weather(diagnostic_df, weather_df)
    working["_input_order"] = np.arange(len(working))
    features = _build_features(working)

    data_quality = (
        working["zero_expected_edge_case"].fillna(False).astype(bool)
        | working["diagnostic_category"].eq("data_quality_issue")
    )
    curtailed = working["diagnostic_category"].eq("intentional_curtailment")
    suppressed = curtailed & suppress_curtailment
    fit_mask = ~(data_quality | suppressed)
    imputed_features = _median_impute(features, fit_mask)

    scores = pd.Series(0.0, index=working.index, dtype=float)
    model_flags = pd.Series(False, index=working.index, dtype=bool)
    # A forest needs at least two observations to establish a comparative
    # boundary.  Small batches therefore remain non-anomalous unless a
    # data-quality rule explicitly flags them.
    if int(fit_mask.sum()) >= 2:
        model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=RANDOM_SEED,
            n_jobs=1,
        )
        model.fit(imputed_features.loc[fit_mask])
        scores.loc[fit_mask] = model.decision_function(imputed_features.loc[fit_mask])
        model_flags.loc[fit_mask] = model.predict(imputed_features.loc[fit_mask]) == -1
    else:
        logger.info("Insufficient eligible rows for Isolation Forest fitting: %d", int(fit_mask.sum()))

    anomaly = model_flags.copy()
    # A diagnostic already supported by weather is operationally explainable,
    # so it is not surfaced as an unexplained anomaly.
    anomaly.loc[working["diagnostic_category"].eq("weather_driven_reduction")] = False
    anomaly.loc[suppressed] = False
    anomaly.loc[data_quality] = True

    reason = pd.Series(None, index=working.index, dtype="object")
    reason.loc[suppressed] = "intentional_curtailment"
    result = working.sort_values("_input_order")
    result["anomaly_score"] = scores.loc[result.index].astype(float)
    result["anomaly"] = anomaly.loc[result.index].astype(bool)
    result["anomaly_suppressed_reason"] = reason.loc[result.index]
    return result.loc[:, input_columns + ["anomaly_score", "anomaly", "anomaly_suppressed_reason"]]


def detectAnomalies(time_range_df: pd.DataFrame) -> list[dict]:
    """Return RenewableStatus-compatible anomaly fields for a time-range batch."""
    diagnostic = (
        time_range_df
        if _DIAGNOSTIC_COLUMNS.issubset(time_range_df.columns)
        else classify_deviation(time_range_df)
    )
    detected = detect_anomalies(time_range_df, diagnostic)
    return [
        {
            "assetId": str(row.asset_id),
            "timestamp": row.timestamp.isoformat() if hasattr(row.timestamp, "isoformat") else str(row.timestamp),
            "anomaly": bool(row.anomaly),
            "anomaly_score": float(row.anomaly_score),
        }
        for row in detected[["asset_id", "timestamp", "anomaly", "anomaly_score"]].itertuples(index=False)
    ]
