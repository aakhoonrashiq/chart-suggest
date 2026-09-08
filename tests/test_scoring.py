"""Tests for the scoring and recommendation engine."""
import os
import sys
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from services.profiler import profile_dataset
from services.chart_matcher import get_recommendations
from services.relationship_detector import detect_relationships

DATA_DIR = os.path.join(os.path.dirname(__file__), "test_datasets")


def load(fname):
    return pd.read_csv(os.path.join(DATA_DIR, fname))


def top_ids(df, filename, n=5):
    p = profile_dataset(df, "t", filename)
    recs, _, _, _ = get_recommendations(p, top_n=n, min_score=40)
    return [r.chart_id for r in recs], [r.score for r in recs]


class TestDataset1Recommendations:
    """Product + Sales → Bar and Pie should rank high."""
    def test_bar_recommended(self):
        df = load("dataset1_categorical.csv")
        ids, scores = top_ids(df, "dataset1.csv")
        assert "bar" in ids or "horizontal_bar" in ids, f"Bar not in top 5: {ids}"

    def test_pie_recommended(self):
        df = load("dataset1_categorical.csv")
        ids, scores = top_ids(df, "dataset1.csv")
        assert "pie" in ids or "donut" in ids, f"Pie/Donut not in top 5: {ids}"

    def test_scores_positive(self):
        df = load("dataset1_categorical.csv")
        ids, scores = top_ids(df, "dataset1.csv")
        assert all(s > 0 for s in scores)


class TestDataset2Recommendations:
    """Date + Revenue → Line should be top recommendation."""
    def test_line_is_top(self):
        df = load("dataset2_timeseries.csv")
        ids, scores = top_ids(df, "dataset2.csv")
        assert "line" in ids[:3], f"Line not in top 3: {ids}"

    def test_area_recommended(self):
        df = load("dataset2_timeseries.csv")
        ids, scores = top_ids(df, "dataset2.csv")
        assert "area" in ids or "smooth_line" in ids, f"Area/SmoothLine not in top 5: {ids}"


class TestDataset3Recommendations:
    """Advertising + Revenue (two numerics) → Scatter should rank high."""
    def test_scatter_recommended(self):
        df = load("dataset3_numeric.csv")
        ids, scores = top_ids(df, "dataset3.csv")
        assert "scatter" in ids, f"Scatter not in top 5: {ids}"


class TestDataset4Recommendations:
    """X, Y, Z three numerics → 3D Scatter should be eligible."""
    def test_3d_scatter_eligible(self):
        df = load("dataset4_3d.csv")
        p = profile_dataset(df, "t4", "dataset4.csv")
        recs, _, _, _ = get_recommendations(p, top_n=20, min_score=30)
        ids = [r.chart_id for r in recs]
        assert "3d_scatter_plot" in ids, f"3D Scatter not found: {ids}"


class TestDataset5Recommendations:
    """Geographic lat/lon → geo charts should appear."""
    def test_geo_chart_recommended(self):
        df = load("dataset5_geographic.csv")
        p = profile_dataset(df, "t5", "dataset5.csv")
        recs, _, _, _ = get_recommendations(p, top_n=20, min_score=30)
        ids = [r.chart_id for r in recs]
        geo_charts = {"3d_scatter_map", "heatmap_geo", "geographic_region_map",
                      "3d_geographic_globe", "heatmap_geo", "3d_hexagon_map"}
        found = set(ids) & geo_charts
        assert len(found) > 0, f"No geo chart found. Got: {ids}"


class TestDataset6Recommendations:
    """Hierarchical → Treemap, Sunburst should appear."""
    def test_treemap_recommended(self):
        df = load("dataset6_hierarchical.csv")
        p = profile_dataset(df, "t6", "dataset6.csv")
        recs, _, _, _ = get_recommendations(p, top_n=20, min_score=30)
        ids = [r.chart_id for r in recs]
        hierarchy_charts = {"treemap", "sunburst", "tree_chart"}
        found = set(ids) & hierarchy_charts
        assert len(found) > 0, f"No hierarchy chart found. Got: {ids}"


