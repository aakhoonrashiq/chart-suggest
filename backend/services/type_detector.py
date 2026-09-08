"""
Semantic type detector — classifies each DataFrame column into a
meaningful semantic type beyond raw pandas dtype.

Semantic types:
  identifier, boolean, datetime, integer, float, percentage,
  currency, latitude, longitude, geo_named, categorical, text,
  flow_source, flow_target, numeric (fallback numeric)
"""
from __future__ import annotations

import re
import logging
from typing import Any, List

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column name patterns
# ---------------------------------------------------------------------------
_LAT_PATTERNS = re.compile(
    r"\b(lat|latitude|lat_|_lat)\b", re.IGNORECASE
)
_LON_PATTERNS = re.compile(
    r"\b(lon|lng|long|longitude|lon_|_lon)\b", re.IGNORECASE
)
_DATE_PATTERNS = re.compile(
    r"\b(date|time|datetime|timestamp|created|updated|year|month|day|"
    r"week|period|quarter|qtr|dt)\b", re.IGNORECASE
)
_ID_PATTERNS = re.compile(
    r"\b(id|_id|uuid|guid|key|code|ref|no|num|number|order_id|"
    r"customer_id|user_id|product_id|sku|serial|index)\b", re.IGNORECASE
)
_BOOL_PATTERNS = re.compile(
    r"\b(is_|has_|flag|active|enabled|disabled|valid|approved|"
    r"deleted|verified)\b", re.IGNORECASE
)
_GEO_NAMED_PATTERNS = re.compile(
    r"\b(country|nation|state|province|region|district|city|town|"
    r"territory|continent|county|prefecture|municipality|area|zone|"
    r"iso_code|iso2|iso3|location|place)\b", re.IGNORECASE
)
_SOURCE_PATTERNS = re.compile(
    r"\b(source|from|origin|src|start|sender|parent)\b", re.IGNORECASE
)
_TARGET_PATTERNS = re.compile(
    r"\b(target|to|dest|destination|dst|end|receiver|child)\b", re.IGNORECASE
)
_PCT_PATTERNS = re.compile(
    r"\b(pct|percent|percentage|rate|ratio|share|proportion)\b", re.IGNORECASE
)
_CURRENCY_PATTERNS = re.compile(
    r"\b(price|cost|revenue|sales|profit|loss|salary|wage|amount|"
    r"spend|budget|income|earning|fee|charge|payment|gross|net)\b", re.IGNORECASE
)

# Common boolean value sets
_BOOL_VALUES = {
    frozenset({"true", "false"}),
    frozenset({"yes", "no"}),
    frozenset({"1", "0"}),
    frozenset({1, 0}),
    frozenset({True, False}),
    frozenset({"y", "n"}),
}


def _sample_values(series: pd.Series, n: int = 100) -> List[Any]:
    """Return up to n non-null sample values from a series."""
    non_null = series.dropna()
    if len(non_null) <= n:
        return non_null.tolist()
    return non_null.sample(n=n, random_state=42).tolist()


def _is_datetime_parseable(series: pd.Series) -> bool:
    """Check if an object column can be parsed as datetime."""
    sample = series.dropna().head(30)
    if len(sample) == 0:
        return False
    try:
        parsed = pd.to_datetime(sample, errors="coerce")
        success_rate = parsed.notna().sum() / len(sample)
        return success_rate >= 0.7
    except Exception:
        return False


def _is_latitude(series: pd.Series) -> bool:
    """Check if a numeric column contains latitude values (-90 to 90)."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    try:
        vals = pd.to_numeric(non_null, errors="coerce").dropna()
        if len(vals) < len(non_null) * 0.8:
            return False
        return float(vals.min()) >= -91 and float(vals.max()) <= 91
    except Exception:
        return False


def _is_longitude(series: pd.Series) -> bool:
    """Check if a numeric column contains longitude values (-180 to 180)."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    try:
        vals = pd.to_numeric(non_null, errors="coerce").dropna()
        if len(vals) < len(non_null) * 0.8:
            return False
        return float(vals.min()) >= -181 and float(vals.max()) <= 181
    except Exception:
        return False


