"""
Chart matcher — loads the catalog and runs the full scoring pipeline.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from models.dataset import DatasetProfile
from models.recommendation import ChartRecommendation, ColumnMapping
from services.relationship_detector import detect_relationships
from services.scoring_engine import score_chart

logger = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).parent.parent / "catalog" / "chart_catalog.json"

# Load catalog once at import time
_CATALOG: List[Dict[str, Any]] = []

def _load_catalog() -> List[Dict[str, Any]]:
    global _CATALOG
    if _CATALOG:
        return _CATALOG
    with open(CATALOG_PATH) as f:
        data = json.load(f)
    _CATALOG = data["charts"]
    logger.info(f"Chart catalog loaded: {len(_CATALOG)} charts")
    return _CATALOG


def _confidence(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 60:
        return "medium"
    if score >= 40:
        return "low"
    return "none"


def get_recommendations(
    profile: DatasetProfile,
    top_n: int = 12,
    min_score: int = 60,
    generate_configs: bool = True,
) -> tuple[List[ChartRecommendation], List[str], int, int]:
    """
    Run the full recommendation pipeline.
    Returns (recommendations, relationships, total_evaluated, total_eligible).
    """
    catalog = _load_catalog()
    relationships = detect_relationships(profile)

    logger.info(f"Relationships detected: {relationships}")
    logger.info(f"Evaluating {len(catalog)} charts...")

    scored: List[tuple[int, ChartRecommendation]] = []
    eligible = 0

    for chart in catalog:
        raw_score, reason, mapping = score_chart(chart, profile, relationships)
        if raw_score == 0:
            continue

        eligible += 1
        col_mappings = [
            ColumnMapping(
                role=role,
                column=col,
                semantic_type=profile.column_profiles[col].semantic_type
                if col in profile.column_profiles else "unknown",
            )
            for role, col in mapping.items()
            if col
        ]

        if generate_configs:
            from services.config_generator import generate_echarts_config
            echarts_cfg = generate_echarts_config(chart, mapping, profile)
        else:
            echarts_cfg = None

        rec = ChartRecommendation(
            chart_id=chart["id"],
            chart_name=chart["name"],
            category=chart["category"],
            score=raw_score,
            confidence=_confidence(raw_score),
            reason=reason,
            mapping=mapping,
            column_mappings=col_mappings,
            echarts_config=echarts_cfg,
        )
        scored.append((raw_score, rec))

    # Sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)

    # Filter by minimum score and take top N
    top = [r for _, r in scored if r.score >= min_score][:top_n]

    logger.info(f"Total evaluated: {len(catalog)}, eligible: {eligible}, returned: {len(top)}")
    return top, relationships, len(catalog), eligible
