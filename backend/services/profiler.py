"""
Data profiler — builds a complete DatasetProfile from a DataFrame.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from models.dataset import ColumnProfile, DatasetProfile
from services.type_detector import (
    detect_semantic_type,
    is_categorical_semantic,
    is_datetime_semantic,
    is_flow,
    is_geo_lat,
    is_geo_lon,
    is_identifier,
    is_numeric_semantic,
)

logger = logging.getLogger(__name__)


def _cardinality_class(n_unique: int, n_total: int) -> str:
    if n_total == 0:
        return "low"
    ratio = n_unique / n_total
    if n_unique == 1:
        return "constant"
    if ratio > 0.95 and n_unique > 50:
        return "unique"
    if ratio <= 0.05 or n_unique <= 10:
        return "low"
    if ratio <= 0.30 or n_unique <= 50:
        return "medium"
    return "high"


def _numeric_stats(series: pd.Series) -> Optional[Dict[str, Any]]:
    try:
        s = pd.to_numeric(series.dropna(), errors="coerce").dropna()
        if len(s) == 0:
            return None
        return {
            "min": float(s.min()),
            "max": float(s.max()),
            "mean": float(s.mean()),
            "median": float(s.median()),
            "std": float(s.std()),
            "q25": float(s.quantile(0.25)),
            "q75": float(s.quantile(0.75)),
        }
    except Exception:
        return None


def _row_count_class(n: int) -> str:
    if n < 10:
        return "tiny"
    if n < 500:
        return "small"
    if n < 10_000:
        return "medium"
    if n < 100_000:
        return "large"
    return "xlarge"


def profile_dataset(df: pd.DataFrame, dataset_id: str, filename: str) -> DatasetProfile:
    """Build a full DatasetProfile for a DataFrame."""
    logger.info(f"Profiling dataset {dataset_id}: {len(df)} rows × {len(df.columns)} cols")

    total_rows = len(df)
    col_profiles: Dict[str, ColumnProfile] = {}

    numeric_cols: List[str] = []
    datetime_cols: List[str] = []
    categorical_cols: List[str] = []
    geo_lat_cols: List[str] = []
    geo_lon_cols: List[str] = []
    geo_named_cols: List[str] = []
    flow_source_cols: List[str] = []
    flow_target_cols: List[str] = []
    identifier_cols: List[str] = []

    for col in df.columns:
        series = df[col]
        n_missing = int(series.isna().sum())
        n_unique = int(series.nunique())
        missing_pct = round(n_missing / max(total_rows, 1) * 100, 2)
        cardinality = _cardinality_class(n_unique, total_rows)

        stype = detect_semantic_type(col, series, total_rows)

        # Build sample values (safe, no sensitive data logging)
        raw_sample = series.dropna().head(5).tolist()
        sample_values = []
        for v in raw_sample:
            try:
                if isinstance(v, (np.integer,)):
                    sample_values.append(int(v))
                elif isinstance(v, (np.floating,)):
                    sample_values.append(float(v))
                else:
                    sample_values.append(str(v))
            except Exception:
                sample_values.append(str(v))

        stats = _numeric_stats(series) if is_numeric_semantic(stype) else None

        cp = ColumnProfile(
            name=col,
            dtype_raw=str(series.dtype),
            semantic_type=stype,
            unique_count=n_unique,
            missing_count=n_missing,
            missing_pct=missing_pct,
            total_count=total_rows,
            cardinality=cardinality,
            sample_values=sample_values,
            is_constant=(n_unique <= 1),
            stats=stats,
        )
        col_profiles[col] = cp

        # Classify into buckets
        if is_numeric_semantic(stype):
            numeric_cols.append(col)
        if is_datetime_semantic(stype):
            datetime_cols.append(col)
        if is_categorical_semantic(stype):
            categorical_cols.append(col)
        if is_geo_lat(stype):
            geo_lat_cols.append(col)
        if is_geo_lon(stype):
            geo_lon_cols.append(col)
        if stype == "geo_named":
            geo_named_cols.append(col)
        if stype == "flow_source":
            flow_source_cols.append(col)
        if stype == "flow_target":
            flow_target_cols.append(col)
        if is_identifier(stype):
            identifier_cols.append(col)

    # Duplicate row count
    try:
        duplicate_rows = int(df.duplicated().sum())
    except Exception:
        duplicate_rows = 0

    profile = DatasetProfile(
        dataset_id=dataset_id,
        filename=filename,
        rows=total_rows,
        columns=len(df.columns),
        duplicate_rows=duplicate_rows,
        column_profiles=col_profiles,
        has_datetime=len(datetime_cols) > 0,
        has_numeric=len(numeric_cols) > 0,
        has_categorical=len(categorical_cols) > 0,
        has_geo_latlon=(len(geo_lat_cols) > 0 and len(geo_lon_cols) > 0),
        has_geo_named=len(geo_named_cols) > 0,
        has_flow=(len(flow_source_cols) > 0 and len(flow_target_cols) > 0),
        has_hierarchy=_detect_hierarchy(df, categorical_cols, col_profiles),
        has_ohlc=_detect_ohlc(df.columns.tolist()),
        numeric_cols=numeric_cols,
        datetime_cols=datetime_cols,
        categorical_cols=categorical_cols,
        geo_lat_cols=geo_lat_cols,
        geo_lon_cols=geo_lon_cols,
        geo_named_cols=geo_named_cols,
        flow_source_cols=flow_source_cols,
        flow_target_cols=flow_target_cols,
        identifier_cols=identifier_cols,
        row_count_class=_row_count_class(total_rows),
    )

    logger.info(
        f"Profile complete: numeric={numeric_cols} datetime={datetime_cols} "
        f"categorical={categorical_cols} geo_latlon={profile.has_geo_latlon} "
        f"flow={profile.has_flow} hierarchy={profile.has_hierarchy} ohlc={profile.has_ohlc}"
    )
    return profile


def _detect_hierarchy(
    df: pd.DataFrame,
    categorical_cols: List[str],
    profiles: Dict[str, ColumnProfile],
) -> bool:
    """
    Detect a potential hierarchy: column A's unique values are a superset
    of column B's unique values per group, AND col B is more granular.
    Simple heuristic: ≥2 categorical columns where cardinality increases.
    """
    if len(categorical_cols) < 2:
        return False
    cards = sorted(categorical_cols, key=lambda c: profiles[c].unique_count)
    # If there are at least 2 categoricals and the finest has > 2x uniqueness of coarsest
    if profiles[cards[-1]].unique_count > profiles[cards[0]].unique_count * 1.5:
        return True
    return False


def _detect_ohlc(columns: List[str]) -> bool:
    """Check if dataset has open/high/low/close pattern."""
    col_lower = {c.lower() for c in columns}
    ohlc_required = {"open", "high", "low", "close"}
    # Fuzzy check
    hits = sum(1 for tok in ohlc_required if any(tok in c.lower() for c in columns))
    return hits >= 4
