"""Intent classification node."""

from __future__ import annotations

from webknot_bd.graph.router import classify_intent
from webknot_bd.graph.trace import trace_event
from webknot_bd.schemas.state import GraphState

FALLBACK_NOTE = "Baseline used after structured output failed twice."


def classify_node(state: GraphState) -> dict:
    intent, fallback = classify_intent(state["query"])
    message = intent.rationale
    if fallback:
        message = f"{FALLBACK_NOTE} {intent.rationale}"
    return {
        "intent": intent.model_dump(mode="json"),
        "trace": [
            trace_event(
                "classify",
                message,
                intent=intent.intent.value,
                confidence=intent.confidence,
                fallback=fallback,
            )
        ],
    }