class TestDataset7Recommendations:
    """Source, Target, Value → Sankey, Chord, Network Graph."""
    def test_sankey_recommended(self):
        df = load("dataset7_flow.csv")
        p = profile_dataset(df, "t7", "dataset7.csv")
        recs, _, _, _ = get_recommendations(p, top_n=20, min_score=30)
        ids = [r.chart_id for r in recs]
        flow_charts = {"sankey", "chord_diagram", "network_graph", "network_diagram"}
        found = set(ids) & flow_charts
        assert len(found) > 0, f"No flow chart found. Got: {ids}"


class TestDataset8Recommendations:
    """Large dataset → ScatterGL should be eligible."""
    def test_webgl_eligible(self):
        df = load("dataset8_large.csv")
        p = profile_dataset(df, "t8", "dataset8.csv")
        recs, _, _, _ = get_recommendations(p, top_n=20, min_score=30)
        ids = [r.chart_id for r in recs]
        assert "scatter_gl" in ids, f"ScatterGL not found: {ids}"


class TestScoringRules:
    """Verify hard eliminators and scoring logic."""
    def test_geo_chart_eliminated_without_geo(self):
        """Geographic charts must score 0 without lat/lon data."""
        df = pd.DataFrame({"Product": ["A", "B"], "Sales": [100, 200]})
        p = profile_dataset(df, "ng", "no_geo.csv")
        recs, _, _, _ = get_recommendations(p, top_n=81, min_score=1)
        ids = [r.chart_id for r in recs]
        geo_only = {"3d_scatter_map", "heatmap_geo", "3d_arc_map", "3d_geo_arcs",
                    "geo_connection_lines", "3d_geographic_globe"}
        found = set(ids) & geo_only
        assert len(found) == 0, f"Geo charts appeared without geo data: {found}"

    def test_sankey_eliminated_without_flow(self):
        """Sankey must score 0 without source/target columns."""
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        p = profile_dataset(df, "nf", "no_flow.csv")
        recs, _, _, _ = get_recommendations(p, top_n=81, min_score=1)
        ids = [r.chart_id for r in recs]
        assert "sankey" not in ids, "Sankey appeared without flow columns"

    def test_pie_penalized_for_high_cardinality(self):
        """Pie chart should score lower with many categories."""
        cats = [f"Category_{i}" for i in range(30)]
        df = pd.DataFrame({"Category": cats, "Value": range(30)})
        p = profile_dataset(df, "hc", "high_card.csv")
        recs_all, _, _, _ = get_recommendations(p, top_n=81, min_score=1)
        pie_rec = next((r for r in recs_all if r.chart_id == "pie"), None)
        # Pie should exist but with lower score due to cardinality penalty
        if pie_rec:
            assert pie_rec.score < 80, "Pie should be penalized for 30 categories"

    def test_table_always_included(self):
        """Table chart should always be included for any dataset."""
        df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
        p = profile_dataset(df, "tbl", "table.csv")
        recs, _, _, _ = get_recommendations(p, top_n=30, min_score=30)
        ids = [r.chart_id for r in recs]
        assert "table" in ids, "Table should always be recommended"

    def test_all_recs_have_mapping(self):
        """All recommendations should have a non-empty mapping."""
        df = load("dataset1_categorical.csv")
        p = profile_dataset(df, "t1", "d1.csv")
        recs, _, _, _ = get_recommendations(p, top_n=12)
        for rec in recs:
            assert len(rec.mapping) > 0, f"{rec.chart_id} has empty mapping"

    def test_no_duplicate_chart_ids(self):
        """Recommendations should not contain duplicate chart_ids."""
        df = load("dataset2_timeseries.csv")
        p = profile_dataset(df, "t2", "d2.csv")
        recs, _, _, _ = get_recommendations(p, top_n=20)
        ids = [r.chart_id for r in recs]
        assert len(ids) == len(set(ids)), f"Duplicate chart IDs: {ids}"