def detect_semantic_type(
    col_name: str,
    series: pd.Series,
    total_rows: int,
) -> str:
    """
    Classify a column into a semantic type using:
    1. pandas dtype
    2. column name patterns
    3. value sampling + statistics
    """
    name = col_name.strip()
    dtype = series.dtype
    non_null = series.dropna()
    n_unique = series.nunique()
    n_total = total_rows
    unique_ratio = n_unique / max(n_total, 1)

    # ── Boolean ──────────────────────────────────────────────────────────────
    if dtype == bool or str(dtype) == "bool":
        return "boolean"

    if _BOOL_PATTERNS.search(name):
        uniq_vals = set(str(v).lower() for v in non_null.unique())
        for bset in _BOOL_VALUES:
            if uniq_vals <= {str(v).lower() for v in bset}:
                return "boolean"

    if n_unique <= 2 and len(non_null) > 0:
        uniq_vals = set(str(v).lower() for v in non_null.unique())
        for bset in _BOOL_VALUES:
            if uniq_vals <= {str(v).lower() for v in bset}:
                return "boolean"

    # ── Datetime ──────────────────────────────────────────────────────────────
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "datetime"

    if _DATE_PATTERNS.search(name):
        if dtype == object or str(dtype).startswith("str"):
            if _is_datetime_parseable(series):
                return "datetime"
        if pd.api.types.is_integer_dtype(dtype):
            # e.g. year column like 2020, 2021
            sample_vals = non_null.dropna()
            if len(sample_vals) > 0:
                mn, mx = int(sample_vals.min()), int(sample_vals.max())
                if 1900 <= mn and mx <= 2100 and n_unique < 200:
                    return "datetime"

    if dtype == object and _is_datetime_parseable(series):
        return "datetime"

    # ── Latitude / Longitude (name-based + value-based) ───────────────────────
    if _LAT_PATTERNS.search(name):
        if pd.api.types.is_numeric_dtype(dtype) and _is_latitude(series):
            return "latitude"

    if _LON_PATTERNS.search(name):
        if pd.api.types.is_numeric_dtype(dtype) and _is_longitude(series):
            return "longitude"

    # Value-based lat/lon detection for unnamed columns
    if pd.api.types.is_numeric_dtype(dtype):
        if _is_latitude(series) and not _is_longitude(series):
            # Lat range is stricter: [-90,90] vs lon [-180,180]
            mn, mx = float(series.dropna().min()), float(series.dropna().max())
            if -90 <= mn and mx <= 90:
                if _LAT_PATTERNS.search(name) or "lat" in name.lower():
                    return "latitude"

    # ── Identifier ────────────────────────────────────────────────────────────
    if _ID_PATTERNS.search(name) and unique_ratio > 0.8:
        return "identifier"

    # High-cardinality numeric that looks like an ID
    if pd.api.types.is_integer_dtype(dtype) and unique_ratio > 0.95 and n_unique > 50:
        if _ID_PATTERNS.search(name):
            return "identifier"

    # ── Flow columns ──────────────────────────────────────────────────────────
    if _SOURCE_PATTERNS.search(name) and dtype == object:
        return "flow_source"
    if _TARGET_PATTERNS.search(name) and dtype == object:
        return "flow_target"

    # ── Geographic named ──────────────────────────────────────────────────────
    if _GEO_NAMED_PATTERNS.search(name) and dtype == object:
        return "geo_named"

    # ── Percentage ────────────────────────────────────────────────────────────
    if pd.api.types.is_numeric_dtype(dtype) and _PCT_PATTERNS.search(name):
        vals = non_null.dropna()
        if len(vals) > 0 and float(vals.min()) >= 0 and float(vals.max()) <= 100:
            return "percentage"

    # ── Currency / Revenue numeric ────────────────────────────────────────────
    if pd.api.types.is_numeric_dtype(dtype) and _CURRENCY_PATTERNS.search(name):
        return "currency"

    # ── Numeric ───────────────────────────────────────────────────────────────
    if pd.api.types.is_float_dtype(dtype):
        return "float"

    if pd.api.types.is_integer_dtype(dtype):
        # Check if it's a disguised boolean
        if n_unique <= 2:
            uniq = set(non_null.unique())
            if uniq <= {0, 1} or uniq <= {True, False}:
                return "boolean"
        return "integer"

    if pd.api.types.is_numeric_dtype(dtype):
        return "numeric"

    # ── Text / Categorical ────────────────────────────────────────────────────
    if dtype == object:
        # Try numeric coercion
        coerced = pd.to_numeric(non_null, errors="coerce")
        numeric_ratio = coerced.notna().sum() / max(len(non_null), 1)
        if numeric_ratio >= 0.8:
            # It's a numeric stored as string
            return "float" if coerced.dropna().dtype == float else "integer"

        # Low cardinality → categorical
        if n_unique <= 50 or unique_ratio <= 0.1:
            return "categorical"

        # High cardinality object → text or identifier
        if unique_ratio > 0.9:
            return "text"

        return "categorical"

    return "categorical"


def is_numeric_semantic(stype: str) -> bool:
    return stype in {"integer", "float", "numeric", "percentage", "currency"}


def is_categorical_semantic(stype: str) -> bool:
    return stype in {"categorical", "boolean", "geo_named"}


def is_datetime_semantic(stype: str) -> bool:
    return stype == "datetime"


def is_geo_lat(stype: str) -> bool:
    return stype == "latitude"


def is_geo_lon(stype: str) -> bool:
    return stype == "longitude"


def is_flow(stype: str) -> bool:
    return stype in {"flow_source", "flow_target"}


def is_identifier(stype: str) -> bool:
    return stype in {"identifier", "text"}
