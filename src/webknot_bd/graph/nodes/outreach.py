"""Draft node. Sample case studies are never cited as real client work."""

from __future__ import annotations

from webknot_bd.graph.llm import invoke_or_baseline
from webknot_bd.graph.trace import trace_event
from webknot_bd.memory.dedupe import should_skip
from webknot_bd.rag.loaders import as_bool
from webknot_bd.schemas.lead import LeadCard, MatchedService
from webknot_bd.schemas.outreach import DraftCopy, DraftStatus, OutreachDraft
from webknot_bd.schemas.state import GraphState
from webknot_bd.schemas.tool_io import CrmUpsertInput, JobNewsSearchOutput, PageFetchOutput, ScoreLeadInput
from webknot_bd.tools.crm import crm_upsert, lookup, refresh_contact
from webknot_bd.tools.lead_scorer import score_lead

FIT_GATE = 60
SIGN_OFF = "Webknot Technologies"
ASK = "Would you be open to a 20-minute call?"
_FORBIDDEN = ("$", "₹", "€", "%", "pricing", "per hour")

# One sentence each, with no digits, so a draft can name a service without inventing a metric.
SERVICE_BLURBS: dict[MatchedService, str] = {
    MatchedService.product_engineering: (
        "Product engineering is a small squad that designs, builds, and ships a product increment "
        "with the client team, from the agreed spec through release."
    ),
    MatchedService.dedicated_squads: (
        "Dedicated squads sit with an existing product team and carry a named slice of the roadmap "
        "from the backlog through release."
    ),
    MatchedService.mvp_build: (
        "An MVP build is an early version of the product, scoped to the public signal and shaped so "
        "a real user can try the workflow."
    ),
    MatchedService.react_frontend: (
        "React and frontend work covers the product interface and how it talks to the APIs the "
        "client already runs."
    ),
    MatchedService.backend_apis: (
        "Backend and API work covers the services behind the product, shaped around the workflow "
        "the public signal describes."
    ),
    MatchedService.mobile: (
        "Mobile work covers the phone surface of the product when the public signal shows people "
        "using that product away from a desk."
    ),
    MatchedService.ai_ml: (
        "AI and ML implementation adds a feature inside the product the company already ships, "
        "using data the client already owns."
    ),
}


def usable_case_study(chunks: list[dict]) -> str | None:
    """Return a non-sample case-study filename, or nothing."""
    for chunk in chunks:
        if as_bool(chunk.get("sample")):
            continue
        source = str(chunk.get("source", ""))
        if chunk.get("doc_type") == "web" and "case" in source.lower():
            return source
    return None


def word_count(text: str) -> int:
    return len(text.split())


def _names_subject(subject: str, company: str, signal: str) -> bool:
    lowered = subject.lower()
    return company.lower() in lowered or signal.lower() in lowered


def make_subject(company: str, signal: str, placeholder: bool) -> str:
    label = signal[:1].upper() + signal[1:] if signal else "Signal"
    candidates = [f"{label} at {company}", f"{company} {signal}"]
    chosen = next((item for item in candidates if _names_subject(item, company, signal) and len(item) <= 80), "")
    if not chosen:
        chosen = candidates[0][:80].rstrip()
    if placeholder:
        prefix = "[sample] "
        rest = chosen[: 80 - len(prefix)].rstrip()
        chosen = prefix + rest
    return chosen[:80]


def _assemble(parts: list[str]) -> str:
    return "\n\n".join([*parts, ASK, SIGN_OFF])


