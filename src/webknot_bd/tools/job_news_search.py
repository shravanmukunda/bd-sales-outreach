"""Hiring, funding, and launch search through DuckDuckGo."""

from __future__ import annotations

import re

from webknot_bd.schemas.lead import Signal
from webknot_bd.schemas.tool_io import JobNewsHit, JobNewsSearchInput, JobNewsSearchOutput, LeadRequest
import webknot_bd.tools.web_search as web_search_module
from webknot_bd.tools.crm import normalize_domain
from webknot_bd.tools.hosts import host_of, url_allowed
from webknot_bd.tools.web_search import ATS_DOMAINS
from webknot_bd.tools.search_brief import baseline_brief, search_phrase

_AT = re.compile(r"\bat\b", re.IGNORECASE)
_HEADLINE = re.compile(r"\s+(?:raises|launches|acquires|announces)\b", re.IGNORECASE)
_LISTING = re.compile(r"\b(jobs?|vacancies|open roles|openings|careers|hiring)\b", re.IGNORECASE)
_NUMBERED_HEADING = re.compile(r"^\d+\s*[.)]\s+(.+)$")
_SEPARATORS = (" — ", " - ", " | ")
_SUFFIXES = ("private limited", "pvt", "ltd", "inc")
_SIGNAL_ORDER = (Signal.hiring, Signal.funding, Signal.launch)


def strip_legal_suffix(name: str) -> str:
    cleaned = name.strip(" .,")
    changed = True
    while cleaned and changed:
        changed = False
        lowered = cleaned.lower()
        for suffix in _SUFFIXES:
            if lowered.endswith(suffix):
                prefix = cleaned[: -len(suffix)].strip(" .,")
                if prefix:
                    cleaned = prefix
                    changed = True
                    break
    return cleaned


def _before_separator(text: str) -> str:
    for separator in _SEPARATORS:
        if separator in text:
            return text.split(separator, 1)[0].strip()
    return text.strip()


def company_name_from_title(title: str) -> str | None:
    """Read a company name from a result title. None when the title has no company."""
    text = " ".join(title.split())
    if not text:
        return None
    match = _AT.search(text)
    if match:
        head = text[match.end() :].strip()
    else:
        head = _before_separator(text)
        if head == text:
            return None
    head = _before_separator(head)
    headline = _HEADLINE.search(head)
    if headline:
        head = head[: headline.start()].strip()
    name = strip_legal_suffix(head)
    if not name or _LISTING.search(name):
        return None
    return name


def topic_phrase(query: str, location: str | None) -> str:
    """Drop the operator's count and filler so the search is a topic, not an instruction."""
    text = re.sub(r"\bfind\s+\d+\b", " ", query, flags=re.IGNORECASE)
    text = re.sub(r"\b(startups?|companies|company)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(in|the|a|an|for)\b", " ", text, flags=re.IGNORECASE)
    if location:
        text = re.sub(re.escape(location), " ", text, flags=re.IGNORECASE)
    words = [word for word in text.split() if word.lower() not in {"bangalore", "bengaluru"}]
    phrase = " ".join(words)
    if location:
        phrase = f"{phrase} {location}".strip()
    return " ".join(phrase.split()) or query.strip()


def company_name_from_url(url: str) -> str | None:
    """Read the company slug from a public Greenhouse, Lever, or Ashby job URL."""
    from urllib.parse import parse_qs, urlparse

    host = host_of(url)
    parsed = urlparse(url)
    path = [part for part in parsed.path.split("/") if part]
    slug = ""
    if host in {"jobs.lever.co", "jobs.ashbyhq.com"} and path:
        slug = path[0]
    elif host in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
        if path and path[0] not in {"embed", "jobs", "job"}:
            slug = path[0]
        else:
            slug = (parse_qs(parsed.query).get("for") or [""])[0]
    if not slug or slug.lower() in {"jobs", "job", "embed"}:
        return None
    name = strip_legal_suffix(" ".join(slug.replace("_", " ").replace("-", " ").split()))
    if not name or _LISTING.search(name):
        return None
    return " ".join(word[:1].upper() + word[1:] for word in name.split())


def hit_from_row(row: dict, signal: Signal) -> JobNewsHit | None:
    """Build a hit. Blocked hosts return None before the title is read as a company."""
    url = str(row.get("href") or row.get("url") or "")
    if not url_allowed(url):
        return None
    title = str(row.get("title") or "")
    company = company_name_from_url(url)
    if company is None:
        company = company_name_from_title(title)
    if company is None:
        company = company_name_from_title(str(row.get("body") or row.get("snippet") or ""))
    if company is None:
        return None
    return JobNewsHit(
        company=company,
        signal=signal,
        title=title or company,
        url=url,
        snippet=str(row.get("body") or row.get("snippet") or ""),
    )


def signals_for(signal: Signal | None) -> tuple[Signal, ...]:
    if signal is None:
        return _SIGNAL_ORDER
    return (signal,)


def ddg_query(query: str, signal: Signal, location: str | None) -> str:
    """Phrase from the baseline slots. Callers that already hold a brief use `search_phrase`."""
    brief = baseline_brief(query)
    if location:
        brief = brief.model_copy(update={"location": location})
    return search_phrase(brief, signal=signal)


def ats_query(payload: JobNewsSearchInput) -> str:
    """Role and place for a public job-board search. The provider limits the domains."""
    parts = [payload.role, payload.sector, "remote" if payload.remote else "", payload.location or ""]
    text = " ".join(part.strip() for part in parts if part and part.strip())
    return text or payload.query


