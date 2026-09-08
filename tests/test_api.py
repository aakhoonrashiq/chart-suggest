"""API integration tests for the single public POST /recommend-charts endpoint."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient
from main import app
from services.chart_matcher import _load_catalog

client = TestClient(app)
DATA_DIR = os.path.join(os.path.dirname(__file__), "test_datasets")


def post_csv(filename: str, top_n: int = 10):
    """Post a CSV to /recommend-charts and return the response."""
    with open(os.path.join(DATA_DIR, filename), "rb") as f:
        return client.post(
            "/recommend-charts",
            files={"file": (filename, f, "text/csv")},
            data={"top_n": str(top_n)},
        )


class TestUploadCSVValidation:
    def test_upload_success(self):
        resp = post_csv("dataset1_categorical.csv")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["dataset"]["filename"] == "dataset1_categorical.csv"

    def test_upload_non_csv_rejected(self):
        resp = client.post(
            "/recommend-charts",
            files={"file": ("file.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Only .csv files are supported" in resp.json()["detail"]

    def test_upload_empty_file(self):
        resp = client.post(
            "/recommend-charts",
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert resp.status_code == 422
        assert "Uploaded file is empty" in resp.json()["detail"]

    def test_upload_no_headers(self):
        content = b"1,2,3\n4,5,6\n7,8,9"
        resp = client.post(
            "/recommend-charts",
            files={"file": ("noheader.csv", content, "text/csv")},
        )
        # Either succeeds or returns 422 if unnamed header check triggers
        assert resp.status_code in (200, 422)


class TestProfileInResponse:
    def test_profile_returns_columns(self):
        resp = post_csv("dataset1_categorical.csv")
        assert resp.status_code == 200
        data = resp.json()
        assert "profile" in data
        cols = data["profile"]["columns"]
        assert "Product" in cols
        assert "Sales" in cols

    def test_profile_timeseries_signals(self):
        resp = post_csv("dataset2_timeseries.csv")
        assert resp.status_code == 200
        signals = resp.json()["profile"]["signals"]
        assert signals["has_datetime"] is True
        assert signals["has_numeric"] is True

    def test_profile_geo_signals(self):
        resp = post_csv("dataset5_geographic.csv")
        assert resp.status_code == 200
        signals = resp.json()["profile"]["signals"]
        assert signals["has_geo_latlon"] is True

    def test_profile_flow_signals(self):
        resp = post_csv("dataset7_flow.csv")
        assert resp.status_code == 200
        signals = resp.json()["profile"]["signals"]
        assert signals["has_flow"] is True


class TestChartSuggestionsInResponse:
    def test_suggestions_returned(self):
        resp = post_csv("dataset1_categorical.csv")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["recommendations"]) > 0

    def test_suggestions_have_scores(self):
        resp = post_csv("dataset1_categorical.csv")
        recs = resp.json()["recommendations"]
        for rec in recs:
            assert 0 <= rec["score"] <= 100

    def test_suggestions_sorted_descending(self):
        resp = post_csv("dataset2_timeseries.csv")
        scores = [r["score"] for r in resp.json()["recommendations"]]
        assert scores == sorted(scores, reverse=True)

    def test_suggestions_have_mapping(self):
        resp = post_csv("dataset1_categorical.csv")
        for rec in resp.json()["recommendations"]:
            assert len(rec["mapping"]) > 0

    def test_suggestions_have_metadata(self):
        resp = post_csv("dataset1_categorical.csv")
        data = resp.json()
        assert "total_charts_evaluated" in data
        assert "total_charts_eligible" in data
        assert "relationships_detected" in data
        assert data["total_charts_evaluated"] == 81

    def test_line_top_for_timeseries(self):
        resp = post_csv("dataset2_timeseries.csv")
        top3_ids = [r["chart_id"] for r in resp.json()["recommendations"][:3]]
        # Either table, line, or area should be top for timeseries
        assert any(cid in ["line", "area", "table"] for cid in top3_ids)

    def test_scatter_for_two_numerics(self):
        resp = post_csv("dataset3_numeric.csv")
        ids = [r["chart_id"] for r in resp.json()["recommendations"]]
        assert "scatter" in ids

    def test_top_n_param(self):
        resp = post_csv("dataset1_categorical.csv", top_n=3)
        assert len(resp.json()["recommendations"]) <= 3


class TestCatalogIntegrity:
    def test_catalog_loads_81_charts(self):
        catalog = _load_catalog()
        assert len(catalog) == 81

    def test_catalog_has_required_fields(self):
        catalog = _load_catalog()
        chart = catalog[0]
        required_fields = {"id", "name", "category", "description", "echarts_type"}
        assert required_fields.issubset(set(chart.keys()))
