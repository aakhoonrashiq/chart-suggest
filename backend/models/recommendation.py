"""Pydantic models for chart recommendations."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ColumnMapping(BaseModel):
    """Maps chart axis/role to CSV column name."""
    role: str           # e.g. "x", "y", "source", "target", "value", "z"
    column: str         # the actual CSV column name
    semantic_type: str  # type of that column


class ChartRecommendation(BaseModel):
    chart_id: str
    chart_name: str
    category: str
    score: int                          # 0–100
    confidence: str                     # "high" | "medium" | "low" | "none"
    reason: str
    mapping: Dict[str, str]             # role → column_name
    column_mappings: List[ColumnMapping]
    echarts_config: Optional[Dict[str, Any]] = None
    warnings: List[str] = []


class RecommendationResponse(BaseModel):
    dataset: Dict[str, Any]
    profile: Dict[str, Any]
    recommendations: List[ChartRecommendation]
    relationships_detected: List[str]
    total_charts_evaluated: int
    total_charts_eligible: int
