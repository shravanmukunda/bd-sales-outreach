"""Deterministic lead scorer. Picks one allowed service and a fit score from the evidence."""

from __future__ import annotations

import re

from webknot_bd.rag.retriever import detect_industry
from webknot_bd.schemas.lead import LeadCard, MatchedService
from webknot_bd.schemas.tool_io import ScoreLeadInput, ScoreLeadOutput

# First matching pattern wins. Patterns are case-insensitive word boundaries.
_SERVICE_RULES: tuple[tuple[re.Pattern[str], MatchedService], ...] = (
    (re.compile(r"\b(?:react|frontend|front-end|front end)\b", re.I), MatchedService.react_frontend),
    (re.compile(r"\b(?:ios|android|mobile)\b", re.I), MatchedService.mobile),
    (re.compile(r"\b(?:api|backend|back-end|node)\b", re.I), MatchedService.backend_apis),
    (re.compile(r"\bmvp\b", re.I), MatchedService.mvp_build),
    (re.compile(r"\b(?:dedicated|squad)\b", re.I), MatchedService.dedicated_squads),
    (re.compile(r"\b(?:ai|ml|machine learning)\b", re.I), MatchedService.ai_ml),
)


def choose_service(text: str) -> tuple[MatchedService, bool]:
    """Return the service line and whether a keyword in `text` selected it."""
    for pattern, service in _SERVICE_RULES:
        if pattern.search(text):
            return service, True
    return MatchedService.product_engineering, False


def _chunk_supports(chunks: list[dict], query: str, matched: MatchedService) -> bool:
    industry = detect_industry(query)
    for chunk in chunks:
        chunk_industry = str(chunk.get("industry", "")).lower()
        chunk_service = str(chunk.get("service", "")).lower()
        if industry and chunk_industry == industry:
            return True
        if chunk_service == matched.value.lower():
            return True
    return False


def score_lead(payload: ScoreLeadInput) -> ScoreLeadOutput:
    text = f"{payload.query} {payload.snippet}"
    matched, keyword_hit = choose_service(text)
    score = 0
    if payload.evidence_url.startswith(("http://", "https://")):
        score += 50
    if keyword_hit:
        score += 20
    if _chunk_supports(payload.chunks, payload.query, matched):
        score += 15
    if payload.signal.value == "hiring":
        score += 10
    score = min(score, 100)
    noted = payload.snippet or payload.signal.value
    if payload.placeholder:
        prefix = (
            "PLACEHOLDER fit score. The scorer does not call a model yet, "
            "and this number is not a judgment about a real company. "
        )
    else:
        prefix = "Fit score from the public signal and the retrieved Webknot text. "
    lead = LeadCard(
        company=payload.company,
        signal=payload.signal,
        evidence_url=payload.evidence_url,
        fit_score=score,
        matched_service=matched,
        reasoning=f"{prefix}Signal noted: {noted}. Matched service: {matched.value}.",
    )
    return ScoreLeadOutput(lead=lead, placeholder=payload.placeholder)
