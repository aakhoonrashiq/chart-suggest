"""Pydantic models for dataset and column profiling."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ColumnProfile(BaseModel):
    name: str
    dtype_raw: str                   # pandas dtype string
    semantic_type: str               # our classified type
    unique_count: int
    missing_count: int
    missing_pct: float
    total_count: int
    cardinality: str                 # "low" | "medium" | "high" | "unique"
    sample_values: List[Any]
    is_constant: bool
    stats: Optional[Dict[str, Any]] = None  # numeric stats if applicable


class DatasetProfile(BaseModel):
    dataset_id: str
    filename: str
    rows: int
    columns: int
    duplicate_rows: int
    column_profiles: Dict[str, ColumnProfile]

    # Derived signals
    has_datetime: bool
    has_numeric: bool
    has_categorical: bool
    has_geo_latlon: bool
    has_geo_named: bool
    has_flow: bool
    has_hierarchy: bool
    has_ohlc: bool

    numeric_cols: List[str]
    datetime_cols: List[str]
    categorical_cols: List[str]
    geo_lat_cols: List[str]
    geo_lon_cols: List[str]
    geo_named_cols: List[str]
    flow_source_cols: List[str]
    flow_target_cols: List[str]
    identifier_cols: List[str]

    row_count_class: str             # "tiny" | "small" | "medium" | "large" | "xlarge"
