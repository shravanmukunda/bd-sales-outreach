"""Judge node. Notes go on the trace. The draft text stays as the writer left it."""

from __future__ import annotations

import re

from webknot_bd.graph.llm import invoke_or_baseline
from webknot_bd.graph.nodes.classify import FALLBACK_NOTE
from webknot_bd.graph.trace import trace_event
from webknot_bd.rag.loaders import as_bool
from webknot_bd.schemas.judge import JudgeNote, JudgeReport, Relevance
from webknot_bd.schemas.lead import LeadCard
from webknot_bd.schemas.outreach import OutreachDraft
from webknot_bd.schemas.state import GraphState

# The mandated ask is not a result figure. Phase 4 puts it in every baseline body.
_ASK = "20-minute"
_FIGURE = re.compile(r"\d{2,}")
_MONEY = ("$", "₹", "€", "%", "pricing", "per hour")

CLAIM_CASE = "Case study is sample data or missing from the retrieved chunks."
CLAIM_SAMPLE = "Body names the sample logistics story."
CLAIM_PRICE = "Price or metric is not in the evidence or the retrieved text."
CLAIM_FIGURE = "A figure in the draft is not in the evidence or the retrieved text."


def _lead_for(company: str, leads: list[LeadCard]) -> LeadCard | None:
    for lead in leads:
        if lead.company == company:
            return lead
    return None


def _snippet_for(company: str, evidence_url: str, tool_results: list[dict]) -> str:
    parts: list[str] = []
    for item in tool_results:
        output = item.get("output") or {}
        tool = item.get("tool")
        if tool == "search_jobs_or_news":
            for hit in output.get("results") or []:
                if hit.get("company") == company or (evidence_url and hit.get("url") == evidence_url):
                    parts.append(str(hit.get("snippet") or ""))
        elif tool == "fetch_company_page" and evidence_url and output.get("url") == evidence_url:
            parts.append(str(output.get("text_excerpt") or ""))
        elif tool == "web_search":
            for hit in output.get("results") or []:
                if evidence_url and hit.get("url") == evidence_url:
                    parts.append(str(hit.get("snippet") or ""))
    return "\n".join(parts)


def _chunk_text(chunk: dict) -> str:
    return str(chunk.get("text") or chunk.get("page_content") or "")


def _supported_text(chunks: list[dict], snippet: str) -> str:
    parts = [snippet]
    for chunk in chunks:
        if as_bool(chunk.get("sample")):
            continue
        parts.append(_chunk_text(chunk))
    return "\n".join(parts)


def _claims(
    draft: OutreachDraft,
    evidence_url: str,
    snippet: str,
    chunks: list[dict],
) -> list[str]:
    claims: list[str] = []
    if draft.case_study_used:
        cited = [
            chunk
            for chunk in chunks
            if str(chunk.get("source", "")) == draft.case_study_used and not as_bool(chunk.get("sample"))
        ]
        if not cited:
            claims.append(CLAIM_CASE)
    if "Parcel North" in draft.body:
        claims.append(CLAIM_SAMPLE)
    allowed = _supported_text(chunks, snippet)
    haystack = f"{draft.subject}\n{draft.body}"
    lowered_allowed = allowed.lower()
    if any(token.lower() in haystack.lower() and token.lower() not in lowered_allowed for token in _MONEY):
        claims.append(CLAIM_PRICE)
    figure_source = f"{evidence_url}\n{allowed}"
    scanned = draft.body.replace(_ASK, " ")
    if any(match.group() not in figure_source for match in _FIGURE.finditer(scanned)):
        claims.append(CLAIM_FIGURE)
    return claims


def _relevance(draft: OutreachDraft, lead: LeadCard | None) -> Relevance:
    if lead is None:
        return Relevance.weak
    company_in_body = lead.company.casefold() in draft.body.casefold()
    url_present = bool(lead.evidence_url) and (
        lead.evidence_url in draft.body or any(lead.evidence_url in hook for hook in draft.personalization_hooks)
    )
    if lead.fit_score >= 80 and company_in_body and url_present:
        return Relevance.strong
    if lead.fit_score >= 60 and company_in_body:
        return Relevance.adequate
    return Relevance.weak


