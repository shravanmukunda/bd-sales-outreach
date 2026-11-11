"""Judge node. Scoring is intentionally deferred; the trace records that."""

from __future__ import annotations

from webknot_bd.graph.trace import trace_event
from webknot_bd.schemas.state import GraphState


def judge_node(state: GraphState) -> dict:
    drafts = state.get("drafts") or []
    return {
        "trace": [
            trace_event(
                "judge",
                "LLM-as-judge scoring is not implemented yet. Drafts were not changed.",
                relevance=None,
                no_hallucinated_claims=None,
                draft_count=len(drafts),
                status="not_scored",
            )
        ],
    }
