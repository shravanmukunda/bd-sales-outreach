"""Intent classification node."""

from __future__ import annotations

from webknot_bd.graph.router import classify_intent
from webknot_bd.graph.trace import trace_event
from webknot_bd.schemas.state import GraphState


def classify_node(state: GraphState) -> dict:
    intent = classify_intent(state["query"])
    return {
        "intent": intent.model_dump(mode="json"),
        "trace": [
            trace_event(
                "classify",
                intent.rationale,
                intent=intent.intent.value,
                confidence=intent.confidence,
            )
        ],
    }