def baseline_copy(
    company: str,
    signal: str,
    evidence: str,
    matched_service: str,
    case_study: str | None,
    placeholder: bool,
) -> DraftCopy:
    """A draft that already meets the voice rules, with the model left off."""
    try:
        service = MatchedService(matched_service)
    except ValueError:
        service = MatchedService.product_engineering
    blurb = SERVICE_BLURBS[service]
    if evidence:
        opening = f"Hello {company} team, a public {signal} signal is listed at {evidence}."
    else:
        opening = f"Hello {company} team, a public {signal} signal is the reason for this note."
    tie = f"{blurb} This is the line that fits the {signal} signal at {company}."
    if case_study:
        case_line = f"The case study on file is {case_study}."
    else:
        case_line = "No client case study is attached to this note."
    pads = [
        blurb,
        f"The {signal} signal is the reason this note is specific to {company}.",
        f"The note stays on {service.value} because that line matches this {signal} signal.",
    ]
    parts = [opening, tie, case_line]
    index = 0
    while word_count(_assemble(parts)) < 120 and index < 30:
        added = False
        for candidate in (pads[index % len(pads)], f"The {signal} signal is why this note is specific."):
            trial = parts + [candidate]
            if word_count(_assemble(trial)) <= 160:
                parts.append(candidate)
                added = True
                break
        if not added:
            break
        index += 1
    hooks = [f"Public signal: {signal} ({evidence})"]
    if case_study:
        hooks.append(f"Case study on file: {case_study}")
    return DraftCopy(
        subject=make_subject(company, signal, placeholder),
        body=_assemble(parts),
        personalization_hooks=hooks,
        case_study_used=case_study,
    )


def _allowed_source(snippet: str, chunks: list[dict]) -> str:
    parts = [snippet]
    for chunk in chunks:
        if as_bool(chunk.get("sample")):
            continue
        parts.append(str(chunk.get("text", "")))
    return "\n".join(parts).lower()


def _sample_source(chunks: list[dict], source: str) -> bool:
    for chunk in chunks:
        if str(chunk.get("source", "")) == source and as_bool(chunk.get("sample")):
            return True
    return False


def accept_draft(
    copy: DraftCopy,
    *,
    company: str,
    signal: str,
    snippet: str,
    chunks: list[dict],
    placeholder: bool,
) -> None:
    """Raise when a draft breaks the voice rules. The helper treats that as a failed attempt."""
    if not 120 <= word_count(copy.body) <= 160:
        raise ValueError("body must be 120 to 160 words")
    if copy.body.count("20-minute call") != 1:
        raise ValueError("body must ask for a 20-minute call once")
    lines = [line.strip() for line in copy.body.splitlines() if line.strip()]
    if not lines or lines[-1] != SIGN_OFF:
        raise ValueError("body must end with the Webknot Technologies sign-off")
    subject = copy.subject.strip()
    if not 1 <= len(subject) <= 80:
        raise ValueError("subject must be 1 to 80 characters")
    if "webknot" in subject.lower():
        raise ValueError("subject must leave out the Webknot name")
    if not _names_subject(subject, company, signal):
        raise ValueError("subject must name the company or the signal")
    if placeholder and not subject.startswith("[sample]"):
        raise ValueError("a placeholder draft subject must start with [sample]")
    allowed = _allowed_source(snippet, chunks)
    haystack = f"{subject}\n{copy.body}".lower()
    for token in _FORBIDDEN:
        if token.lower() in haystack and token.lower() not in allowed:
            raise ValueError(f"draft contains {token} without support in the evidence")
    usable = usable_case_study(chunks)
    if copy.case_study_used:
        if _sample_source(chunks, copy.case_study_used) or copy.case_study_used != usable:
            raise ValueError("case study must be a non-sample file retrieved for this draft")


def _to_outreach(company: str, copy: DraftCopy) -> OutreachDraft:
    return OutreachDraft(
        company=company,
        subject=copy.subject,
        body=copy.body,
        personalization_hooks=list(copy.personalization_hooks),
        case_study_used=copy.case_study_used,
        status=DraftStatus.pending_approval,
    )


def build_draft(
    lead: LeadCard,
    snippet: str,
    chunks: list[dict],
    placeholder: bool,
) -> OutreachDraft:
    copy = baseline_copy(
        lead.company,
        lead.signal.value,
        lead.evidence_url,
        lead.matched_service.value,
        usable_case_study(chunks),
        placeholder,
    )
    accept_draft(
        copy,
        company=lead.company,
        signal=lead.signal.value,
        snippet=snippet,
        chunks=chunks,
        placeholder=placeholder,
    )
    return _to_outreach(lead.company, copy)


