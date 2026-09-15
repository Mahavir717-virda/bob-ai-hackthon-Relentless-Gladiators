"""
GridPilot AI — Data Quality Reporting Module
============================================
Compiles and serializes machine-readable JSON data-quality reports
capturing counts, percentages, and audit metrics for all pipeline checks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Optional

from services.data.policies import MissingHandlingResult
from services.data.schema import SchemaValidationResult
from services.data.validator import (
    DuplicateValidationResult,
    MissingIntervalResult,
    RangeValidationResult,
    TimestampValidationResult,
)


@dataclass
class DataQualityReport:
    """Comprehensive machine-readable data quality report."""
    asset_id: str
    group_name: str
    source_uri: str
    execution_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    rows_in: int = 0
    rows_out: int = 0
    schema_validation: Optional[Dict[str, Any]] = None
    timestamp_validation: Optional[Dict[str, Any]] = None
    duplicate_validation: Optional[Dict[str, Any]] = None
    missing_intervals: Optional[Dict[str, Any]] = None
    missing_demand_handling: Optional[Dict[str, Any]] = None
    range_validation: Optional[Dict[str, Any]] = None
    canonical_output_path: Optional[str] = None
    status: str = "COMPLETED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": {
                "asset_id": self.asset_id,
                "group_name": self.group_name,
                "source_uri": self.source_uri,
                "execution_timestamp": self.execution_timestamp,
                "status": self.status,
                "canonical_output_path": self.canonical_output_path,
            },
            "summary": {
                "rows_in": self.rows_in,
                "rows_out": self.rows_out,
                "data_retention_pct": round(
                    (self.rows_out / self.rows_in * 100.0) if self.rows_in > 0 else 0.0,
                    4,
                ),
            },
            "checks": {
                "schema_validation": self.schema_validation,
                "timestamp_validation": self.timestamp_validation,
                "duplicate_validation": self.duplicate_validation,
                "missing_intervals": self.missing_intervals,
                "missing_demand_handling": self.missing_demand_handling,
                "range_validation": self.range_validation,
            },
        }

    def save_json(self, output_path: Path | str) -> Path:
        """Serialize report to a machine-readable JSON file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        return path
