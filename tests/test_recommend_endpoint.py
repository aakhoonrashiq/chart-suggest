"""
Integration tests for the single POST /recommend-charts workflow.
Tests:
- Single POST CSV recommendation flow
- Top-N selection (3, 5, 10)
- Backend default Top-N configuration
- Invalid Top-N values (0, -1, 'abc', 'null', 1000)
- Error handling (empty file, non-CSV, missing file)
- Verification that no ECharts configurations are returned
- House price dataset recommendation testing
"""
import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from main import app
from config import DEFAULT_TOP_N, MAX_TOP_N, MIN_TOP_N

client = TestClient(app)
DATA_DIR = os.path.join(os.path.dirname(__file__), "test_datasets")
HOUSE_PRICE_CSV = os.path.join(DATA_DIR, "house_price_dataset.csv")


class TestRecommendChartsWorkflow:
    def test_single_post_recommend_charts_success(self):
        """Verify the single POST /recommend-charts endpoint returns complete recommendations."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp = client.post(
                "/recommend-charts",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
                data={"top_n": "5"},
            )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()

        assert data["success"] is True
        assert "dataset" in data
        assert data["dataset"]["filename"] == "house_price_dataset.csv"
        assert data["dataset"]["rows"] == 1200
        assert data["dataset"]["columns"] == 6

        assert "profile" in data
        assert "relationships_detected" in data
        assert "total_charts_evaluated" in data
        assert data["total_charts_evaluated"] == 81
        assert "total_charts_eligible" in data
        assert data["total_charts_eligible"] > 0

        recs = data["recommendations"]
        assert len(recs) == 5
        assert data["top_n"] == 5

    def test_single_application_route_exclusivity(self):
        """Verify that POST /recommend-charts is the only exposed application endpoint and old /api/ routes are not mounted."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp_old_alias = client.post(
                "/api/recommend-charts",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
                data={"top_n": "3"},
            )
        assert resp_old_alias.status_code == 404

        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp_old_upload = client.post(
                "/api/upload-csv",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
            )
        assert resp_old_upload.status_code == 404

    def test_recommendation_metadata_has_no_echarts_config(self):
        """Verify that the recommendation endpoint returns metadata only and does NOT generate ECharts configs."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp = client.post(
                "/recommend-charts",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
                data={"top_n": "5"},
            )
        assert resp.status_code == 200
        recs = resp.json()["recommendations"]

        for rec in recs:
            # Must NOT contain ECharts rendering configuration
            assert "echarts_config" not in rec or rec.get("echarts_config") is None
            assert "series" not in rec
            assert "xAxis" not in rec
            assert "yAxis" not in rec

            # Must contain recommendation metadata
            assert "rank" in rec
            assert "chart_id" in rec
            assert "chart_name" in rec
            assert "chart_type" in rec
            assert "chart_type_label" in rec
            assert "category" in rec
            assert "score" in rec
            assert "confidence" in rec
            assert "reason" in rec
            assert "mapping" in rec
            assert isinstance(rec["mapping"], dict)

    def test_ranking_descending_by_score(self):
        """Verify recommendations are strictly sorted by score descending."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp = client.post(
                "/recommend-charts",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
                data={"top_n": "10"},
            )
        assert resp.status_code == 200
        recs = resp.json()["recommendations"]
        scores = [r["score"] for r in recs]
        assert scores == sorted(scores, reverse=True)


class TestTopNConfiguration:
    def test_default_top_n_when_omitted(self):
        """When top_n is omitted, the backend uses DEFAULT_TOP_N."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp = client.post(
                "/recommend-charts",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["top_n"] == DEFAULT_TOP_N
        assert len(data["recommendations"]) == DEFAULT_TOP_N

    def test_default_top_n_when_null_or_empty(self):
        """When top_n is empty or 'null', the backend falls back to DEFAULT_TOP_N."""
        for empty_val in ["", "null", "none"]:
            with open(HOUSE_PRICE_CSV, "rb") as f:
                resp = client.post(
                    "/recommend-charts",
                    files={"file": ("house_price_dataset.csv", f, "text/csv")},
                    data={"top_n": empty_val},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["top_n"] == DEFAULT_TOP_N
            assert len(data["recommendations"]) == DEFAULT_TOP_N

    def test_top_n_values_3_5_10(self):
        """Verify top_n=3, 5, 10 return exact number of recommendations."""
        for n in [3, 5, 10]:
            with open(HOUSE_PRICE_CSV, "rb") as f:
                resp = client.post(
                    "/recommend-charts",
                    files={"file": ("house_price_dataset.csv", f, "text/csv")},
                    data={"top_n": str(n)},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["recommendations"]) == n
            assert data["top_n"] == n
            # Ranks must be 1..N
            assert [r["rank"] for r in data["recommendations"]] == list(range(1, n + 1))

    def test_top_n_as_query_parameter(self):
        """Verify top_n passed via query param works as well."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp = client.post(
                "/recommend-charts?top_n=4",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
            )
        assert resp.status_code == 200
        assert len(resp.json()["recommendations"]) == 4

    def test_invalid_top_n_zero(self):
        """top_n=0 returns 422 Unprocessable Entity."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp = client.post(
                "/recommend-charts",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
                data={"top_n": "0"},
            )
        assert resp.status_code == 422
        assert f"at least {MIN_TOP_N}" in resp.json()["detail"]

    def test_invalid_top_n_negative(self):
        """top_n=-1 returns 422 Unprocessable Entity."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp = client.post(
                "/recommend-charts",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
                data={"top_n": "-1"},
            )
        assert resp.status_code == 422
        assert f"at least {MIN_TOP_N}" in resp.json()["detail"]

    def test_invalid_top_n_non_numeric(self):
        """top_n='abc' returns 422 Unprocessable Entity."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp = client.post(
                "/recommend-charts",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
                data={"top_n": "abc"},
            )
        assert resp.status_code == 422
        assert "must be an integer" in resp.json()["detail"]

    def test_invalid_top_n_exceeds_max(self):
        """top_n=1000 returns 422 Unprocessable Entity."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp = client.post(
                "/recommend-charts",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
                data={"top_n": "1000"},
            )
        assert resp.status_code == 422
        assert f"cannot exceed {MAX_TOP_N}" in resp.json()["detail"]


