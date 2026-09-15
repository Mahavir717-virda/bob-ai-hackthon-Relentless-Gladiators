"""
GridPilot AI — Demand Data Ingestion Pipeline
=============================================
Production ingestion pipeline orchestrating:
  1. Data Loading (Parquet / CSV / DataFrame)
  2. Schema Validation against confirmed OpenSTEF fields
  3. Timestamp Normalization (UTC) & Sorting
  4. Duplicate Timestamp Detection & Deduplication
  5. Missing Interval (15-min Grid Gap) Detection
  6. Explicit Missing Demand Value Handling (audited policy)
  7. Physical Numeric Range Validation & Flagging
  8. Canonical Dataset Export & Data Quality JSON Artifact Generation
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, Union
import pandas as pd

from services.data.config import IngestionConfig, MissingValuePolicy
from services.data.policies import handle_missing_demand
from services.data.quality_reporter import DataQualityReport
from services.data.schema import validate_schema
from services.data.validator import (
    detect_and_handle_duplicates,
    detect_missing_intervals,
    normalize_and_sort_timestamps,
    validate_numeric_ranges,
)


class DemandIngestionPipeline:
    """
    Production-grade demand data ingestion and cleansing pipeline.
    """

    def __init__(self, config: Optional[IngestionConfig] = None) -> None:
        self.config = config or IngestionConfig()

    def load_raw_data(self, source: Union[str, Path, pd.DataFrame]) -> Tuple[pd.DataFrame, str]:
        """Load raw data from Parquet, CSV, or DataFrame."""
        if isinstance(source, pd.DataFrame):
            return source.copy(), "dataframe_in_memory"

        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        suffix = source_path.suffix.lower()
        if suffix in [".parquet", ".pq"]:
            df = pd.read_parquet(source_path)
        elif suffix in [".csv"]:
            df = pd.read_csv(source_path, low_memory=False)
        else:
            raise ValueError(f"Unsupported file format '{suffix}'. Expected .parquet or .csv")

        return df, str(source_path)

    def process(
        self,
        source: Union[str, Path, pd.DataFrame],
        output_canonical_path: Optional[Union[str, Path]] = None,
        output_report_path: Optional[Union[str, Path]] = None,
    ) -> Tuple[pd.DataFrame, DataQualityReport]:
        """
        Execute full end-to-end ingestion and data-quality assessment.

        Parameters
        ----------
        source : str | Path | pd.DataFrame
            Input data source path or DataFrame.
        output_canonical_path : str | Path, optional
            Path where the cleaned canonical Parquet file will be stored.
        output_report_path : str | Path, optional
            Path where the machine-readable JSON report will be stored.

        Returns
        -------
        Tuple[pd.DataFrame, DataQualityReport]
            The canonical cleaned dataset and the quality report.
        """
        # Step 1: Load raw data
        raw_df, source_uri = self.load_raw_data(source)
        rows_in = len(raw_df)

        asset_name = self.config.asset_id or Path(source_uri).stem
        group_name = self.config.group_name.value

        # Step 2: Schema validation
        schema_result = validate_schema(raw_df, self.config)
        if not schema_result.is_valid:
            report = DataQualityReport(
                asset_id=asset_name,
                group_name=group_name,
                source_uri=source_uri,
                rows_in=rows_in,
                rows_out=0,
                schema_validation=schema_result.to_dict(),
                status="FAILED_SCHEMA_VALIDATION",
            )
            if output_report_path:
                report.save_json(output_report_path)
            raise ValueError(
                f"Schema validation failed for '{asset_name}': {schema_result.errors}"
            )

        # Step 3: Timestamp normalization and sorting
        ts_df, ts_result = normalize_and_sort_timestamps(raw_df, self.config)

        # Step 4: Duplicate detection and handling
        dedup_df, dupe_result = detect_and_handle_duplicates(ts_df, self.config, keep="first")

        # Step 5: Missing interval (sampling gap) detection against 15-min uniform grid
        gap_result = detect_missing_intervals(dedup_df, self.config)

        # Step 6: Explicit missing demand value handling
        handled_df, missing_result = handle_missing_demand(dedup_df, self.config)

        # Step 7: Physical numeric range validation and flagging
        validated_df, range_result = validate_numeric_ranges(handled_df, self.config)

        # Step 8: Assemble canonical dataset with standardized units
        canonical_df = validated_df.copy()

        # Add asset metadata
        canonical_df["asset_id"] = asset_name
        canonical_df["group_name"] = group_name

        # Ensure active power is expressed in both native Watts and standard MW/kW
        load_col = self.config.demand_col
        if not self.config.is_normalized_renewable:
            canonical_df["demand_mw"] = canonical_df[load_col] / 1e6
            canonical_df["demand_kw"] = canonical_df[load_col] / 1e3
        else:
            canonical_df["demand_mw"] = canonical_df[load_col]  # Normalized ratio for renewables
            canonical_df["demand_kw"] = canonical_df[load_col]

        # Order canonical columns
        canonical_order = [
            self.config.timestamp_col,
            "asset_id",
            "group_name",
            self.config.demand_col,
            "demand_mw",
            "demand_kw",
        ]
        if self.config.available_at_col in canonical_df.columns:
            canonical_order.append(self.config.available_at_col)

        audit_cols = ["is_imputed", "is_out_of_range", "is_reverse_flow"]
        for col in audit_cols:
            if col in canonical_df.columns:
                canonical_order.append(col)

        # Remaining columns (if any)
        remaining = [c for c in canonical_df.columns if c not in canonical_order]
        canonical_df = canonical_df[canonical_order + remaining]

        rows_out = len(canonical_df)

        # Build quality report
        report = DataQualityReport(
            asset_id=asset_name,
            group_name=group_name,
            source_uri=source_uri,
            rows_in=rows_in,
            rows_out=rows_out,
            schema_validation=schema_result.to_dict(),
            timestamp_validation=ts_result.to_dict(),
            duplicate_validation=dupe_result.to_dict(),
            missing_intervals=gap_result.to_dict(),
            missing_demand_handling=missing_result.to_dict(),
            range_validation=range_result.to_dict(),
            canonical_output_path=str(output_canonical_path) if output_canonical_path else None,
            status="SUCCESS",
        )

        # Step 9: Export artifacts
        if output_canonical_path:
            out_p = Path(output_canonical_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            canonical_df.to_parquet(out_p, index=False)

        if output_report_path:
            report.save_json(output_report_path)

        return canonical_df, report
