"""Model reader for a find-leads sentence. The baseline is used when the chat model is off or fails."""

from __future__ import annotations

import re

from pydantic import BaseModel

from webknot_bd.graph.llm import invoke_or_baseline
from webknot_bd.schemas.lead import Signal
from webknot_bd.schemas.tool_io import LeadRequest
from webknot_bd.tools.search_brief import baseline_brief, expects_hiring

_INSTRUCTION = re.compile(r"\b(?:search\s+me|find\s+\d+)\b", re.IGNORECASE)
_REMOTE = re.compile(r"\b(?:remote|wfh|work from home)\b", re.IGNORECASE)


def accept_brief(query: str, brief: LeadRequest) -> None:
    """Reject a reply that copies the sentence into a slot or invents remote or the signal."""
    for label, field in (("location", brief.location or ""), ("role", brief.role)):
        if field and (_repeats_query(field, query) or _INSTRUCTION.search(field)):
            raise ValueError(f"{label} repeats the request")
    if brief.remote and _REMOTE.search(query) is None:
        raise ValueError("remote was not in the sentence")
    if expects_hiring(query) and brief.signal is not Signal.hiring:
        raise ValueError("signal should be hiring")


def read_search_brief(query: str) -> tuple[LeadRequest, bool]:
    """Return the brief and whether the baseline replaced the model."""

    def check(value: BaseModel) -> None:
        if not isinstance(value, LeadRequest):
            value = LeadRequest.model_validate(value)
        accept_brief(query, value)

    result, fallback = invoke_or_baseline(
        LeadRequest,
        _prompt(query),
        lambda: baseline_brief(query),
        check=check,
    )
    if isinstance(result, LeadRequest):
        return result, fallback
    return LeadRequest.model_validate(result), fallback


def _prompt(query: str) -> str:
    return (
        "Read the business-development request into slots. "
        "Do not write a search-engine query. Do not copy the whole sentence into any field.\n"
        "count: integer 1 to 10, default 5.\n"
        "location: a place name only, or null. Bengaluru and Bangalore are Bengaluru.\n"
        "remote: true only when the sentence says remote, WFH, or work from home.\n"
        "role: a short skill phrase such as 'Java Spring Boot' or 'React developers'. "
        "Leave it empty when the sentence names no skill. Drop filler such as 'search me'.\n"
        "sector: a short industry word such as fintech, or empty.\n"
        "signal: hiring, funding, or launch. "
        "Use hiring for hiring, looking for developers, need engineers, open roles, devs, developers, or engineers, "
        "unless the sentence is about funding or a launch.\n"
        "Examples:\n"
        "- Find 5 fintech startups hiring React developers in Bengaluru "
        "-> count 5, sector fintech, role React developers, location Bengaluru, remote false, signal hiring.\n"
        "- Search me companies hiring Java Spring Boot devs in India "
        "-> count 5, role Java Spring Boot, location India, remote false, signal hiring.\n"
        "- Search me startups looking for remote devs in Australia "
        "-> count 5, location Australia, remote true, signal hiring.\n"
        f"Request: {query}"
    )


def _repeats_query(field: str, query: str) -> bool:
    field_norm = " ".join(field.casefold().split())
    query_norm = " ".join(query.casefold().split())
    return field_norm == query_norm or query_norm in field_norm
