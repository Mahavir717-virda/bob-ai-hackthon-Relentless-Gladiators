"""
GridPilot AI — Demand Forecasting Feature Engineering Pipeline
==============================================================
Module Version: 1.0.0
Author: Member 2 (Data + Demand Forecasting)

Provides reusable, versioned feature engineering for:
  - Chunk 5: LightGBM Demand Forecasting (15m, 30m, 60m horizons)
  - Chunk 7: XGBoost Demand Spike Classifier

Strict Leakage Prevention Guarantee:
-------------------------------------
Every lag and rolling feature is constructed exclusively from PAST
information. At any row index t, computed features NEVER reference
row t or any row > t. Rolling statistics are strictly evaluated over
already-shifted (past) series: series.shift(1).rolling(w).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

from services.forecasting.holidays import is_dutch_holiday

FEATURE_PIPELINE_VERSION = "1.0.0"


@dataclass
class FeatureConfig:
    """Configuration for demand forecasting feature generation."""
    target_col: str = "demand_mw"
    timestamp_col: str = "timestamp"
    asset_col: Optional[str] = "asset_id"
    freq_minutes: int = 15

    # Required lag offsets in minutes (15m, 30m, 60m, 1440m = 24h)
    lag_minutes: List[int] = field(default_factory=lambda: [15, 30, 60, 1440])

    # Past-only rolling window sizes in periods (4 = 1hr, 16 = 4hr, 96 = 24hr)
    rolling_windows: List[int] = field(default_factory=lambda: [4, 16, 96])

    # Rolling aggregations to compute
    rolling_stats: List[str] = field(default_factory=lambda: ["mean", "std", "min", "max"])

    # Include past-only momentum / acceleration features
    include_momentum: bool = True

    # Confirmed weather features from OpenMeteo (docs/data/openstef-demand.md)
    weather_cols: List[str] = field(
        default_factory=lambda: [
            "temperature_2m",
            "relative_humidity_2m",
            "cloud_cover",
            "wind_speed_10m",
            "shortwave_radiation",
        ]
    )

    # Optional additional weather predictors
    optional_weather_cols: List[str] = field(
        default_factory=lambda: [
            "surface_pressure",
            "wind_direction_10m",
            "direct_radiation",
            "diffuse_radiation",
            "direct_normal_irradiance",
        ]
    )

    # Cyclical sin/cos encodings for hour and day of week
    include_cyclical: bool = True


class DemandFeaturePipeline:
    """
    Production, versioned feature engineering pipeline.

    Imports cleanly into downstream training and serving pipelines:
      from services.forecasting.features import DemandFeaturePipeline
    """

    def __init__(self, config: Optional[FeatureConfig] = None) -> None:
        self.config = config or FeatureConfig()
        self.version = FEATURE_PIPELINE_VERSION
        self.feature_names_: List[str] = []
        self.numeric_features_: List[str] = []
        self.categorical_features_: List[str] = []

    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add strictly past lag features.
        For lag L minutes, shift is L // freq_minutes.
        Never uses current (t) or future (> t) values.
        """
        df = df.copy()
        target = self.config.target_col
        freq = self.config.freq_minutes
        group_col = self.config.asset_col if self.config.asset_col in df.columns else None

        for lag_min in self.config.lag_minutes:
            steps = int(lag_min / freq)
            col_name = f"{target}_lag_{lag_min}m"
            if group_col:
                df[col_name] = df.groupby(group_col)[target].shift(steps)
            else:
                df[col_name] = df[target].shift(steps)

        return df

    def _add_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add past-only rolling statistics.
        CRITICAL: The rolling window is applied to series.shift(1).
        At row t, the window covers t-w through t-1.
        Row t is never included in the rolling calculation.
        """
        df = df.copy()
        target = self.config.target_col
        group_col = self.config.asset_col if self.config.asset_col in df.columns else None

        # Shift target by 1 step so rolling window is strictly in the past
        if group_col:
            shifted_target = df.groupby(group_col)[target].shift(1)
        else:
            shifted_target = df[target].shift(1)

        for w in self.config.rolling_windows:
            if "mean" in self.config.rolling_stats:
                col_name = f"{target}_roll_mean_{w}"
                if group_col:
                    df[col_name] = (
                        shifted_target.groupby(df[group_col])
                        .rolling(w)
                        .mean()
                        .reset_index(level=0, drop=True)
                    )
                else:
                    df[col_name] = shifted_target.rolling(w).mean()

            if "std" in self.config.rolling_stats:
                col_name = f"{target}_roll_std_{w}"
                if group_col:
                    df[col_name] = (
                        shifted_target.groupby(df[group_col])
                        .rolling(w)
                        .std()
                        .reset_index(level=0, drop=True)
                    )
                else:
                    df[col_name] = shifted_target.rolling(w).std()

            if "min" in self.config.rolling_stats:
                col_name = f"{target}_roll_min_{w}"
                if group_col:
                    df[col_name] = (
                        shifted_target.groupby(df[group_col])
                        .rolling(w)
                        .min()
                        .reset_index(level=0, drop=True)
                    )
                else:
                    df[col_name] = shifted_target.rolling(w).min()

            if "max" in self.config.rolling_stats:
                col_name = f"{target}_roll_max_{w}"
                if group_col:
                    df[col_name] = (
                        shifted_target.groupby(df[group_col])
                        .rolling(w)
                        .max()
                        .reset_index(level=0, drop=True)
                    )
                else:
                    df[col_name] = shifted_target.rolling(w).max()

        return df

    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute past-only rate of change / momentum:
          - diff_15m: lag_15m - lag_30m (recent 15-min slope)
          - diff_1h: lag_15m - lag_60m (recent 1-hour slope)
        Both components are purely past values.
        """
        df = df.copy()
        target = self.config.target_col
        lag_15 = f"{target}_lag_15m"
        lag_30 = f"{target}_lag_30m"
        lag_60 = f"{target}_lag_60m"

        if lag_15 in df.columns and lag_30 in df.columns:
            df[f"{target}_diff_15m"] = df[lag_15] - df[lag_30]

        if lag_15 in df.columns and lag_60 in df.columns:
            df[f"{target}_diff_1h"] = df[lag_15] - df[lag_60]

        return df

    def _add_calendar_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add calendar and temporal features based on interval timestamp:
          - hour: 0-23
          - day_of_week: 0 (Monday) to 6 (Sunday)
          - is_weekend: 1 if Sat/Sun else 0
          - is_holiday: 1 if Dutch official holiday else 0
          - season: 1 (winter), 2 (spring), 3 (summer), 4 (autumn)
          - cyclical representations: sin/cos for hour and day of week
        """
        df = df.copy()
        ts_col = self.config.timestamp_col
        ts_series = pd.to_datetime(df[ts_col], utc=True)

        df["hour"] = ts_series.dt.hour.astype(int)
        df["day_of_week"] = ts_series.dt.dayofweek.astype(int)
        df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)

        # Dutch official holiday flag
        df["is_holiday"] = ts_series.apply(is_dutch_holiday).astype(int)

        # Season classification:
        # Dec, Jan, Feb = 1 (Winter)
        # Mar, Apr, May = 2 (Spring)
        # Jun, Jul, Aug = 3 (Summer)
        # Sep, Oct, Nov = 4 (Autumn)
        month = ts_series.dt.month
        df["season"] = month.map(
            lambda m: 1 if m in (12, 1, 2) else (2 if m in (3, 4, 5) else (3 if m in (6, 7, 8) else 4))
        ).astype(int)

        if self.config.include_cyclical:
            # Hour cycle (24-hour period)
            df["sin_hour"] = np.sin(2 * np.pi * df["hour"] / 24.0)
            df["cos_hour"] = np.cos(2 * np.pi * df["hour"] / 24.0)

            # Day of week cycle (7-day period)
            df["sin_dow"] = np.sin(2 * np.pi * df["day_of_week"] / 7.0)
            df["cos_dow"] = np.cos(2 * np.pi * df["day_of_week"] / 7.0)

        return df

    def transform(
        self,
        df: pd.DataFrame,
        weather_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Generate all features from the cleaned canonical dataset.

        Parameters
        ----------
        df : pd.DataFrame
            Cleaned canonical demand dataset (must contain timestamp and target_col).
        weather_df : pd.DataFrame, optional
            Weather features DataFrame aligned on timestamp. If weather columns
            already exist in df, they will be utilized directly.

        Returns
        -------
        pd.DataFrame
            Feature-engineered dataset with strictly past features.
        """
        df = df.sort_values(self.config.timestamp_col).reset_index(drop=True)

        # If external weather data provided, merge on timestamp
        if weather_df is not None:
            w_df = weather_df.copy()
            if isinstance(w_df.index, pd.DatetimeIndex):
                if w_df.index.name == self.config.timestamp_col:
                    w_df = w_df.reset_index()
                elif self.config.timestamp_col not in w_df.columns:
                    w_df[self.config.timestamp_col] = w_df.index
                    w_df.index = pd.RangeIndex(len(w_df))
            elif self.config.timestamp_col in w_df.columns and w_df.index.name == self.config.timestamp_col:
                w_df.index.name = None

            # Identify weather columns to merge
            cols_to_merge = [
                c for c in w_df.columns
                if c != self.config.timestamp_col and c not in df.columns
            ]
            if cols_to_merge:
                df = pd.merge(df, w_df[[self.config.timestamp_col] + cols_to_merge], on=self.config.timestamp_col, how="left")

        # 1. Autoregressive lags (strictly past)
        df = self._add_lag_features(df)

        # 2. Rolling statistics (strictly past on shifted data)
        df = self._add_rolling_features(df)

        # 3. Momentum features
        if self.config.include_momentum:
            df = self._add_momentum_features(df)

        # 4. Calendar and holiday features
        df = self._add_calendar_features(df)

        # Catalog feature columns
        non_feature_cols = {
            self.config.timestamp_col,
            self.config.target_col,
            "available_at",
            "is_imputed",
            "is_out_of_range",
            "is_reverse_flow",
            "load",  # raw load Watts if target is demand_mw
            "demand_kw",
        }
        if self.config.asset_col:
            non_feature_cols.add(self.config.asset_col)
        if "group_name" in df.columns:
            non_feature_cols.add("group_name")

        self.feature_names_ = [c for c in df.columns if c not in non_feature_cols]
        self.categorical_features_ = [
            c for c in ["hour", "day_of_week", "season", "is_weekend", "is_holiday"]
            if c in self.feature_names_
        ]
        self.numeric_features_ = [
            c for c in self.feature_names_ if c not in self.categorical_features_
        ]

        return df

    def get_metadata(self) -> Dict[str, Any]:
        """Return feature pipeline metadata for model provenance."""
        return {
            "pipeline_version": self.version,
            "target_col": self.config.target_col,
            "freq_minutes": self.config.freq_minutes,
            "lag_minutes": self.config.lag_minutes,
            "rolling_windows": self.config.rolling_windows,
            "rolling_stats": self.config.rolling_stats,
            "total_features": len(self.feature_names_),
            "feature_names": self.feature_names_,
            "categorical_features": self.categorical_features_,
            "numeric_features": self.numeric_features_,
        }
