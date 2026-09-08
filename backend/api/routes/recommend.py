"""
Single POST API for the Chart Recommendation workflow:
POST /recommend-charts (and /api/recommend-charts)

Orchestrates the complete recommendation process in one request:
CSV Upload -> CSV Validation -> Dataset Parsing -> Dataset Profiling ->
Column Type Detection -> Semantic Detection -> Relationship Detection ->
Chart Catalog Matching -> Eligibility Check -> Suitability Scoring ->
Ranking -> Top-N Selection -> Recommendation Metadata Response.

Returns recommendation metadata only without generating ECharts configurations.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from config import DEFAULT_TOP_N, MAX_TOP_N, MIN_TOP_N, MIN_SCORE
from services.csv_service import CSVValidationError, get_dataset, load_csv
from services.profiler import profile_dataset
from services.chart_matcher import _load_catalog, get_recommendations

router = APIRouter()
logger = logging.getLogger(__name__)


def _format_chart_type_label(chart_id: str, chart_name: str) -> str:
    """Format chart identifier into human-readable uppercase type label."""
    cid = chart_id.lower().replace("-", "_")
    if cid == "3d_scatter_plot":
        return "3D SCATTER PLOT"
    if cid == "3d_bar_chart":
        return "3D BAR CHART"
    if cid == "3d_line_chart":
        return "3D LINE CHART"
    if cid == "3d_surface_plot":
        return "3D SURFACE PLOT"
    if cid == "scatter":
        return "SCATTER PLOT"
    if cid == "bubble":
        return "BUBBLE CHART"
    if cid == "bar":
        return "BAR CHART"
    if cid == "line":
        return "LINE CHART"
    if cid == "pie":
        return "PIE CHART"
    if cid == "table":
        return "TABLE"

    # General cleanup
    cleaned = cid.replace("_chart", "").replace("_plot", "")
    label = cleaned.replace("_", " ").upper()
    if not any(label.endswith(w) for w in ["CHART", "PLOT", "MAP", "GRAPH", "TABLE", "MATRIX", "COORDINATES", "RIVER", "TREE", "BURST", "CLOUD"]):
        if "SCATTER" in label or "BOX" in label or "CONTOUR" in label:
            label += " PLOT"
        else:
            label += " CHART"
    return label


def _validate_and_parse_top_n(top_n_form: Optional[str], top_n_query: Optional[str]) -> int:
    """Validate and parse top_n parameter from form field or query parameter."""
    # Query parameter takes precedence if explicitly passed; otherwise use form field
    raw_val = top_n_query if top_n_query is not None else top_n_form

    # If omitted, null, or empty string, fallback to default
    if raw_val is None:
        return DEFAULT_TOP_N

    raw_str = str(raw_val).strip()
    if raw_str == "" or raw_str.lower() in ("null", "none", "undefined"):
        return DEFAULT_TOP_N

    try:
        val = int(raw_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid top_n '{raw_val}': must be an integer."
        )

    if val < MIN_TOP_N:
        raise HTTPException(
            status_code=422,
            detail=f"top_n must be at least {MIN_TOP_N} (got {val})."
        )

    if val > MAX_TOP_N:
        raise HTTPException(
            status_code=422,
            detail=f"top_n cannot exceed {MAX_TOP_N} (got {val})."
        )

    return val


@router.post("/recommend-charts")
async def recommend_charts(
    request: Request,
    file: UploadFile = File(...),
    top_n: Optional[str] = Form(
        default=str(DEFAULT_TOP_N),
        description=f"Number of top chart recommendations to return (default: {DEFAULT_TOP_N}, range: {MIN_TOP_N}–{MAX_TOP_N})"
    ),
):
    """
    Single POST API for the complete chart recommendation workflow.
    Accepts a CSV file + optional Top-N value.
    Performs CSV parsing, profiling, semantic detection, relationship detection,
    chart matching, scoring, ranking, and Top-N selection.
    Only charts with a suitability score >= 60% (MIN_SCORE — backend-controlled, not user-configurable) are returned.
    Returns recommendation metadata only (no ECharts rendering configuration).
    """

    # 1. Validate file existence and extension
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No CSV file provided.")

    filename = file.filename
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    # 2. Validate Top-N parameter
    query_top_n = request.query_params.get("top_n")
    effective_top_n = _validate_and_parse_top_n(top_n, query_top_n)
    logger.info(f"CSV received: file={filename}, requested top_n={effective_top_n}")

    # 3. CSV parsing and validation
    try:
        content = await file.read()
        dataset_id = load_csv(content, filename)
        df, filename = get_dataset(dataset_id)
        logger.info(f"CSV validated & dataset loaded: {len(df)} rows, {len(df.columns)} columns")
    except CSVValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error during CSV parsing")
        raise HTTPException(status_code=500, detail=f"CSV processing error: {str(e)}")

    # 4. Dataset profiling, column type detection, and semantic detection
    try:
        profile = profile_dataset(df, dataset_id, filename)
        logger.info(f"Dataset profiled: {profile.rows} rows, {profile.columns} cols, numeric={len(profile.numeric_cols)}, categorical={len(profile.categorical_cols)}, datetime={len(profile.datetime_cols)}")
        logger.info("Columns detected & classified")
    except Exception as e:
        logger.exception("Error during dataset profiling")
        raise HTTPException(status_code=500, detail=f"Profiling error: {str(e)}")

    # 5. Relationship detection, chart catalog matching, scoring, and ranking
    try:
        catalog_lookup = {c["id"]: c for c in _load_catalog()}
        recommendations, relationships, total_eval, total_eligible = get_recommendations(
            profile,
            top_n=effective_top_n,
            min_score=MIN_SCORE,  # Fixed at 60% — not user-configurable
            generate_configs=False,  # Recommendation metadata only, NO ECharts configs
        )
        logger.info(f"Relationships detected: {relationships}")
        logger.info(f"Chart recommendations evaluated: {total_eval} catalog charts, {total_eligible} eligible")
        logger.info(f"Charts ranked & Top-{effective_top_n} selected: {len(recommendations)} returned")
    except Exception as e:
        logger.exception("Error during chart recommendation")
        raise HTTPException(status_code=500, detail=f"Recommendation error: {str(e)}")

    # 6. Build recommendation response metadata
    recs_out: List[Dict[str, Any]] = []
    for rank, rec in enumerate(recommendations, start=1):
        chart_def = catalog_lookup.get(rec.chart_id, {})
        chart_type = chart_def.get("echarts_type") or rec.chart_id
        type_label = _format_chart_type_label(rec.chart_id, rec.chart_name)

        recs_out.append({
            "rank": rank,
            "chart_id": rec.chart_id,
            "chart_name": rec.chart_name,
            "chart_type": chart_type,
            "chart_type_label": type_label,
            "category": rec.category,
            "score": rec.score,
            "confidence": rec.confidence,
            "reason": rec.reason,
            "mapping": rec.mapping,
            "column_mappings": [
                {
                    "role": cm.role,
                    "column": cm.column,
                    "semantic_type": cm.semantic_type,
                }
                for cm in rec.column_mappings
            ],
            "warnings": rec.warnings,
        })

    # Column summary for frontend data inspection
    col_summary = {}
    for col_name, cp in profile.column_profiles.items():
        col_summary[col_name] = {
            "semantic_type": cp.semantic_type,
            "unique_count": cp.unique_count,
            "missing_count": cp.missing_count,
            "missing_pct": cp.missing_pct,
        }

    response_payload: Dict[str, Any] = {
        "success": True,
        "dataset": {
            "dataset_id": dataset_id,
            "filename": filename,
            "rows": profile.rows,
            "columns": profile.columns,
        },
        "profile": {
            "columns": col_summary,
            "signals": {
                "has_datetime": profile.has_datetime,
                "has_numeric": profile.has_numeric,
                "has_categorical": profile.has_categorical,
                "has_geo_latlon": profile.has_geo_latlon,
                "has_geo_named": profile.has_geo_named,
                "has_flow": profile.has_flow,
                "has_hierarchy": profile.has_hierarchy,
                "has_ohlc": profile.has_ohlc,
            },
        },
        "relationships_detected": relationships,
        "total_charts_evaluated": total_eval,
        "total_charts_eligible": total_eligible,
        "top_n": effective_top_n,
        "recommendations": recs_out,
    }

    if len(recs_out) == 0:
        response_payload["message"] = "No suitable charts were found for this dataset."

    return JSONResponse(response_payload)