class TestErrorHandling:
    def test_missing_file_parameter(self):
        """Missing file parameter returns 422 from FastAPI validation."""
        resp = client.post("/recommend-charts", data={"top_n": "5"})
        assert resp.status_code == 422

    def test_non_csv_file_rejected(self):
        """Non-CSV file extension returns 400."""
        resp = client.post(
            "/recommend-charts",
            files={"file": ("test.txt", b"column1,column2\n1,2", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Only .csv files are supported" in resp.json()["detail"]

    def test_empty_csv_rejected(self):
        """Empty CSV returns 422."""
        resp = client.post(
            "/recommend-charts",
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert resp.status_code == 422
        assert "Uploaded file is empty" in resp.json()["detail"]

    def test_no_data_rows_csv_rejected(self):
        """CSV with no data rows returns 422."""
        resp = client.post(
            "/recommend-charts",
            files={"file": ("nodata.csv", b"colA,colB\n", "text/csv")},
        )
        assert resp.status_code == 422


class TestMinScoreNotUserConfigurable:
    """
    Verify that min_score is NOT exposed as a user-configurable API parameter.

    The backend always enforces MIN_SCORE = 60 regardless of what the user sends.
    """

    def test_min_score_absent_from_openapi_schema(self):
        """min_score must NOT appear in the OpenAPI parameter list for POST /recommend-charts."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        endpoint = schema["paths"]["/recommend-charts"]["post"]
        # Collect all parameter names
        params = [p["name"] for p in endpoint.get("parameters", [])]
        assert "min_score" not in params, (
            f"min_score must not be a user-facing API parameter, but found in: {params}"
        )

    def test_request_succeeds_without_min_score(self):
        """A request with only file + top_n (no min_score) must succeed."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp = client.post(
                "/recommend-charts",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
                data={"top_n": "5"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["recommendations"]) > 0

    def test_user_cannot_lower_threshold_via_query_param(self):
        """Sending min_score=30 via query string must NOT override the backend 60% threshold.
        All returned charts must still have score >= 60."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp = client.post(
                "/recommend-charts?min_score=30",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
                data={"top_n": "20"},
            )
        assert resp.status_code == 200
        for rec in resp.json()["recommendations"]:
            assert rec["score"] >= 60, (
                f"Chart '{rec['chart_id']}' scored {rec['score']} — below the fixed 60% threshold"
            )

    def test_user_cannot_raise_threshold_via_query_param(self):
        """Sending min_score=90 via query string must NOT override the backend 60% threshold."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp = client.post(
                "/recommend-charts?min_score=90",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
                data={"top_n": "20"},
            )
        assert resp.status_code == 200
        # All returned charts must have score >= 60 (backend threshold),
        # NOT >= 90 (user-attempted override that must be ignored).
        for rec in resp.json()["recommendations"]:
            assert rec["score"] >= 60

    def test_all_returned_scores_gte_60(self):
        """Every recommendation returned by the API must have score >= 60."""
        with open(HOUSE_PRICE_CSV, "rb") as f:
            resp = client.post(
                "/recommend-charts",
                files={"file": ("house_price_dataset.csv", f, "text/csv")},
                data={"top_n": "20"},
            )
        assert resp.status_code == 200
        for rec in resp.json()["recommendations"]:
            assert rec["score"] >= 60, (
                f"Chart '{rec['chart_id']}' returned with score {rec['score']} — below fixed 60% threshold"
            )

