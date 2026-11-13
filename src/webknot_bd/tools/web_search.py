"""Public web search. Tavily when a key is set, otherwise DuckDuckGo."""

from __future__ import annotations

from webknot_bd.config import settings
from webknot_bd.schemas.tool_io import SearchHit, WebSearchInput, WebSearchOutput
from webknot_bd.tools.hosts import url_allowed

TIMEOUT_SECONDS = 15
TAVILY_URL = "https://api.tavily.com/search"
# Public job posts. LinkedIn, Indeed, and Naukri stay on the blocklist.
ATS_DOMAINS = (
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
)


def search_provider() -> str:
    """Tavily when `TAVILY_API_KEY` is set. Tests leave the key empty and stay on DuckDuckGo."""
    if settings.tavily_api_key.strip():
        return "tavily"
    return "duckduckgo"


def duckduckgo_text(query: str, max_results: int) -> list[dict]:
    """Return DuckDuckGo text rows. An empty result set is an empty list."""
    from ddgs import DDGS

    client = DDGS(timeout=TIMEOUT_SECONDS)
    try:
        return list(client.text(query, max_results=max_results))
    except Exception as exc:
        if "No results found" in str(exc):
            return []
        raise


def tavily_text(
    query: str,
    max_results: int,
    *,
    include_domains: list[str] | None = None,
) -> list[dict]:
    """Return Tavily rows in the same shape as DuckDuckGo text rows."""
    import httpx

    key = settings.tavily_api_key.strip()
    if not key:
        raise RuntimeError("TAVILY_API_KEY is empty")
    body: dict = {
        "query": query,
        "max_results": max(1, min(max_results, 10)),
        "search_depth": "basic",
        "include_answer": False,
    }
    if include_domains:
        body["include_domains"] = include_domains
    response = httpx.post(
        TAVILY_URL,
        json=body,
        headers={"Authorization": f"Bearer {key}"},
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Tavily HTTP {response.status_code}")
    rows = []
    for item in response.json().get("results") or []:
        rows.append(
            {
                "title": str(item.get("title") or ""),
                "href": str(item.get("url") or ""),
                "body": str(item.get("content") or ""),
            }
        )
    return rows


def search_text(
    query: str,
    max_results: int,
    *,
    include_domains: list[str] | None = None,
) -> list[dict]:
    """One text search on the active provider."""
    if search_provider() == "tavily":
        return tavily_text(query, max_results, include_domains=include_domains)
    return duckduckgo_text(query, max_results)


def _row_url(row: dict) -> str:
    return str(row.get("href") or row.get("url") or "")


def _row_snippet(row: dict) -> str:
    return str(row.get("body") or row.get("snippet") or "")


def web_search(payload: WebSearchInput) -> WebSearchOutput:
    try:
        rows = search_text(payload.query, payload.max_results)
    except Exception as exc:
        return WebSearchOutput(
            provider=search_provider(),
            query=payload.query,
            results=[],
            placeholder=False,
            error=f"{type(exc).__name__}: {exc}",
        )
    hits: list[SearchHit] = []
    for row in rows:
        url = _row_url(row)
        if not url_allowed(url):
            continue
        hits.append(
            SearchHit(
                title=str(row.get("title") or ""),
                url=url,
                snippet=_row_snippet(row),
            )
        )
        if len(hits) >= payload.max_results:
            break
    return WebSearchOutput(
        provider=search_provider(),
        query=payload.query,
        results=hits,
        placeholder=False,
    )
