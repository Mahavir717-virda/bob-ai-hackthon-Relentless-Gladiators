"""
GridPilot AI — LightGBM Demand Forecasting Configuration
=========================================================
Holds configurable, documented hyperparameters and training specifications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class LightGBMTrainingConfig:
    """Configurable hyperparameters and provenance metadata for LightGBM models."""
    model_version: str = "demand-lgbm-v1"
    feature_version: str = "1.0.0"
    target_col: str = "demand_mw"
    timestamp_col: str = "timestamp"
    freq_minutes: int = 15
    horizons_minutes: List[int] = field(default_factory=lambda: [15, 30, 60])

    # Chronological split proportions (identical to Chunk 4)
    train_ratio: float = 0.70
    val_ratio: float = 0.15

    # Reproducible LightGBM hyperparameters
    lgbm_params: Dict[str, Any] = field(
        default_factory=lambda: {
            "objective": "regression",
            "metric": "mae",
            "learning_rate": 0.05,
            "num_leaves": 31,
            "min_data_in_leaf": 20,
            "feature_fraction": 0.9,
            "bagging_fraction": 0.9,
            "bagging_freq": 5,
            "seed": 42,
            "verbose": -1,
        }
    )

    num_boost_round: int = 500
    early_stopping_rounds: int = 30
    output_dir: Path | str = "./ml/models/demand"

    def get_periods_for_horizon(self, horizon_min: int) -> int:
        """Convert minutes to discrete time intervals."""
        return int(horizon_min / self.freq_minutes)
