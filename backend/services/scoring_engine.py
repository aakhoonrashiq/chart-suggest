"""
Scoring engine — assigns a 0-100 suitability score to each chart
given a dataset profile and detected relationships.

Scoring model (max 100 points):
  30 pts  — required semantic types present
  15 pts  — column count satisfies chart requirements
  20 pts  — semantic / structural signal match
  10 pts  — cardinality is appropriate for chart type
  10 pts  — row count / dataset size appropriate
  15 pts  — relationship bonus (time series, hierarchy, flow, etc.)

Hard eliminators → score = 0:
  - Required geo but no geo detected
  - Required flow but no flow detected
  - Required OHLC but no OHLC detected
  - Required 3+ numerics but <3 numeric columns
  - Column count < chart minimum
  - Missing mandatory semantic type(s)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from models.dataset import DatasetProfile

logger = logging.getLogger(__name__)


def _has_enough_of(needed: List[str], profile: DatasetProfile) -> Tuple[bool, int]:
    """
    Check whether the profile satisfies required_semantics counts.
    Returns (satisfied, points_0_to_30).
    For simplicity we count unique *categories* of semantics.
    """
    needed_groups: Dict[str, int] = {}
    for s in needed:
        needed_groups[s] = needed_groups.get(s, 0) + 1

    # Map semantic groups to profile lists
    available: Dict[str, int] = {
        "numeric": len(profile.numeric_cols),
        "integer": len(profile.numeric_cols),
        "float": len(profile.numeric_cols),
        "currency": len(profile.numeric_cols),
        "percentage": len(profile.numeric_cols),
        "categorical": len(profile.categorical_cols),
        "series": len(profile.categorical_cols),
        "datetime": len(profile.datetime_cols),
        "datetime_or_ordered": len(profile.datetime_cols) + len(profile.categorical_cols),
        "geo_lat": len(profile.geo_lat_cols),
        "geo_lon": len(profile.geo_lon_cols),
        "geo_named": len(profile.geo_named_cols),
        "flow_source": len(profile.flow_source_cols),
        "flow_target": len(profile.flow_target_cols),
    }

    total_required = len(needed_groups)
    satisfied = 0
    for grp, count_needed in needed_groups.items():
        avail = available.get(grp, 0)
        if avail >= count_needed:
            satisfied += 1

    if total_required == 0:
        return True, 30  # Table chart — accepts anything
    ratio = satisfied / total_required
    points = int(30 * ratio)
    return ratio >= 1.0, points


def score_chart(
    chart: Dict[str, Any],
    profile: DatasetProfile,
    relationships: List[str],
) -> Tuple[int, str, Dict[str, str]]:
    """
    Score a chart against a dataset profile.
    Returns (score, reason, column_mapping).
    """
    cid = chart["id"]
    min_cols = chart.get("min_cols", 1)
    max_cols = chart.get("max_cols")
    requires_geo = chart.get("requires_geo", False)
    requires_flow = chart.get("requires_flow", False)
    requires_hierarchy = chart.get("requires_hierarchy", False)
    requires_ohlc = chart.get("requires_ohlc", False)
    requires_3d = chart.get("requires_3d", False)
    webgl = chart.get("webgl", False)
    required_semantics = chart.get("required_semantics", [])
    max_cats_ideal = chart.get("max_categories_ideal")
    scoring_hints = chart.get("scoring_hints", {})
    min_rows_rec = chart.get("min_rows_recommended", 1)

    total_cols = profile.columns
    reasons = []
    warnings = []
    score = 0

    # ── HARD ELIMINATORS ─────────────────────────────────────────────────────
    if requires_geo and not profile.has_geo_latlon and not profile.has_geo_named:
        return 0, "Dataset has no geographic data.", {}

    if requires_flow and not profile.has_flow:
        return 0, "Dataset has no source/target flow columns.", {}

    if requires_ohlc and not profile.has_ohlc:
        return 0, "Dataset lacks open/high/low/close columns.", {}

    if requires_3d and len(profile.numeric_cols) < 3:
        return 0, "3D chart requires at least 3 numeric columns.", {}

    if requires_hierarchy and not profile.has_hierarchy:
        return 0, "Dataset shows no hierarchical structure.", {}

    if total_cols < min_cols:
        return 0, f"Chart needs ≥{min_cols} columns but dataset has only {total_cols}.", {}

    if max_cols is not None and total_cols > max_cols * 3:
        # Too many columns — not a hard block but reduce relevance below threshold
        pass

    # ── SEMANTIC TYPES (30 pts) ───────────────────────────────────────────────
    satisfied, type_points = _has_enough_of(required_semantics, profile)
    if not satisfied and len(required_semantics) > 0 and type_points < 10:
        return 0, "Missing required column types.", {}
    score += type_points
    if type_points >= 25:
        reasons.append("Required column types present.")
    elif type_points >= 15:
        reasons.append("Most required column types present.")

    # ── COLUMN COUNT (15 pts) ─────────────────────────────────────────────────
    if total_cols >= min_cols:
        if max_cols is None:
            col_pts = 15
        else:
            excess = max(0, total_cols - max_cols)
            col_pts = max(0, 15 - excess * 3)
        score += col_pts
        if col_pts >= 12:
            reasons.append("Column count is well-suited.")

    # ── RELATIONSHIP SIGNALS (15 pts) ─────────────────────────────────────────
    rel_pts = 0

    if "time_series_bonus" in scoring_hints and "time_series" in relationships:
        rel_pts += scoring_hints["time_series_bonus"]
        reasons.append("Datetime column + numeric → trend analysis.")

    if "category_metric_bonus" in scoring_hints and "category_metric" in relationships:
        rel_pts += scoring_hints["category_metric_bonus"]
        reasons.append("Categorical + numeric → comparison.")

    if "two_numeric_bonus" in scoring_hints and "two_numeric" in relationships:
        rel_pts += scoring_hints["two_numeric_bonus"]
        reasons.append("Two numeric columns → correlation/relationship.")

    if "three_numeric_bonus" in scoring_hints and "three_or_more_numeric" in relationships:
        rel_pts += scoring_hints["three_numeric_bonus"]
        reasons.append("Three+ numeric columns → 3D/multi-variable analysis.")

    if "many_numeric_bonus" in scoring_hints and len(profile.numeric_cols) >= 3:
        rel_pts += scoring_hints["many_numeric_bonus"]
        reasons.append("Multiple numeric dimensions detected.")

    if "multi_categorical_bonus" in scoring_hints and "multi_category_metric" in relationships:
        rel_pts += scoring_hints["multi_categorical_bonus"]
        reasons.append("Multiple categorical dimensions → composition view.")

    if "hierarchy_bonus" in scoring_hints and "hierarchical" in relationships:
        rel_pts += scoring_hints["hierarchy_bonus"]
        reasons.append("Hierarchical categorical structure detected.")

    if "flow_bonus" in scoring_hints and "flow_network" in relationships:
        rel_pts += scoring_hints["flow_bonus"]
        reasons.append("Source/target columns → flow/network relationship.")

    if "geo_latlon_bonus" in scoring_hints and "geo_latlon" in relationships:
        rel_pts += scoring_hints["geo_latlon_bonus"]
        reasons.append("Geographic latitude/longitude detected.")

    if "geo_named_bonus" in scoring_hints and "geo_named_metric" in relationships:
        rel_pts += scoring_hints["geo_named_bonus"]
        reasons.append("Geographic region names + metric detected.")

    if "ohlc_bonus" in scoring_hints and "ohlc" in relationships:
        rel_pts += scoring_hints["ohlc_bonus"]
        reasons.append("OHLC price data detected.")

    if "large_dataset_bonus" in scoring_hints and "large_dataset" in relationships:
        if profile.rows >= min_rows_rec:
            rel_pts += scoring_hints["large_dataset_bonus"]
            reasons.append(f"Large dataset ({profile.rows:,} rows) benefits from WebGL rendering.")
        else:
            rel_pts -= 10
            warnings.append("WebGL chart recommended for large datasets only.")

    if "single_numeric_bonus" in scoring_hints and "single_metric" in relationships:
        rel_pts += scoring_hints["single_numeric_bonus"]
        reasons.append("Single metric value detected.")

    if "funnel_bonus" in scoring_hints and "funnel_candidate" in relationships:
        rel_pts += scoring_hints["funnel_bonus"]
        reasons.append("Ordered stages with values detected.")

    if "time_category_metric" in relationships and cid in ("theme_river", "bump_chart", "bar_chart_race"):
        rel_pts += 15
        reasons.append("Time + category + metric → temporal stream/race.")

    if "ordered_category_bonus" in scoring_hints:
        # Check if categorical column looks ordered (e.g., Q1, Q2 / Jan, Feb)
        if profile.has_categorical:
            rel_pts += scoring_hints["ordered_category_bonus"] // 2  # half credit

    # Base score for table (always usable)
    if "base_score" in scoring_hints:
        rel_pts += scoring_hints["base_score"]
        reasons.append("Tabular data always viewable as a table.")

    score += min(rel_pts, 40)  # cap relationship bonus at 40

    # ── CARDINALITY (10 pts) ──────────────────────────────────────────────────
    card_pts = 0
    if max_cats_ideal is not None and profile.has_categorical:
        # Find the categorical col with highest cardinality
        cat_cards = [profile.column_profiles[c].unique_count for c in profile.categorical_cols if c in profile.column_profiles]
        if cat_cards:
            max_card = max(cat_cards)
            if max_card <= max_cats_ideal:
                card_pts = 10
            elif max_card <= max_cats_ideal * 2:
                card_pts = 5
            else:
                card_pts = 0
                if chart.get("scoring_hints", {}).get("pie_cardinality_penalty"):
                    penalty = min(40, (max_card - max_cats_ideal) * 3)
                    score = max(0, score - penalty)
                    warnings.append(
                        f"High cardinality ({max_card} categories) may make this chart unreadable."
                    )
    else:
        card_pts = 10  # no restriction → full points
    score += card_pts

    # ── ROW COUNT (10 pts) ────────────────────────────────────────────────────
    row_class = profile.row_count_class
    if webgl:
        if row_class in ("large", "xlarge"):
            score += 10
        elif row_class == "medium":
            score += 3
            warnings.append("This WebGL chart is most useful for very large datasets.")
        else:
            score -= 5
            warnings.append("WebGL charts are overkill for small datasets.")
    else:
        if row_class == "tiny":
            score += 5
        elif row_class in ("small", "medium"):
            score += 10
        elif row_class == "large":
            score += 8
        else:
            score += 5

    # ── 3D SANITY CHECK ───────────────────────────────────────────────────────
    if requires_3d and len(profile.numeric_cols) < 3:
        score = max(0, score - 20)
        warnings.append("3D chart requires 3 independent numeric dimensions.")

    # ── CLAMP ─────────────────────────────────────────────────────────────────
    score = min(100, max(0, score))

    reason_text = " ".join(reasons) if reasons else chart.get("description", "")
    mapping = _build_mapping(chart, profile)

    return score, reason_text, mapping


def _build_mapping(chart: Dict[str, Any], profile: DatasetProfile) -> Dict[str, str]:
    """Dynamically build column mapping for a chart based on profile."""
    mapping: Dict[str, str] = {}
    cid = chart["id"]
    mapping_keys = chart.get("mapping_keys", [])

    num = list(profile.numeric_cols)
    cat = list(profile.categorical_cols)
    dt = list(profile.datetime_cols)
    lat = list(profile.geo_lat_cols)
    lon = list(profile.geo_lon_cols)
    geo_named = list(profile.geo_named_cols)
    src = list(profile.flow_source_cols)
    tgt = list(profile.flow_target_cols)

    def pop(lst: List[str]) -> Optional[str]:
        return lst.pop(0) if lst else None

    # Special-case by chart id
    if cid in ("line", "area", "stepped_line", "smooth_line", "multi_x_axis_line", "stacked_line_chart", "stacked_area"):
        mapping["x"] = pop(dt) or pop(cat) or pop(num) or ""
        mapping["y"] = pop(num) or ""
        if num:
            mapping["y2"] = pop(num) or ""

    elif cid == "bar_with_line":
        mapping["x"] = pop(dt) or pop(cat) or ""
        mapping["bar_value"] = pop(num) or ""
        mapping["line_value"] = pop(num) or ""

    elif cid == "nightingale_rose":
        # Nightingale uses pie-style name/value mapping
        mapping["name"] = pop(cat) or ""
        mapping["value"] = pop(num) or ""

    elif cid in ("bar", "horizontal_bar", "circular_bar_chart", "waterfall_chart", "horizontal_waterfall_chart"):
        mapping["x"] = pop(cat) or pop(dt) or ""
        mapping["y"] = pop(num) or ""

    elif cid in ("polar_bar", "polar_end_angle_arc_bar", "pictorial_bar"):
        mapping["category"] = pop(cat) or pop(dt) or ""
        mapping["value"] = pop(num) or ""

    elif cid in ("stacked_bar_chart", "100_stacked_bar", "stacked_horizontal_bar", "100_stacked_horizontal_bar"):
        mapping["x"] = pop(cat) or pop(dt) or ""
        mapping["series"] = pop(cat) or ""
        mapping["y"] = pop(num) or ""

    elif cid == "bar_chart_race":
        mapping["time"] = pop(dt) or pop(cat) or ""
        mapping["category"] = pop(cat) or ""
        mapping["value"] = pop(num) or ""

    elif cid == "range_bar_chart":
        mapping["category"] = pop(cat) or ""
        mapping["low"] = pop(num) or ""
        mapping["high"] = pop(num) or ""

    elif cid in ("pie", "donut", "funnel"):
        mapping["name"] = pop(cat) or ""
        mapping["value"] = pop(num) or ""

    elif cid in ("scatter", "effect_scatter"):
        mapping["x"] = pop(num) or ""
        mapping["y"] = pop(num) or ""
        if cat:
            mapping["color"] = pop(cat) or ""

    elif cid == "bubble":
        mapping["x"] = pop(num) or ""
        mapping["y"] = pop(num) or ""
        mapping["size"] = pop(num) or ""
        if cat:
            mapping["color"] = pop(cat) or ""

    elif cid in ("3d_scatter_plot", "3d_surface_plot", "3d_line_chart"):
        mapping["x"] = pop(num) or ""
        mapping["y"] = pop(num) or ""
        mapping["z"] = pop(num) or ""

    elif cid == "3d_bar_chart":
        mapping["x"] = pop(cat) or pop(num) or ""
        mapping["y"] = pop(cat) or pop(num) or ""
        mapping["value"] = pop(num) or ""

    elif cid in ("heatmap", "polar_heatmap"):
        mapping["x"] = pop(cat) or pop(dt) or ""
        mapping["y"] = pop(cat) or ""
        mapping["value"] = pop(num) or ""

    elif cid in ("calendar_heatmap", "calendar_chart"):
        mapping["date"] = pop(dt) or ""
        mapping["value"] = pop(num) or ""

    elif cid in ("sankey", "chord_diagram", "network_graph", "network_diagram", "graph_gl"):
        mapping["source"] = pop(src) or pop(cat) or ""
        mapping["target"] = pop(tgt) or pop(cat) or ""
        if num:
            mapping["value"] = pop(num) or ""

    elif cid in ("treemap", "sunburst", "partition_map"):
        mapping["parent"] = pop(cat) or ""
        mapping["child"] = pop(cat) or ""
        mapping["value"] = pop(num) or ""

    elif cid == "tree_chart":
        mapping["parent"] = pop(cat) or ""
        mapping["child"] = pop(cat) or ""

    elif cid == "geographic_region_map":
        mapping["region"] = pop(geo_named) or pop(cat) or ""
        mapping["value"] = pop(num) or ""

    elif cid in ("3d_scatter_map", "heatmap_geo", "3d_hexagon_map"):
        mapping["latitude"] = pop(lat) or ""
        mapping["longitude"] = pop(lon) or ""
        mapping["value"] = pop(num) or ""

    elif cid in ("geo_connection_lines", "3d_arc_map", "3d_geo_arcs"):
        mapping["src_lat"] = pop(lat) or ""
        mapping["src_lon"] = pop(lon) or ""
        mapping["dst_lat"] = pop(lat) or ""
        mapping["dst_lon"] = pop(lon) or ""
        if num:
            mapping["value"] = pop(num) or ""

    elif cid == "3d_geographic_globe":
        mapping["latitude"] = pop(lat) or ""
        mapping["longitude"] = pop(lon) or ""
        if num:
            mapping["value"] = pop(num) or ""

    elif cid in ("candlestick_chart",):
        mapping["date"] = pop(dt) or ""
        mapping["open"] = pop(num) or ""
        mapping["close"] = pop(num) or ""
        mapping["low"] = pop(num) or ""
        mapping["high"] = pop(num) or ""

    elif cid == "radar":
        mapping["series"] = pop(cat) or ""
        mapping["dimensions"] = ",".join(num[:6])

    elif cid in ("scatter_matrix", "correlation_matrix", "parallel_coordinates"):
        mapping["dimensions"] = ",".join(num[:8])

    elif cid == "box_plot":
        mapping["category"] = pop(cat) or ""
        mapping["values"] = pop(num) or ""

    elif cid == "theme_river":
        mapping["date"] = pop(dt) or ""
        mapping["category"] = pop(cat) or ""
        mapping["value"] = pop(num) or ""

    elif cid == "bump_chart":
        mapping["time"] = pop(dt) or pop(cat) or ""
        mapping["category"] = pop(cat) or ""
        mapping["rank"] = pop(num) or ""

    elif cid == "polar_line":
        mapping["x"] = pop(cat) or pop(dt) or ""
        mapping["y"] = pop(num) or ""

    elif cid in ("kpi", "big_number", "big_number_total", "gauge"):
        mapping["value"] = pop(num) or ""
        if num:
            mapping["target"] = pop(num) or ""

    elif cid in ("progress_bar", "bullet_chart"):
        mapping["value"] = pop(num) or ""
        mapping["target"] = pop(num) or ""
        mapping["category"] = pop(cat) or ""

    elif cid in ("table", "pivot_table"):
        mapping["columns"] = ",".join(list(profile.column_profiles.keys())[:10])

    elif cid in ("scatter_gl", "lines_gl", "flow_gl_vector_field"):
        mapping["x"] = pop(num) or ""
        mapping["y"] = pop(num) or ""
        if cat:
            mapping["color"] = pop(cat) or ""

    else:
        # Generic fallback
        if cat:
            mapping["x"] = pop(cat) or ""
        if num:
            mapping["y"] = pop(num) or ""

    # Remove empty mappings
    return {k: v for k, v in mapping.items() if v}
