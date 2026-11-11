"""Compile the LangGraph workflow."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from webknot_bd.config import configure_logging
from webknot_bd.graph.nodes import (
    classify_node,
    decide_node,
    guardrails_node,
    judge_node,
    outreach_node,
    respond_node,
    retrieve_node,
    tool_node,
)
from webknot_bd.graph.router import route_after_decision, route_after_retrieve
from webknot_bd.schemas.state import GraphState


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("classify", classify_node)
    graph.add_node("decide", decide_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("tool", tool_node)
    graph.add_node("outreach", outreach_node)
    graph.add_node("judge", judge_node)
    graph.add_node("guardrails", guardrails_node)
    graph.add_node("respond", respond_node)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "decide")
    graph.add_conditional_edges(
        "decide",
        route_after_decision,
        {"retrieve": "retrieve", "tool": "tool", "direct": "respond"},
    )
    graph.add_edge("tool", "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        route_after_retrieve,
        {"outreach": "outreach", "respond": "respond"},
    )
    graph.add_edge("outreach", "judge")
    graph.add_edge("judge", "guardrails")
    graph.add_edge("guardrails", "respond")
    graph.add_edge("respond", END)
    return graph.compile()


def run_query(query: str) -> dict:
    configure_logging()
    state = build_graph().invoke({"query": query, "trace": []})
    final = state.get("final_response")
    if not final:
        raise RuntimeError("Graph finished without a final response")
    return final
