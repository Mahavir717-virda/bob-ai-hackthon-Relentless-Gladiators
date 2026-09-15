"""
GridPilot AI — Demand Spike Labeling Engine
============================================
Derives and persists reproducible data-driven spike labeling rules from
historical training demand-growth distributions.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import numpy as np
import pandas as pd

from ml.models.demand.spike_config import SpikeClassifierConfig


def derive_labeling_rule(
    train_df: pd.DataFrame,
    config: Optional[SpikeClassifierConfig] = None,
    output_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Derives reproducible labeling cut-points strictly from historical training distribution.

    Parameters
    ----------
    train_df : pd.DataFrame
        Chronological training split containing 'demand_mw' and 'timestamp'.
    config : SpikeClassifierConfig, optional
        Configuration holding percentiles and parameters.
    output_path : Path | str, optional
        Path to save the versioned JSON artifact. Defaults to ml/models/demand/spike_labeling_rule_v1.json.

    Returns
    -------
    Dict[str, Any]
        Labeling rule metadata dictionary.
    """
    cfg = config or SpikeClassifierConfig()
    df = train_df.sort_values("timestamp").reset_index(drop=True)

    lead_steps = max(1, int(cfg.lead_minutes / 15))
    target_future = df["demand_mw"].shift(-lead_steps)
    current_demand = df["demand_mw"]
    denom = np.maximum(current_demand, cfg.denominator_stabilizer_mw)

    # Growth percentage formula: (y_{t+h} - y_t) / max(y_t, eps) * 100
    growth_pct = ((target_future - current_demand) / denom) * 100.0
    valid_growth = growth_pct.dropna()

    p_moderate_val = float(valid_growth.quantile(cfg.moderate_percentile))
    p_severe_val = float(valid_growth.quantile(cfg.severe_percentile))

    # Also record absolute MW change percentiles for physical context
    mw_diff = (target_future - current_demand).dropna()
    p_moderate_mw = float(mw_diff.quantile(cfg.moderate_percentile))
    p_severe_mw = float(mw_diff.quantile(cfg.severe_percentile))

    # Calculate class counts on training set
    n_total = len(valid_growth)
    n_class_0 = int((valid_growth < p_moderate_val).sum())
    n_class_1 = int(((valid_growth >= p_moderate_val) & (valid_growth < p_severe_val)).sum())
    n_class_2 = int((valid_growth >= p_severe_val).sum())

    rule_metadata = {
        "rule_version": "spike-rule-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_version": cfg.model_version,
        "derivation_split": "chronological_train_split_70pct",
        "sample_size": n_total,
        "lead_minutes": cfg.lead_minutes,
        "denominator_stabilizer_mw": cfg.denominator_stabilizer_mw,
        "growth_metric_formula": "((demand_{t+15m} - demand_t) / max(demand_t, 0.10 MW)) * 100",
        "percentile_cutpoints": {
            "moderate_percentile": cfg.moderate_percentile,
            "severe_percentile": cfg.severe_percentile,
        },
        "thresholds": {
            "moderate_spike_growth_pct_min": round(p_moderate_val, 4),
            "severe_spike_growth_pct_min": round(p_severe_val, 4),
            "moderate_spike_mw_delta_min": round(p_moderate_mw, 4),
            "severe_spike_mw_delta_min": round(p_severe_mw, 4),
        },
        "class_definitions": {
            0: {
                "name": "normal",
                "condition": f"growth_pct < {round(p_moderate_val, 2)}%",
                "train_samples": n_class_0,
                "train_prevalence_pct": round((n_class_0 / n_total) * 100.0, 2),
            },
            1: {
                "name": "moderate",
                "condition": f"{round(p_moderate_val, 2)}% <= growth_pct < {round(p_severe_val, 2)}%",
                "train_samples": n_class_1,
                "train_prevalence_pct": round((n_class_1 / n_total) * 100.0, 2),
            },
            2: {
                "name": "severe",
                "condition": f"growth_pct >= {round(p_severe_val, 2)}%",
                "train_samples": n_class_2,
                "train_prevalence_pct": round((n_class_2 / n_total) * 100.0, 2),
            },
        },
    }

    if output_path is None:
        output_path = Path("./ml/models/demand/spike_labeling_rule_v1.json")
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rule_metadata, f, indent=2)

    return rule_metadata


def assign_spike_labels(
    df: pd.DataFrame,
    labeling_rule: Dict[str, Any],
    demand_col: str = "demand_mw",
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Assigns classes 0, 1, 2 to dataframe based on the documented labeling rule.

    Returns
    -------
    Tuple[np.ndarray, np.ndarray]
        (labels array of int [0, 1, 2], growth_pct array of float)
    """
    lead_min = labeling_rule.get("lead_minutes", 15)
    lead_steps = max(1, int(lead_min / 15))
    eps = labeling_rule.get("denominator_stabilizer_mw", 0.10)
    p_moderate = labeling_rule["thresholds"]["moderate_spike_growth_pct_min"]
    p_severe = labeling_rule["thresholds"]["severe_spike_growth_pct_min"]

    current_demand = df[demand_col].to_numpy(dtype=float)
    target_future = pd.Series(current_demand).shift(-lead_steps).to_numpy(dtype=float)
    denom = np.maximum(current_demand, eps)

    growth_pct = ((target_future - current_demand) / denom) * 100.0

    labels = np.zeros(len(df), dtype=int)
    moderate_mask = (growth_pct >= p_moderate) & (growth_pct < p_severe)
    severe_mask = growth_pct >= p_severe

    labels[moderate_mask] = 1
    labels[severe_mask] = 2

    return labels, growth_pct
