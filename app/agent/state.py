"""LangGraph agent state schema.

Defines the state passed through each node of the recommendation workflow:
    analyze_activity → decide_retrieve → retrieve → evaluate → [refine] → generate
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    """State object passed through the recommendation state graph."""

    user_id: int
    activity_summary: Dict[str, Any]
    formatted_summary: str
    extracted_query: str
    category_filter: Optional[str]
    level_filter: Optional[str]
    retrieved_products: List[Dict[str, Any]]
    evaluation_passed: bool
    refine_count: int
    narrative: str
    recommended_product_ids: List[int]
    fingerprint: str
    error: Optional[str]
