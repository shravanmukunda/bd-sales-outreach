"""Decision node. Picks retrieve, tool, or direct."""

from __future__ import annotations

from webknot_bd.graph.router import decide
from webknot_bd.graph.trace import trace_event
from webknot_bd.schemas.intent import Intent
from webknot_bd.schemas.state import GraphState


def decide_node(state: GraphState) -> dict:
    intent = Intent.model_validate(state["intent"])
    decision = decide(state["query"], intent)
    return {
        "decision": decision.model_dump(mode="json"),
        "trace": [
            trace_event(
                "decide",
                decision.reason,
                route=decision.route.value,
                confidence=decision.confidence,
            )
        ],
    }
