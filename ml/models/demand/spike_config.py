"""
GridPilot AI — Demand Spike Classifier Configuration
=====================================================
Configuration schema for the 3-class XGBoost spike detection model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class SpikeClassifierConfig:
    """Hyperparameters and metadata for XGBoost spike detection."""

    model_version: str = "demand-spike-xgb-v1"
    feature_version: str = "1.0.0"
    random_seed: int = 42

    # Labeling rule percentiles derived from historical training data
    lead_minutes: int = 15  # Predict spike occurring in next 15-min step
    denominator_stabilizer_mw: float = 0.10  # Avoid division by zero during solar feed-in
    moderate_percentile: float = 0.95  # 95th percentile of load growth
    severe_percentile: float = 0.99   # 99th percentile of load growth

    # XGBoost Hyperparameters
    max_depth: int = 5
    learning_rate: float = 0.05
    n_estimators: int = 300
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_weight: float = 3.0
    objective: str = "multi:softprob"
    num_class: int = 3
    eval_metric: str = "mlogloss"
    early_stopping_rounds: int = 25

    # Feature column definitions
    feature_names: List[str] = field(
        default_factory=lambda: [
            "current_load",
            "forecast_load",
            "load_growth_pct",
            "historical_peak_24h",
            "temp_c",
            "humidity",
            "cloud_cover",
            "wind_speed",
            "solar_radiation",
            "hour",
            "hour_sin",
            "hour_cos",
            "day_of_week",
            "is_weekend",
        ]
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
