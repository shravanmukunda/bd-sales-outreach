"""Decision node. Picks retrieve, tool, or direct."""

from __future__ import annotations

from webknot_bd.graph.nodes.classify import FALLBACK_NOTE
from webknot_bd.graph.router import decide
from webknot_bd.graph.trace import trace_event
from webknot_bd.schemas.intent import Intent
from webknot_bd.schemas.state import GraphState


def decide_node(state: GraphState) -> dict:
    intent = Intent.model_validate(state["intent"])
    decision, fallback = decide(state["query"], intent)
    message = decision.reason
    if fallback:
        message = f"{FALLBACK_NOTE} {decision.reason}"
    return {
        "decision": decision.model_dump(mode="json"),
        "trace": [
            trace_event(
                "decide",
                message,
                route=decision.route.value,
                confidence=decision.confidence,
                fallback=fallback,
            )
        ],
    }
