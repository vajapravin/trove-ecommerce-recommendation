"""LangGraph workflow node implementations.

Each function takes `AgentState` and returns updated state dict keys.
Nodes:
  1. analyze_activity: Summarizes behavior into query & optional metadata filters.
  2. decide_retrieve: Validates search criteria before retrieval.
  3. retrieve: Queries Chroma vector store with semantic query + metadata filters.
  4. evaluate: Checks if shortlist meets quality & relevance threshold.
  5. refine: Broadens/adjusts query parameters if evaluation fails.
  6. generate: Produces persuasive narrative + product picks grounded in Chroma IDs.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.agent.state import AgentState
from app.config import get_settings
from app.mesh_client import chat_complete
from app.vector_store import query_products

logger = logging.getLogger("trove.agent")


def analyze_activity_node(state: AgentState) -> Dict[str, Any]:
    """Node 1: Extract core search query and category/level preferences from activity summary."""
    summary_text = state.get("formatted_summary", "")
    summary_dict = state.get("activity_summary", {})

    search_queries = summary_dict.get("search_queries", [])
    categories = summary_dict.get("interacted_categories", [])
    levels = summary_dict.get("interacted_levels", [])
    viewed_titles = summary_dict.get("viewed_product_titles", [])

    default_query = search_queries[0] if search_queries else (
        " ".join(viewed_titles[:2]) if viewed_titles else "software engineering courses"
    )
    default_cat = categories[0] if categories else None
    default_level = levels[0] if levels else None

    settings = get_settings()
    if not settings.MESH_API_KEY:
        logger.info("MESH_API_KEY not set; using heuristic activity analysis")
        return {
            "extracted_query": default_query,
            "category_filter": default_cat,
            "level_filter": default_level,
        }

    system_prompt = (
        "You are an e-commerce interest analysis AI. Analyze the shopper's recent behavior summary "
        "and return a JSON object with: \n"
        '  "search_query": string (a concise 3-6 word semantic search query capturing what they are looking for),\n'
        '  "category": string or null (one primary category if evident, e.g. "AI", "Backend", "Data", "DevOps"),\n'
        '  "level": string or null ("beginner", "intermediate", "advanced", or null).\n'
        "Output ONLY valid JSON."
    )

    user_prompt = f"Shopper Activity Summary:\n{summary_text}"

    try:
        raw_response = chat_complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(raw_response)
        query = parsed.get("search_query") or default_query
        cat = parsed.get("category") or default_cat
        lvl = parsed.get("level") or default_level
        return {
            "extracted_query": query,
            "category_filter": cat,
            "level_filter": lvl,
        }
    except Exception as exc:
        logger.warning("LLM analyze node error (%s); falling back to heuristics", exc)
        return {
            "extracted_query": default_query,
            "category_filter": default_cat,
            "level_filter": default_level,
        }


def decide_retrieve_node(state: AgentState) -> Dict[str, Any]:
    """Node 2: Decision node ensuring valid query parameters exist."""
    query = state.get("extracted_query", "").strip()
    if not query:
        query = "best recommended courses"
    return {"extracted_query": query}


def retrieve_node(state: AgentState) -> Dict[str, Any]:
    """Node 3: Semantic search via Chroma vector store with metadata filtering."""
    query = state.get("extracted_query", "courses")
    cat = state.get("category_filter")
    lvl = state.get("level_filter")

    conditions: List[Dict[str, Any]] = []
    if cat:
        conditions.append({"category": cat})
    if lvl:
        conditions.append({"level": lvl})

    where_clause: Dict[str, Any] = {}
    if len(conditions) == 1:
        where_clause = conditions[0]
    elif len(conditions) > 1:
        where_clause = {"$and": conditions}

    hits = query_products(
        query_text=query,
        n_results=15,
        where=where_clause if where_clause else None,
    )

    # If filtered search returned nothing, fall back to unfiltered search
    if not hits and where_clause:
        logger.info("Filtered retrieve returned 0 hits; trying unfiltered query: %r", query)
        hits = query_products(query_text=query, n_results=15)

    return {"retrieved_products": hits}



def evaluate_node(state: AgentState) -> Dict[str, Any]:
    """Node 4: Check if retrieval yields sufficient relevant candidate products."""
    hits = state.get("retrieved_products", [])
    refine_count = state.get("refine_count", 0)

    # We want at least 1 product; if zero products and refine_count < 2, trigger refine
    passed = len(hits) > 0 or refine_count >= 2
    return {"evaluation_passed": passed}


def refine_node(state: AgentState) -> Dict[str, Any]:
    """Node 5: Broaden search criteria if evaluation failed."""
    refine_count = state.get("refine_count", 0) + 1
    # Drop category and level filters to broaden retrieval
    return {
        "refine_count": refine_count,
        "category_filter": None,
        "level_filter": None,
    }


def generate_node(state: AgentState) -> Dict[str, Any]:
    """Node 6: Write persuasive personalized narrative & pick products grounded in Chroma retrieval."""
    hits = state.get("retrieved_products", [])
    summary_text = state.get("formatted_summary", "")
    settings = get_settings()

    if not hits:
        return {
            "narrative": "We noticed your recent visits! Browse our full catalog to discover great learning paths.",
            "recommended_product_ids": [],
        }

    candidate_ids = [h["product_id"] for h in hits]
    candidate_summary = "\n".join(
        f"- ID {h['product_id']}: '{h['title']}' | Category: {h['category']} | Level: {h['level']} | Price: ${h['price']:.2f}"
        for h in hits[:8]
    )

    fallback_picks = candidate_ids[:3]
    fallback_narrative = (
        f"Based on your recent interest in {hits[0]['category']} and related topics, "
        f"we have selected top courses tailored for your journey. Explore these recommendations below to level up your skills!"
    )

    if not settings.MESH_API_KEY:
        logger.info("MESH_API_KEY not set; returning heuristic grounded recommendation")
        return {
            "narrative": fallback_narrative,
            "recommended_product_ids": fallback_picks,
        }

    system_prompt = (
        "You are Trove's expert AI recommendation agent. Write a personalized, persuasive narrative "
        "recommending products to a shopper based on their activity summary.\n"
        "CRITICAL RULE: You MUST ONLY select product IDs from the provided Candidates list below. "
        "Do NOT invent or hallucinate any product ID.\n"
        "Return a JSON object with:\n"
        '  "narrative": string (2 short, warm, highly persuasive paragraphs tailored to the shopper),\n'
        '  "product_ids": list of integers (3 to 5 chosen IDs from Candidates list).\n'
        "Output ONLY valid JSON."
    )

    user_prompt = (
        f"Shopper Activity Summary:\n{summary_text}\n\n"
        f"Candidates (retrieve from catalog):\n{candidate_summary}\n"
    )

    try:
        raw_response = chat_complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(raw_response)
        narrative = parsed.get("narrative") or fallback_narrative
        chosen_ids = parsed.get("product_ids") or fallback_picks

        # Enforce strict grounding: filter out any ID not present in candidate_ids
        grounded_ids = [pid for pid in chosen_ids if pid in candidate_ids]
        if not grounded_ids:
            grounded_ids = fallback_picks

        return {
            "narrative": narrative,
            "recommended_product_ids": grounded_ids,
        }
    except Exception as exc:
        logger.warning("LLM generate node error (%s); returning fallback", exc)
        return {
            "narrative": fallback_narrative,
            "recommended_product_ids": fallback_picks,
        }
