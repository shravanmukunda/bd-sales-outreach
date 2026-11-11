"""Draft node. Sample case studies are never cited as real client work."""

from __future__ import annotations

from webknot_bd.graph.trace import trace_event
from webknot_bd.memory.dedupe import should_skip
from webknot_bd.rag.loaders import as_bool
from webknot_bd.schemas.lead import LeadCard
from webknot_bd.schemas.outreach import DraftStatus, OutreachDraft
from webknot_bd.schemas.state import GraphState
from webknot_bd.schemas.tool_io import CrmUpsertInput
from webknot_bd.tools.crm import crm_upsert


def usable_case_study(chunks: list[dict]) -> str | None:
    """Return a non-sample case-study filename, or nothing."""
    for chunk in chunks:
        if as_bool(chunk.get("sample")):
            continue
        source = str(chunk.get("source", ""))
        if chunk.get("doc_type") == "web" and "case" in source.lower():
            return source
    return None


def build_draft(
    company: str,
    signal: str,
    evidence: str,
    case_study: str | None,
) -> OutreachDraft:
    hooks = [f"Public signal: {signal}"]
    if case_study:
        hooks.append(f"Case study on file: {case_study}")
    body = (
        f"Hello {company} team,\n\n"
        "This is a placeholder draft. The outreach writer is not built yet, "
        "so this note does not claim any Webknot client results.\n\n"
    )
    if evidence:
        body += f"Public signal ({signal}): {evidence}\n"
    else:
        body += f"Request: {signal}\n"
    if case_study:
        body += f"\nApproved case study to consider: {case_study}\n"
    else:
        body += (
            "\nNo approved Webknot case study was attached. "
            "Sample seed files are not cited as client work.\n"
        )
    subject = f"{signal.capitalize()} at {company}" if evidence else "Outreach draft pending approval"
    return OutreachDraft(
        company=company,
        subject=subject[:140],
        body=body,
        personalization_hooks=hooks,
        case_study_used=case_study,
        status=DraftStatus.pending_approval,
    )


def outreach_node(state: GraphState) -> dict:
    case_study = usable_case_study(state.get("retrieved_chunks") or [])
    drafts: list[dict] = []
    skipped: list[dict] = []
    lead_rows = state.get("leads") or []

    if lead_rows:
        targets = []
        for raw in lead_rows:
            lead = LeadCard.model_validate(raw)
            targets.append((lead.company, lead.signal.value, lead.evidence_url))
    else:
        targets = [(state.get("query") or "Prospect", "outreach request", "")]

    for company, signal, evidence in targets:
        skip, status = should_skip(company)
        if skip:
            skipped.append({"company": company, "status": status})
            continue
        crm_upsert(CrmUpsertInput(company=company, status="pending_approval", note="draft created"))
        drafts.append(build_draft(company, signal, evidence, case_study).model_dump(mode="json"))

    message = f"Prepared {len(drafts)} draft(s) for approval."
    if skipped:
        names = ", ".join(item["company"] for item in skipped)
        message += f" Skipped {len(skipped)} already in the CRM: {names}."
    if case_study is None:
        message += " No approved case study was cited."

    return {
        "drafts": drafts,
        "trace": [
            trace_event(
                "outreach",
                message,
                drafted=len(drafts),
                skipped=skipped,
                case_study_used=case_study,
            )
        ],
    }
