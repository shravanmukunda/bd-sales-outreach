"""Read a find-leads sentence into slots, then build the DuckDuckGo phrase from those slots."""

from __future__ import annotations

import re

from webknot_bd.schemas.lead import Signal
from webknot_bd.schemas.tool_io import LeadRequest

_REMOTE = re.compile(r"\b(?:remote|wfh|work from home)\b", re.IGNORECASE)
_PLACE_IN = re.compile(
    r"\bin\s+([A-Za-z][\w'/-]*(?:\s+[A-Za-z][\w'/-]*){0,2})\s*$",
    re.IGNORECASE,
)
_SECTOR = re.compile(r"\b([A-Za-z][\w'+-]*)\s+(?:startups?|companies|firms)\b", re.IGNORECASE)
_SECTOR_SKIP = {
    "search",
    "me",
    "find",
    "for",
    "the",
    "a",
    "an",
    "some",
    "any",
    "get",
    "show",
    "which",
    "draft",
}
_FUNDING = re.compile(r"\b(?:funding|funded|raises|raised)\b", re.IGNORECASE)
_LAUNCH = re.compile(r"\b(?:launch|launches|launching)\b", re.IGNORECASE)
_HIRING_WORD = re.compile(r"\bhiring\b", re.IGNORECASE)
_HIRING_CUE = re.compile(
    r"\b(?:looking\s+for|need\s+engineers|open\s+roles|openings|devs|developers|engineers)\b",
    re.IGNORECASE,
)
_FILLER = {"the", "a", "an", "for", "of", "and", "me", "that", "with", "to"}


def expects_hiring(query: str) -> bool:
    """Hiring cues count unless the sentence is about funding or a launch."""
    if _HIRING_WORD.search(query):
        return True
    if _FUNDING.search(query) or _LAUNCH.search(query):
        return False
    return _HIRING_CUE.search(query) is not None


def baseline_brief(query: str) -> LeadRequest:
    """Offline reader. Handles the rubric sentence and the India and Australia examples."""
    match = re.search(r"\d+", query)
    count = 5
    if match:
        count = min(10, max(1, int(match.group())))
    location = _location(query)
    sector = _sector(query)
    return LeadRequest(
        count=count,
        location=location,
        remote=_REMOTE.search(query) is not None,
        role=_role(query, location, sector),
        sector=sector,
        signal=_signal(query),
    )


def search_phrase(brief: LeadRequest, *, signal: Signal | None = None) -> str:
    """Stable order: sector, signal word, role, remote, location, then the search suffix."""
    chosen = brief.signal if signal is None else signal
    if chosen is Signal.funding:
        suffix = "funding"
        signal_word = ""
    elif chosen is Signal.launch:
        suffix = "product launch"
        signal_word = ""
    elif chosen is Signal.hiring:
        suffix = "jobs"
        signal_word = "hiring"
    else:
        suffix = "jobs"
        signal_word = ""
    parts: list[str] = [brief.sector, signal_word, brief.role]
    if brief.remote:
        parts.append("remote")
    if brief.location:
        parts.append(brief.location)
    parts.append(suffix)
    return " ".join(part.strip() for part in parts if part and part.strip())


def _signal(query: str) -> Signal | None:
    if expects_hiring(query):
        return Signal.hiring
    funding = _FUNDING.search(query)
    launch = _LAUNCH.search(query)
    if funding and (launch is None or funding.start() <= launch.start()):
        return Signal.funding
    if launch:
        return Signal.launch
    return None


def _location(query: str) -> str | None:
    if re.search(r"\bbangalore\b", query, re.IGNORECASE):
        return "Bengaluru"
    if re.search(r"\bbengaluru\b", query, re.IGNORECASE):
        return "Bengaluru"
    match = _PLACE_IN.search(query.strip())
    if match is None:
        return None
    raw = match.group(1).strip()
    if raw.split()[0].lower() in {"remote", "a", "the", "an"}:
        return None
    words = []
    for part in raw.split():
        if part.isupper() or part[:1].isupper():
            words.append(part)
        else:
            words.append(part[:1].upper() + part[1:])
    return " ".join(words)


def _sector(query: str) -> str:
    for match in _SECTOR.finditer(query):
        word = match.group(1)
        if word.lower() in _SECTOR_SKIP:
            continue
        return word
    return ""


def _role(query: str, location: str | None, sector: str) -> str:
    cleaned = query
    cleaned = re.sub(r"\b(?:search\s+me|show\s+me|get\s+me)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bfind(?:\s+\d+)?\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\blooking\s+for\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bopen\s+roles\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bwork\s+from\s+home\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(?:remote|wfh|hiring|funding|funded|launch(?:ing|es)?|raises|raised)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    if location:
        cleaned = re.sub(re.escape(location), " ", cleaned, flags=re.IGNORECASE)
        if location == "Bengaluru":
            cleaned = re.sub(r"\bbangalore\b", " ", cleaned, flags=re.IGNORECASE)
    if sector:
        cleaned = re.sub(rf"\b{re.escape(sector)}\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bin\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:startups?|companies|company|firms|firm)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d+\b", " ", cleaned)
    words = [word for word in cleaned.split() if word.lower() not in _FILLER]
    while words and words[0].lower() in {"need", "needs"}:
        words.pop(0)
    while words and words[-1].lower() == "devs":
        words.pop()
    return " ".join(words)