def phrase_for(payload: JobNewsSearchInput, signal: Signal) -> str:
    """Use the stored brief when the tool node read the sentence. Otherwise parse the raw query."""
    if payload.use_brief:
        brief = LeadRequest(
            count=payload.max_results,
            location=payload.location,
            remote=payload.remote,
            role=payload.role,
            sector=payload.sector,
            signal=signal,
        )
        return search_phrase(brief, signal=signal)
    return ddg_query(payload.query, signal, payload.location)


def company_names_from_html(html: str) -> list[str]:
    """Read numbered headings such as '1 . PhonePe' from a public list article."""
    from bs4 import BeautifulSoup

    names: list[str] = []
    seen: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["h2", "h3"]):
        text = " ".join(tag.get_text(" ", strip=True).split())
        match = _NUMBERED_HEADING.match(text)
        if match is None:
            continue
        name = strip_legal_suffix(match.group(1).strip(" ."))
        if not name or _LISTING.search(name):
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def _fetch_html(url: str) -> str:
    import httpx

    response = httpx.get(
        url,
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; WebknotBD/1.0)"},
    )
    response.raise_for_status()
    return response.text[:1_000_000]


_LIST_RESULTS = 8


def list_queries(payload: JobNewsSearchInput) -> list[str]:
    """Two public-list phrases. The shorter 'top startups' phrase is the one that returns articles."""
    place = payload.location or ""
    sector = (payload.sector or "").strip()
    if not sector and "fintech" in payload.query.lower():
        sector = "fintech"
    if sector:
        phrases = (
            f"top {sector} startups",
            f"funded {sector} startups",
        )
    else:
        phrases = (
            "top startups",
            f"funded startups {topic_phrase(payload.query, payload.location)}",
        )
    queries: list[str] = []
    for phrase in phrases:
        text = " ".join(part for part in (phrase, place) if part).strip()
        if text and text not in queries:
            queries.append(text)
    return queries


def _hits_from_list_rows(rows: list[dict], payload: JobNewsSearchInput) -> list[JobNewsHit]:
    for row in rows:
        url = str(row.get("href") or row.get("url") or "")
        title = str(row.get("title") or "")
        if not url_allowed(url):
            continue
        lowered = f"{title} {url}".lower()
        if "fintech" in payload.query.lower() and "fintech" not in lowered and "startup" not in lowered:
            continue
        try:
            names = company_names_from_html(_fetch_html(url))
        except Exception:
            continue
        hits: list[JobNewsHit] = []
        seen: set[str] = set()
        for name in names:
            if len(hits) >= payload.max_results:
                break
            key = normalize_domain(name)
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                JobNewsHit(
                    company=name,
                    signal=Signal.funding,
                    title=title or name,
                    url=url,
                    snippet=(
                        f"{name} is named on a public list of funded startups. "
                        f"The page is {title or url}."
                    ),
                )
            )
        if hits:
            return hits
    return []


def _list_rows(query: str) -> list[dict]:
    """One search, and a second when the first comes back empty."""
    try:
        rows = web_search_module.search_text(query, _LIST_RESULTS)
    except Exception:
        rows = []
    if rows:
        return rows
    try:
        return web_search_module.search_text(query, _LIST_RESULTS)
    except Exception:
        return []


def companies_from_public_list(payload: JobNewsSearchInput) -> list[JobNewsHit]:
    """When hiring search keeps nothing, read company names from a public startup list."""
    for query in list_queries(payload):
        hits = _hits_from_list_rows(_list_rows(query), payload)
        if hits:
            return hits
    return []


def order_hits(rows: list[dict], *, signal: Signal | None, count: int) -> list[JobNewsHit]:
    """Keep allowed hits. A named signal is the only one used. Otherwise hiring, then funding, then launch."""
    kept: list[JobNewsHit] = []
    seen: set[str] = set()
    for group in signals_for(signal):
        for row in rows:
            row_signal = row.get("signal", group)
            if Signal(row_signal) is not group:
                continue
            if len(kept) >= count:
                return kept
            hit = hit_from_row(row, group)
            if hit is None:
                continue
            key = normalize_domain(hit.company)
            if key in seen:
                continue
            seen.add(key)
            kept.append(hit)
            if len(kept) >= count:
                return kept
    return kept


def search_jobs_or_news(payload: JobNewsSearchInput) -> JobNewsSearchOutput:
    """Hiring on Tavily checks public job boards first. An empty hiring search then tries startup lists."""
    kept: list[JobNewsHit] = []
    seen: set[str] = set()
    error = ""
    for signal in signals_for(payload.signal):
        if len(kept) >= payload.max_results:
            break
        searches: list[tuple[str, list[str] | None]] = []
        if signal is Signal.hiring and web_search_module.search_provider() == "tavily":
            searches.append((ats_query(payload), list(ATS_DOMAINS)))
        searches.append((phrase_for(payload, signal), None))
        for query, domains in searches:
            if len(kept) >= payload.max_results:
                break
            try:
                rows = web_search_module.search_text(
                    query,
                    payload.max_results,
                    include_domains=domains,
                )
            except Exception as exc:
                rows = []
                error = f"{type(exc).__name__}: {exc}"
            for row in rows:
                if len(kept) >= payload.max_results:
                    break
                hit = hit_from_row(row, signal)
                if hit is None:
                    continue
                key = normalize_domain(hit.company)
                if key in seen:
                    continue
                seen.add(key)
                kept.append(hit)
    if not kept and payload.signal in {None, Signal.hiring}:
        kept = companies_from_public_list(payload)
    if kept:
        error = ""
    return JobNewsSearchOutput(
        provider=web_search_module.search_provider(),
        query=payload.query,
        results=kept,
        placeholder=False,
        error=error,
    )
