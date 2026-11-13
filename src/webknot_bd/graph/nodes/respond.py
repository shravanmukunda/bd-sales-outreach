"""Response node. Assembles the schema-valid payload the UI renders."""

from __future__ import annotations

from webknot_bd.graph.trace import trace_event
from webknot_bd.rag.retriever import chroma_ready
from webknot_bd.schemas.decision import Decision
from webknot_bd.schemas.intent import Intent
from webknot_bd.schemas.lead import LeadCard
from webknot_bd.schemas.outreach import OutreachDraft
from webknot_bd.schemas.response import FinalResponse, TraceEvent
from webknot_bd.schemas.state import GraphState

DIRECT_SUBJECT_LINE = (
    "A good cold email subject line is specific, short, and tied to a public signal "
    "the reader will recognize, such as a role they are hiring for, a launch, or a funding round. "
    "Name that signal. Leave Webknot's name out of the subject. "
    "Skip clickbait, fake familiarity, and anything you cannot point to on a public page."
)


def _chunk_lines(chunks: list[dict]) -> str:
    lines = []
    for chunk in chunks[:4]:
        label = str(chunk.get("source") or "document")
        if chunk.get("sample"):
            label += " (sample seed, not a real engagement)"
        snippet = " ".join(str(chunk.get("text", "")).split())[:180]
        lines.append(f"- {label}: {snippet}")
    return "Retrieved context:\n" + "\n".join(lines)


def _empty_retrieval(industry: str | None, service: str | None, store_ready: bool) -> str:
    parts = [f"industry={industry}" if industry else "", f"service={service}" if service else ""]
    active = ", ".join(part for part in parts if part)
    extra = f" Filter: {active}." if active else ""
    if store_ready:
        return (
            "No chunks matched."
            + extra
            + " The vector store is already built. Add a document tagged with that industry or service if this filter should hit."
        )
    return (
        "No Webknot chunks were retrieved."
        + extra
        + " Run `python scripts/ingest.py` after Ollama is up."
    )


def _answer(
    route: str,
    query: str,
    leads: list[LeadCard],
    drafts: list[OutreachDraft],
    chunks: list[dict],
    industry: str | None,
    service: str | None,
    store_ready: bool,
    *,
    skipped: list[dict],
    placeholder: bool,
) -> str:
    if route == "direct":
        lowered = query.lower()
        if "subject line" in lowered or "what makes a good" in lowered:
            return DIRECT_SUBJECT_LINE
        return "This question can be answered directly. No documents were retrieved and no tools ran."

    parts: list[str] = []
    if route == "tool" and placeholder:
        parts.append(
            f"Prepared {len(leads)} placeholder lead card(s) and {len(drafts)} draft(s) "
            "waiting for approval. No email was sent. Live company search is not connected, "
            "so these cards are fictional example.com placeholders, not real startups."
        )
    elif route == "tool":
        parts.append(
            f"Prepared {len(leads)} lead card(s) from public search and {len(drafts)} draft(s) "
            "waiting for approval. No email was sent."
        )
    else:
        parts.append(
            f"Used the Webknot knowledge base. {len(chunks)} chunk(s) retrieved. No email was sent."
        )
        if "case study" in query.lower():
            parts.append("The corpus has no real case study yet.")
    if drafts:
        parts.append(f"{len(drafts)} draft(s) are pending approval.")
    elif route == "tool" and leads and skipped:
        parts.append("Every company is inside the 90-day window, so no new draft was created.")
    elif route == "tool" and leads:
        parts.append("No lead reached a fit score of 60, so no draft was created.")
    if chunks:
        parts.append(_chunk_lines(chunks))
    elif route in {"retrieve", "tool"}:
        parts.append(_empty_retrieval(industry, service, store_ready))
    return "\n\n".join(parts)


def respond_node(state: GraphState) -> dict:
    decision_data = state.get("decision") or {}
    route = decision_data.get("route", "direct")
    leads = [LeadCard.model_validate(item) for item in state.get("leads") or []]
    drafts = [OutreachDraft.model_validate(item) for item in state.get("drafts") or []]
    chunks = list(state.get("retrieved_chunks") or [])
    skipped: list[dict] = []
    placeholder = False
    for event in state.get("trace") or []:
        if event.get("node") == "outreach":
            skipped = list((event.get("data") or {}).get("skipped") or [])
        if event.get("node") == "tool":
            placeholder = bool((event.get("data") or {}).get("placeholder"))
    answer = _answer(
        route,
        state.get("query", ""),
        leads,
        drafts,
        chunks,
        state.get("industry"),
        state.get("service"),
        chroma_ready(),
        skipped=skipped,
        placeholder=placeholder,
    )
    event = trace_event("respond", "Built the final response. Nothing was sent.", route=route)
    trace = list(state.get("trace") or []) + [event]
    final = FinalResponse(
        answer=answer,
        leads=leads,
        drafts=drafts,
        trace=[TraceEvent.model_validate(item) for item in trace],
        decision=Decision.model_validate(decision_data) if decision_data else None,
        intent=Intent.model_validate(state["intent"]) if state.get("intent") else None,
    )
    return {
        "trace": [event],
        "final_response": final.model_dump(mode="json"),
    }
