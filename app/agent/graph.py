"""LangGraph state graph definition.

Constructs the recommendation state machine graph with two-stage candidate retrieval and re-ranking:
  analyze_activity → decide_retrieve → retrieve → evaluate → [refine] → rerank → generate → END
"""
from __future__ import annotations

import os
from langgraph.graph import END, StateGraph

from app.agent.nodes import (
    analyze_activity_node,
    decide_retrieve_node,
    evaluate_node,
    generate_node,
    refine_node,
    rerank_node,
    retrieve_node,
)
from app.agent.state import AgentState
from app.config import get_settings


def should_refine(state: AgentState) -> str:
    """Conditional edge routing based on evaluation outcome."""
    if state.get("evaluation_passed", True):
        return "rerank"
    return "refine"


def setup_langsmith_tracing():
    """Configure LangSmith environment variables if enabled in config."""
    settings = get_settings()
    if settings.LANGSMITH_TRACING and settings.LANGSMITH_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT or "trove"
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT or "trove"


def build_recommendation_graph():
    """Build and compile the LangGraph recommendation state machine graph."""
    setup_langsmith_tracing()

    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("analyze_activity", analyze_activity_node)
    builder.add_node("decide_retrieve", decide_retrieve_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("evaluate", evaluate_node)
    builder.add_node("refine", refine_node)
    builder.add_node("rerank", rerank_node)
    builder.add_node("generate", generate_node)

    # Set flow & edges
    builder.set_entry_point("analyze_activity")
    builder.add_edge("analyze_activity", "decide_retrieve")
    builder.add_edge("decide_retrieve", "retrieve")
    builder.add_edge("retrieve", "evaluate")

    builder.add_conditional_edges(
        "evaluate",
        should_refine,
        {
            "rerank": "rerank",
            "refine": "refine",
        },
    )

    builder.add_edge("refine", "retrieve")
    builder.add_edge("rerank", "generate")
    builder.add_edge("generate", END)

    return builder.compile()


recommendation_graph = build_recommendation_graph()