def baseline_report(
    drafts: list[OutreachDraft],
    leads: list[LeadCard],
    chunks: list[dict],
    tool_results: list[dict],
) -> JudgeReport:
    notes: list[JudgeNote] = []
    for draft in drafts:
        lead = _lead_for(draft.company, leads)
        evidence_url = lead.evidence_url if lead else ""
        snippet = _snippet_for(draft.company, evidence_url, tool_results)
        notes.append(
            JudgeNote(
                company=draft.company,
                relevance=_relevance(draft, lead),
                unsupported_claims=_claims(draft, evidence_url, snippet, chunks),
            )
        )
    return JudgeReport(notes=notes)


def accept_report(report: JudgeReport, drafts: list[OutreachDraft]) -> None:
    """Raise when a model report does not line up with the drafts it scored."""
    if len(report.notes) != len(drafts):
        raise ValueError("note count must match the draft count")
    allowed = {item.value for item in Relevance}
    for note, draft in zip(report.notes, drafts, strict=True):
        if note.company != draft.company:
            raise ValueError("note companies must follow the draft order")
        label = note.relevance.value if isinstance(note.relevance, Relevance) else str(note.relevance)
        if label not in allowed:
            raise ValueError("relevance must be strong, adequate, or weak")
        if any(not claim.strip() for claim in note.unsupported_claims):
            raise ValueError("claim strings must be non-empty")


def _prompt(
    drafts: list[OutreachDraft],
    leads: list[LeadCard],
    chunks: list[dict],
    tool_results: list[dict],
) -> str:
    lines = [
        "Score each draft. Return one note per draft, in the same order, with the same company name.",
        "relevance is strong, adequate, or weak.",
        "unsupported_claims lists short strings that quote an unsupported phrase. Leave the list empty when nothing failed.",
        "Do not rewrite the draft.",
    ]
    for draft in drafts:
        lead = _lead_for(draft.company, leads)
        evidence_url = lead.evidence_url if lead else ""
        lines.append(f"Company: {draft.company}")
        lines.append(f"Subject: {draft.subject}")
        lines.append(f"Body: {draft.body}")
        lines.append(f"Hooks: {list(draft.personalization_hooks)}")
        lines.append(f"case_study_used: {draft.case_study_used}")
        lines.append(f"Evidence URL: {evidence_url}")
        lines.append(f"Snippet: {_snippet_for(draft.company, evidence_url, tool_results)}")
        if lead is not None:
            lines.append(f"Fit: {lead.fit_score}")
    for chunk in chunks:
        lines.append(
            f"Chunk source={chunk.get('source')} sample={as_bool(chunk.get('sample'))} text={_chunk_text(chunk)}"
        )
    return "\n".join(lines)


def judge_node(state: GraphState) -> dict:
    drafts = [OutreachDraft.model_validate(raw) for raw in state.get("drafts") or []]
    leads = [LeadCard.model_validate(raw) for raw in state.get("leads") or []]
    chunks = list(state.get("retrieved_chunks") or [])
    tool_results = list(state.get("tool_results") or [])

    def baseline() -> JudgeReport:
        report = baseline_report(drafts, leads, chunks, tool_results)
        accept_report(report, drafts)
        return report

    def check(value: JudgeReport) -> None:
        accept_report(JudgeReport.model_validate(value), drafts)

    report, fallback = invoke_or_baseline(
        JudgeReport,
        _prompt(drafts, leads, chunks, tool_results),
        baseline,
        check=check,
    )
    notes = JudgeReport.model_validate(report).notes
    message = f"Scored {len(notes)} draft(s). Drafts were not changed."
    if fallback:
        message = f"{FALLBACK_NOTE} {message}"
    return {
        "trace": [
            trace_event(
                "judge",
                message,
                status="scored",
                fallback=fallback,
                notes=[note.model_dump(mode="json") for note in notes],
                draft_count=len(drafts),
            )
        ],
    }