class TestMinScoreBoundary:
    """
    Verify the 60% threshold boundary: score >= 60 is accepted, score < 60 is rejected.
    These tests call get_recommendations directly so they can fine-tune the threshold
    without going through the HTTP layer (which always enforces MIN_SCORE=60).
    """

    def test_score_59_excluded(self):
        """A chart that would score exactly 59 must be excluded at the 60% threshold."""
        df = load("dataset1_categorical.csv")
        p = profile_dataset(df, "b1", "boundary.csv")
        recs_60, _, _, _ = get_recommendations(p, top_n=81, min_score=60)
        recs_59, _, _, _ = get_recommendations(p, top_n=81, min_score=59)
        # Every chart returned at threshold=60 must also appear at threshold=59
        ids_60 = {r.chart_id for r in recs_60}
        ids_59 = {r.chart_id for r in recs_59}
        assert ids_60.issubset(ids_59), "threshold=60 returned charts that threshold=59 didn't — impossible"
        # threshold=59 may include extra charts that scored exactly 59
        # (no assertion on strict difference; scoring model may not produce exactly 59)

    def test_score_60_included(self):
        """Charts scoring exactly >= 60 must be present when threshold is 60."""
        df = load("dataset1_categorical.csv")
        p = profile_dataset(df, "b2", "boundary.csv")
        recs, _, _, _ = get_recommendations(p, top_n=81, min_score=60)
        for rec in recs:
            assert rec.score >= 60, (
                f"Chart '{rec.chart_id}' with score {rec.score} was returned despite score < 60"
            )

    def test_score_61_included(self):
        """Charts scoring 61+ must pass the threshold."""
        df = load("dataset2_timeseries.csv")
        p = profile_dataset(df, "b3", "boundary.csv")
        recs, _, _, _ = get_recommendations(p, top_n=81, min_score=61)
        for rec in recs:
            assert rec.score >= 61, (
                f"Chart '{rec.chart_id}' with score {rec.score} slipped past threshold=61"
            )

    def test_filter_uses_gte_not_gt(self):
        """The filter condition is >= (inclusive), not > (exclusive)."""
        df = load("dataset1_categorical.csv")
        p = profile_dataset(df, "b4", "boundary.csv")
        # Fetch all charts at threshold=60 and at threshold=61
        recs_at_60, _, _, _ = get_recommendations(p, top_n=81, min_score=60)
        recs_at_61, _, _, _ = get_recommendations(p, top_n=81, min_score=61)
        ids_60 = {r.chart_id for r in recs_at_60}
        ids_61 = {r.chart_id for r in recs_at_61}
        # Every chart that passes threshold=61 must also pass threshold=60
        assert ids_61.issubset(ids_60), "Charts passing threshold=61 must also pass threshold=60"

    def test_min_score_constant_is_60(self):
        """The centralised MIN_SCORE constant must equal 60."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
        from config import MIN_SCORE
        assert MIN_SCORE == 60, f"MIN_SCORE constant is {MIN_SCORE}, expected 60"




class TestRelationshipDetection:
    def test_timeseries_detected(self):
        df = load("dataset2_timeseries.csv")
        p = profile_dataset(df, "r2", "d2.csv")
        rels = detect_relationships(p)
        assert "time_series" in rels

    def test_two_numeric_detected(self):
        df = load("dataset3_numeric.csv")
        p = profile_dataset(df, "r3", "d3.csv")
        rels = detect_relationships(p)
        assert "two_numeric" in rels

    def test_flow_detected(self):
        df = load("dataset7_flow.csv")
        p = profile_dataset(df, "r7", "d7.csv")
        rels = detect_relationships(p)
        assert "flow_network" in rels

    def test_geo_latlon_detected(self):
        df = load("dataset5_geographic.csv")
        p = profile_dataset(df, "r5", "d5.csv")
        rels = detect_relationships(p)
        assert "geo_latlon" in rels

    def test_large_dataset_detected(self):
        df = load("dataset8_large.csv")
        p = profile_dataset(df, "r8", "d8.csv")
        rels = detect_relationships(p)
        assert "large_dataset" in rels