def _prompt(company: str, signal: str, evidence: str, service: str, snippet: str, case_study: str | None) -> str:
    services = ", ".join(item.value for item in MatchedService)
    case_rule = (
        f"case_study_used may be {case_study}."
        if case_study
        else "Set case_study_used to null. No non-sample case study was retrieved."
    )
    return (
        "Write one English outreach email.\n"
        f"Company: {company}\n"
        f"Signal: {signal}\n"
        f"Evidence URL: {evidence}\n"
        f"Matched service: {service}\n"
        f"Allowed services: {services}\n"
        f"Evidence snippet: {snippet}\n"
        "Body: 120 to 160 words. Ask once, using the phrase 20-minute call. "
        f"The last line is {SIGN_OFF}. No price and no invented metric.\n"
        "Subject: 1 to 80 characters, name the company or the signal, and do not write Webknot.\n"
        f"{case_rule}\n"
        "Return subject, body, personalization_hooks, and case_study_used."
    )


def compose_draft(
    company: str,
    signal: str,
    evidence: str,
    matched_service: str,
    snippet: str,
    chunks: list[dict],
    placeholder: bool,
) -> tuple[OutreachDraft, bool]:
    """Baseline draft, or one model attempt sequence when the chat model is on."""
    case_study = usable_case_study(chunks)

    def baseline() -> DraftCopy:
        copy = baseline_copy(company, signal, evidence, matched_service, case_study, placeholder)
        accept_draft(
            copy,
            company=company,
            signal=signal,
            snippet=snippet,
            chunks=chunks,
            placeholder=placeholder,
        )
        return copy

    def check(value: DraftCopy) -> None:
        accept_draft(
            DraftCopy.model_validate(value),
            company=company,
            signal=signal,
            snippet=snippet,
            chunks=chunks,
            placeholder=placeholder,
        )

    result, fallback = invoke_or_baseline(
        DraftCopy,
        _prompt(company, signal, evidence, matched_service, snippet, case_study),
        baseline,
        check=check,
    )
    return _to_outreach(company, DraftCopy.model_validate(result)), fallback


def _search_hits(tool_results: list[dict]) -> list:
    hits = []
    for item in tool_results:
        if item.get("tool") != "search_jobs_or_news":
            continue
        output = JobNewsSearchOutput.model_validate(item.get("output") or {})
        hits.extend(output.results)
    return hits


def _company_domains(tool_results: list[dict]) -> dict[str, str]:
    """Map a fetched URL to the company host, when the fetch found one."""
    domains: dict[str, str] = {}
    for item in tool_results:
        if item.get("tool") != "fetch_company_page":
            continue
        page = PageFetchOutput.model_validate(item.get("output") or {})
        if page.company_domain:
            domains[page.url] = page.company_domain
    return domains


def visible_leads(state: GraphState) -> list[dict]:
    """Scored cards from the search hits. Does not write a draft or a CRM row."""
    chunks = list(state.get("retrieved_chunks") or [])
    query = state.get("query") or ""
    tool_results = list(state.get("tool_results") or [])
    hits = _search_hits(tool_results)
    if not hits:
        return [LeadCard.model_validate(raw).model_dump(mode="json") for raw in state.get("leads") or []]
    search_output = next(
        (item.get("output") or {} for item in tool_results if item.get("tool") == "search_jobs_or_news"),
        {},
    )
    placeholder = bool(search_output.get("placeholder", True))
    cards = []
    for hit in hits:
        lead = score_lead(
            ScoreLeadInput(
                company=hit.company,
                signal=hit.signal,
                evidence_url=hit.url,
                snippet=hit.snippet,
                query=query,
                chunks=chunks,
                placeholder=placeholder,
            )
        ).lead
        cards.append(lead.model_dump(mode="json"))
    return cards


def _existing_row(company: str, domain: str) -> tuple[dict | None, str]:
    if domain:
        row = lookup(domain)
        if row is not None:
            return row, domain
    row = lookup(company)
    return row, company


