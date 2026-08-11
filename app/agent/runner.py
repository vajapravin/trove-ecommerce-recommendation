"""Recommendation agent runner.

High-level interface function `run_recommendation_agent(db, user_id)`:
1. Aggregates user behavior via `summarize_user_activity`.
2. Executes the LangGraph recommendation state graph.
3. Persists output narrative, grounded product IDs, and fingerprint to DB `Recommendation`.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.agent.graph import recommendation_graph
from app.agent.state import AgentState
from app.models import Recommendation
from app.services.activity_summary import summarize_user_activity

logger = logging.getLogger("trove.agent")


def run_recommendation_agent(
    db: Session,
    user_id: int,
    source: str = "web",
) -> Recommendation:
    """Run the recommendation agent graph for user_id and persist the result."""
    summary = summarize_user_activity(db, user_id=user_id)

    initial_state: AgentState = {
        "user_id": user_id,
        "activity_summary": {
            "total_events": summary.total_events,
            "search_queries": summary.search_queries,
            "viewed_product_ids": summary.viewed_product_ids,
            "viewed_product_titles": summary.viewed_product_titles,
            "interacted_categories": summary.interacted_categories,
            "interacted_levels": summary.interacted_levels,
            "cart_product_ids": summary.cart_product_ids,
        },
        "formatted_summary": summary.formatted_summary,
        "refine_count": 0,
        "fingerprint": summary.activity_fingerprint,
    }

    logger.info("Executing LangGraph recommendation agent for user_id=%d", user_id)
    final_state = recommendation_graph.invoke(initial_state)

    narrative = final_state.get("narrative", "Explore our product catalog for personalized recommendations!")
    product_ids = final_state.get("recommended_product_ids", [])
    fingerprint = summary.activity_fingerprint

    interests_summary = {
        "queries": summary.search_queries,
        "categories": summary.interacted_categories,
        "levels": summary.interacted_levels,
    }

    reco = Recommendation(
        user_id=user_id,
        narrative=narrative,
        product_ids_json=json.dumps(product_ids),
        fingerprint=fingerprint,
        source=source,
        interests_json=json.dumps(interests_summary),
    )
    db.add(reco)
    db.commit()
    db.refresh(reco)

    logger.info("Saved recommendation id=%d for user_id=%d with %d products", reco.id, user_id, len(product_ids))
    return reco
