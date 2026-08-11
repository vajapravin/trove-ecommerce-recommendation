"""LangGraph workflow node implementations.

Each function takes `AgentState` and returns updated state dict keys.
Nodes:
  1. analyze_activity: Summarizes behavior into query & optional metadata filters.
  2. decide_retrieve: Validates search criteria before retrieval.
  3. retrieve: Queries Chroma vector store for a top-15 shortlist with metadata filters.
  4. evaluate: Checks if shortlist meets quality & relevance threshold.
  5. refine: Broadens/adjusts query parameters if evaluation fails.
  6. rerank: Re-ranks top-15 shortlist candidates down to top-5 picks using Mesh LLM.
  7. generate: Produces persuasive narrative + product picks grounded in Chroma IDs.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.agent.state import AgentState
from app.config import get_settings
from app.mesh_client import chat_complete
from app.vector_store import query_products

logger = logging.getLogger("trove.agent.nodes")


def analyze_activity_node(state: AgentState) -> Dict[str, Any]:
    """Node 1: Extract core search query and category/level preferences from activity summary."""
    summary_text = state.get("formatted_summary", "")
    summary_dict = state.get("activity_summary", {})

    search_queries = summary_dict.get("search_queries", [])
    categories = summary_dict.get("interacted_categories", [])
    levels = summary_dict.get("interacted_levels", [])
    viewed_titles = summary_dict.get("viewed_product_titles", [])

    default_query = search_queries[0] if search_queries else (
        " ".join(viewed_titles[:2]) if viewed_titles else "trending e-commerce products"
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
        '  "category": string or null (one primary category if evident, e.g. "AI & Agents", "Backend", "Data", "DevOps", "Interview Prep"),\n'
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
        query = "best recommended products"
    return {"extracted_query": query}


def retrieve_node(state: AgentState) -> Dict[str, Any]:
    """Node 3: Semantic search via Chroma vector store returning top-15 shortlist candidates."""
    query = state.get("extracted_query", "products")
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

    return {"shortlist": hits}


def evaluate_node(state: AgentState) -> Dict[str, Any]:
    """Node 4: Check if retrieval yields sufficient candidate products."""
    hits = state.get("shortlist", [])
    refine_count = state.get("refine_count", 0)

    passed = len(hits) > 0 or refine_count >= 2
    return {"evaluation_passed": passed}


def refine_node(state: AgentState) -> Dict[str, Any]:
    """Node 5: Broaden search criteria if evaluation failed."""
    refine_count = state.get("refine_count", 0) + 1
    return {
        "refine_count": refine_count,
        "category_filter": None,
        "level_filter": None,
    }


def rerank_node(state: AgentState) -> Dict[str, Any]:
    """Node 6: Re-rank top-15 shortlist down to top-5 picks using Mesh LLM."""
    shortlist = state.get("shortlist", [])
    summary_text = state.get("formatted_summary", "")
    query = state.get("extracted_query", "")

    if not shortlist:
        return {"reranked_products": []}

    # Sort shortlist by Chroma distance (ascending) as baseline
    sorted_shortlist = sorted(shortlist, key=lambda x: x.get("distance", 0.0))
    default_top5 = sorted_shortlist[:5]

    settings = get_settings()
    if not settings.MESH_API_KEY:
        logger.info("MESH_API_KEY not set; using vector distance for top-5 shortlist re-ranking")
        return {"reranked_products": default_top5}

    candidates_formatted = "\n".join(
        f"- ID {h['product_id']}: '{h['title']}' (Category: {h['category']}, Level: {h['level']}) — {h.get('tags', '')}"
        for h in shortlist
    )

    system_prompt = (
        "You are an expert e-commerce re-ranking system. Re-rank the provided candidate products "
        "based on how strongly they match the user's specific intent and activity summary.\n"
        "Return a JSON object with:\n"
        '  "ranked_product_ids": list of integers (the top 5 product IDs in descending order of relevance).\n'
        "Output ONLY valid JSON."
    )

    user_prompt = (
        f"User Activity Summary:\n{summary_text}\n\n"
        f"Inferred Search Query: '{query}'\n\n"
        f"Candidates (Top 15 retrieved):\n{candidates_formatted}\n"
    )

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
        ranked_ids = parsed.get("ranked_product_ids", [])
        shortlist_map = {h["product_id"]: h for h in shortlist}

        reranked = [shortlist_map[pid] for pid in ranked_ids if pid in shortlist_map]
        if not reranked:
            reranked = default_top5
        elif len(reranked) < 3:
            for item in default_top5:
                if item not in reranked:
                    reranked.append(item)

        return {"reranked_products": reranked[:5]}
    except Exception as exc:
        logger.warning("LLM rerank node error (%s); falling back to vector distance top-5", exc)
        return {"reranked_products": default_top5}


def generate_node(state: AgentState) -> Dict[str, Any]:
    """Node 7: Write persuasive personalized narrative & pick products grounded in re-ranked candidate IDs."""
    reranked = state.get("reranked_products", [])
    if not reranked:
        reranked = state.get("shortlist", [])[:5]

    summary_text = state.get("formatted_summary", "")
    settings = get_settings()

    if not reranked:
        return {
            "narrative": "We noticed your recent visits! Browse our full catalog to discover great learning paths.",
            "recommended_product_ids": [],
        }

    candidate_ids = [h["product_id"] for h in reranked]
    candidate_summary = "\n".join(
        f"- ID {h['product_id']}: '{h['title']}' | Category: {h['category']} | Level: {h['level']} | Price: ${h['price']:.2f}"
        for h in reranked
    )

    fallback_picks = candidate_ids[:3]
    fallback_narrative = (
        f"Based on your recent interest in {reranked[0]['category']} and related items, "
        f"we have selected top products tailored for your shopping interests. Explore these recommendations below!"
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
        f"Candidates (Re-ranked for shopper):\n{candidate_summary}\n"
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
