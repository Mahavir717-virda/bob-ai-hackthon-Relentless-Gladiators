"""
GridPilot AI — Schema Validation Module
=======================================
Validates incoming datasets against the confirmed OpenSTEF Liander 2024
schema documented in docs/data/openstef-demand.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import pandas as pd

from services.data.config import IngestionConfig


@dataclass
class SchemaValidationResult:
    """Outcome of schema validation."""
    is_valid: bool
    missing_required_columns: List[str] = field(default_factory=list)
    present_columns: List[str] = field(default_factory=list)
    detected_dtypes: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "missing_required_columns": self.missing_required_columns,
            "present_columns": self.present_columns,
            "detected_dtypes": self.detected_dtypes,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_schema(
    df: pd.DataFrame,
    config: Optional[IngestionConfig] = None,
) -> SchemaValidationResult:
    """
    Validate DataFrame schema against confirmed OpenSTEF demand specification.

    Parameters
    ----------
    df : pd.DataFrame
        Incoming raw DataFrame.
    config : IngestionConfig, optional
        Pipeline configuration specifying expected columns.

    Returns
    -------
    SchemaValidationResult
        Detailed report of column existence and data types.
    """
    if config is None:
        config = IngestionConfig()

    present_cols = [str(c) for c in df.columns]
    detected_dtypes = {str(c): str(df[c].dtype) for c in df.columns}
    missing_required: List[str] = []
    errors: List[str] = []
    warnings: List[str] = []

    # Check required demand column ('load')
    if config.demand_col not in df.columns:
        missing_required.append(config.demand_col)
        errors.append(f"Missing required demand column '{config.demand_col}'.")
    else:
        # Check that demand is numeric
        if not pd.api.types.is_numeric_dtype(df[config.demand_col]):
            # Try to see if it can be coerced
            non_numeric = pd.to_numeric(df[config.demand_col], errors="coerce").isna().sum()
            if non_numeric > 0:
                errors.append(
                    f"Column '{config.demand_col}' must be numeric; contains non-numeric values."
                )

    # Check timestamp column
    # Timestamp may be in columns or in DatetimeIndex
    has_timestamp_col = config.timestamp_col in df.columns
    is_datetime_index = isinstance(df.index, pd.DatetimeIndex)

    if not has_timestamp_col and not is_datetime_index:
        missing_required.append(config.timestamp_col)
        errors.append(
            f"Missing required timestamp column '{config.timestamp_col}' and index is not DatetimeIndex."
        )

    # Check available_at column (optional in some minimal formats, confirmed in OpenSTEF)
    if config.available_at_col not in df.columns:
        warnings.append(
            f"Optional availability timestamp '{config.available_at_col}' not found. Telemetry availability assumed real-time."
        )

    is_valid = len(errors) == 0

    return SchemaValidationResult(
        is_valid=is_valid,
        missing_required_columns=missing_required,
        present_columns=present_cols,
        detected_dtypes=detected_dtypes,
        errors=errors,
        warnings=warnings,
    )