def _draft_one(
    company: str,
    signal: str,
    evidence: str,
    snippet: str,
    chunks: list[dict],
    placeholder: bool,
    matched_service: str,
    drafts: list[dict],
    skipped: list[dict],
    domain: str = "",
) -> bool:
    """Store one pending draft. Returns whether the model reply was replaced by the baseline."""
    skip, reason = should_skip(company, domain)
    row, key = _existing_row(company, domain)
    if skip:
        skipped.append(
            {
                "company": company,
                "status": str(row["status"]) if row else "",
                "reason": reason,
            }
        )
        return False
    if row is not None:
        refresh_contact(key, note="draft created")
    else:
        crm_upsert(
            CrmUpsertInput(
                company=company,
                domain=domain,
                status="pending_approval",
                note="draft created",
            )
        )
    draft, fallback = compose_draft(
        company,
        signal,
        evidence,
        matched_service,
        snippet,
        chunks,
        placeholder,
    )
    drafts.append(draft.model_dump(mode="json"))
    return fallback


def outreach_node(state: GraphState) -> dict:
    chunks = list(state.get("retrieved_chunks") or [])
    case_study = usable_case_study(chunks)
    query = state.get("query") or ""
    tool_results = list(state.get("tool_results") or [])
    hits = _search_hits(tool_results)
    domains = _company_domains(tool_results)
    drafts: list[dict] = []
    skipped: list[dict] = []
    fell_back = False

    if hits:
        search_output = next(
            (
                item.get("output") or {}
                for item in tool_results
                if item.get("tool") == "search_jobs_or_news"
            ),
            {},
        )
        placeholder = bool(search_output.get("placeholder", True))
        scored = [
            (
                score_lead(
                    ScoreLeadInput(
                        company=hit.company,
                        signal=hit.signal,
                        evidence_url=hit.url,
                        snippet=hit.snippet,
                        query=query,
                        chunks=chunks,
                        placeholder=placeholder,
                    )
                ).lead,
                hit.snippet,
            )
            for hit in hits
        ]
        leads = [lead for lead, _snippet in scored]
        for lead, snippet in scored:
            if lead.fit_score < FIT_GATE:
                continue
            fell_back = _draft_one(
                lead.company,
                lead.signal.value,
                lead.evidence_url,
                snippet,
                chunks,
                placeholder,
                lead.matched_service.value,
                drafts,
                skipped,
                domains.get(lead.evidence_url, ""),
            ) or fell_back
    else:
        incoming = [LeadCard.model_validate(raw) for raw in state.get("leads") or []]
        if incoming:
            leads = incoming
            for lead in leads:
                if lead.fit_score < FIT_GATE:
                    continue
                fell_back = _draft_one(
                    lead.company,
                    lead.signal.value,
                    lead.evidence_url,
                    "",
                    chunks,
                    False,
                    lead.matched_service.value,
                    drafts,
                    skipped,
                    domains.get(lead.evidence_url, ""),
                ) or fell_back
        elif any(item.get("tool") == "search_jobs_or_news" for item in tool_results):
            # A search that returned nothing is not a company. Do not draft the query text.
            leads = []
        else:
            # A draft request with no search hits and no cards. There is no fit score to gate.
            leads = []
            fell_back = _draft_one(
                query or "Prospect",
                "outreach request",
                "",
                "",
                chunks,
                False,
                MatchedService.product_engineering.value,
                drafts,
                skipped,
            )

    message = f"Prepared {len(drafts)} draft(s) for approval."
    if fell_back:
        message = f"Baseline used after structured output failed twice. {message}"
    if skipped:
        names = ", ".join(item["company"] for item in skipped)
        message += f" Skipped {len(skipped)} because the 90-day window is still open: {names}."
    if case_study is None:
        message += " No approved case study was cited."

    return {
        "leads": [lead.model_dump(mode="json") for lead in leads],
        "drafts": drafts,
        "trace": [
            trace_event(
                "outreach",
                message,
                drafted=len(drafts),
                skipped=skipped,
                case_study_used=case_study,
                fallback=fell_back,
            )
        ],
    }
