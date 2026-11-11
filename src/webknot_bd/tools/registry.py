"""Tool registry. The tool node calls these by name with structured inputs."""

from __future__ import annotations

from collections.abc import Callable

from webknot_bd.tools.crm import crm_upsert
from webknot_bd.tools.job_news_search import search_jobs_or_news
from webknot_bd.tools.lead_scorer import score_lead
from webknot_bd.tools.page_fetch import fetch_company_page
from webknot_bd.tools.web_search import web_search

TOOL_REGISTRY: dict[str, Callable] = {
    "web_search": web_search,
    "fetch_company_page": fetch_company_page,
    "search_jobs_or_news": search_jobs_or_news,
    "score_lead": score_lead,
    "crm_upsert": crm_upsert,
}


def run_tool(name: str, payload):
    try:
        tool = TOOL_REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(sorted(TOOL_REGISTRY))
        raise KeyError(f"Unknown tool {name!r}. Known tools: {known}") from exc
    return tool(payload)
