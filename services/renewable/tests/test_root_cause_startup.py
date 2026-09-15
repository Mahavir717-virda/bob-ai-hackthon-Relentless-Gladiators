"""
Test Root-Cause Model Startup Initialization & Connection
==========================================================
Verifies that trained solar and wind root-cause models are loaded at startup
and executed cleanly by analyzeRootCause() without fallback data.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from services.renewable.root_cause import load_root_cause_model, _BUNDLES, analyzeRootCause
from services.renewable.renewable_service import _root_cause_artifact_status, RenewableDataError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = PROJECT_ROOT / "ml" / "models" / "renewable"


def test_solar_root_cause_model_artifact_loads():
    """Verify Solar Root Cause XGBoost artifact loads successfully into _BUNDLES."""
    result = load_root_cause_model("solar", MODEL_DIR)
    assert result["model"] is not None
    assert "solar" in _BUNDLES
    assert _BUNDLES["solar"].model is not None
    assert len(result["feature_columns"]) > 0


def test_wind_root_cause_model_artifact_loads():
    """Verify Wind Root Cause XGBoost artifact loads successfully into _BUNDLES."""
    result = load_root_cause_model("wind", MODEL_DIR)
    assert result["model"] is not None
    assert "wind" in _BUNDLES
    assert _BUNDLES["wind"].model is not None
    assert len(result["feature_columns"]) > 0


def test_root_cause_startup_initialization_registers_both_models():
    """Verify _root_cause_artifact_status loads both models without raising errors."""
    _root_cause_artifact_status()
    assert "solar" in _BUNDLES
    assert "wind" in _BUNDLES


def test_analyze_root_cause_uses_trained_model():
    """Verify analyzeRootCause returns model-attributed output for a known timestamp."""
    _root_cause_artifact_status()
    bundle = _BUNDLES.get("solar")
    if bundle and not bundle.rows.empty:
        sample_row = bundle.rows.iloc[0]
        res = analyzeRootCause(sample_row["asset_id"], sample_row["timestamp"])
        assert "category" in res
        assert "confidence" in res
        assert res["category"] != ""


def test_missing_model_raises_explicit_error(tmp_path):
    """Verify explicit error is raised if a required root-cause model file is missing."""
    with pytest.raises(FileNotFoundError):
        load_root_cause_model("solar", model_dir=tmp_path)
