"""
Relationship detector — identifies high-level patterns between columns.
Used to guide chart scoring bonuses.
"""
from __future__ import annotations

from typing import List

from models.dataset import DatasetProfile


def detect_relationships(profile: DatasetProfile) -> List[str]:
    """
    Return a list of human-readable relationship labels detected in the dataset.
    These feed into the scoring engine.
    """
    rels: List[str] = []

    has_dt = profile.has_datetime
    has_num = profile.has_numeric
    has_cat = profile.has_categorical
    has_geo = profile.has_geo_latlon
    has_geo_named = profile.has_geo_named
    has_flow = profile.has_flow
    has_hier = profile.has_hierarchy
    has_ohlc = profile.has_ohlc
    n_num = len(profile.numeric_cols)
    n_cat = len(profile.categorical_cols)
    n_rows = profile.rows

    # Time series
    if has_dt and has_num:
        rels.append("time_series")

    # Category + metric
    if has_cat and has_num and n_cat >= 1 and n_num >= 1:
        rels.append("category_metric")

    # Two numeric → scatter/correlation
    if n_num >= 2 and not has_dt:
        rels.append("two_numeric")

    # Three+ numeric → 3D / bubble / scatter matrix
    if n_num >= 3:
        rels.append("three_or_more_numeric")

    # Two cat + numeric → heatmap / stacked bar
    if n_cat >= 2 and has_num:
        rels.append("multi_category_metric")

    # Hierarchy
    if has_hier and has_cat:
        rels.append("hierarchical")

    # Flow / network
    if has_flow:
        rels.append("flow_network")

    # Geographic lat/lon
    if has_geo:
        rels.append("geo_latlon")

    # Geographic named regions
    if has_geo_named and has_num:
        rels.append("geo_named_metric")

    # OHLC
    if has_ohlc:
        rels.append("ohlc")

    # Single numeric (KPI/Gauge candidates)
    if n_num == 1 and n_cat == 0 and not has_dt:
        rels.append("single_metric")

    # Large dataset
    if profile.row_count_class in ("large", "xlarge"):
        rels.append("large_dataset")

    # Funnel: categorical with monotone-decreasing values (approximate)
    if has_cat and has_num and n_cat == 1 and n_num == 1 and 3 <= n_rows <= 20:
        rels.append("funnel_candidate")

    # Category + time + metric → theme river / bump
    if has_dt and has_cat and has_num:
        rels.append("time_category_metric")

    return rels
