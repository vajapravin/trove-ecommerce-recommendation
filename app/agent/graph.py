"""LangGraph state graph definition.

Constructs the recommendation state machine graph:
  analyze_activity → decide_retrieve → retrieve → evaluate → [refine] → generate → END
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agent.nodes import (
    analyze_activity_node,
    decide_retrieve_node,
    evaluate_node,
    generate_node,
    refine_node,
    retrieve_node,
)
from app.agent.state import AgentState


def should_refine(state: AgentState) -> str:
    """Conditional edge routing based on evaluation outcome."""
    if state.get("evaluation_passed", True):
        return "generate"
    return "refine"


def build_recommendation_graph():
    """Build and compile the LangGraph recommendation state machine graph."""
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("analyze_activity", analyze_activity_node)
    builder.add_node("decide_retrieve", decide_retrieve_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("evaluate", evaluate_node)
    builder.add_node("refine", refine_node)
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
            "generate": "generate",
            "refine": "refine",
        },
    )

    builder.add_edge("refine", "retrieve")
    builder.add_edge("generate", END)

    return builder.compile()


recommendation_graph = build_recommendation_graph()
