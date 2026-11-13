"""Tool node. Calls registered tools with structured inputs and stores their outputs."""

from __future__ import annotations

from webknot_bd.graph.nodes.classify import FALLBACK_NOTE
from webknot_bd.graph.search_brief import read_search_brief
from webknot_bd.graph.trace import trace_event
from webknot_bd.schemas.state import GraphState
from webknot_bd.schemas.tool_io import (
    JobNewsHit,
    JobNewsSearchInput,
    JobNewsSearchOutput,
    LeadRequest,
    PageFetchInput,
    WebSearchInput,
    WebSearchOutput,
)
from webknot_bd.tools.registry import run_tool
from webknot_bd.tools.search_brief import baseline_brief

SHORT_SNIPPET = 80


def parse_lead_request(query: str) -> LeadRequest:
    """Baseline slots for a find-leads sentence. The model path is `read_search_brief`."""
    return baseline_brief(query)


def _stored(name: str, output) -> dict:
    return {"tool": name, "output": output.model_dump(mode="json")}


def tool_node(state: GraphState) -> dict:
    query = state["query"]
    intent = (state.get("intent") or {}).get("intent")
    fallback = False
    if intent == "find_leads":
        request, fallback = read_search_brief(query)
    else:
        request = baseline_brief(query)
    results: list[dict] = []
    failed_urls: list[str] = []

    if intent == "find_leads":
        searched = run_tool(
            "search_jobs_or_news",
            JobNewsSearchInput(
                query=query,
                location=request.location,
                signal=request.signal,
                max_results=request.count,
                role=request.role,
                sector=request.sector,
                remote=request.remote,
                use_brief=True,
            ),
        )
        enriched: list[JobNewsHit] = []
        fetches = 0
        for hit in searched.results:
            if len(hit.snippet) >= SHORT_SNIPPET or fetches >= request.count:
                enriched.append(hit)
                continue
            page = run_tool("fetch_company_page", PageFetchInput(url=hit.url))
            fetches += 1
            results.append(_stored("fetch_company_page", page))
            if page.error or not page.text_excerpt.strip():
                failed_urls.append(hit.url)
                enriched.append(hit)
            else:
                enriched.append(hit.model_copy(update={"snippet": page.text_excerpt}))
        searched = searched.model_copy(update={"results": enriched})
        results.insert(0, _stored("search_jobs_or_news", searched))
        message = _search_message("search_jobs_or_news", searched, failed_urls)
        if fallback:
            message = f"{FALLBACK_NOTE} {message}"
        placeholder = searched.placeholder
    elif intent == "research_company":
        searched = run_tool("web_search", WebSearchInput(query=query, max_results=5))
        results.append(_stored("web_search", searched))
        attempts = 0
        for hit in searched.results:
            if attempts >= 2:
                break
            page = run_tool("fetch_company_page", PageFetchInput(url=hit.url))
            attempts += 1
            results.append(_stored("fetch_company_page", page))
            if page.error or not page.text_excerpt.strip():
                failed_urls.append(hit.url)
                continue
            break
        message = _search_message("web_search", searched, failed_urls)
        placeholder = searched.placeholder or any(
            item["output"].get("placeholder") for item in results if item["tool"] == "fetch_company_page"
        )
    else:
        searched = run_tool("web_search", WebSearchInput(query=query, max_results=5))
        results.append(_stored("web_search", searched))
        message = _search_message("web_search", searched, [])
        placeholder = searched.placeholder

    return {
        "tool_results": results,
        "leads": [],
        "trace": [
            trace_event(
                "tool",
                message,
                tools=[item["tool"] for item in results],
                placeholder=placeholder,
                count=request.count,
                location=request.location,
                role=request.role,
                sector=request.sector,
                remote=request.remote,
                signal=request.signal.value if request.signal else None,
                fallback=fallback,
                failed_urls=failed_urls,
            )
        ],
    }


def _search_message(
    tool: str,
    output: JobNewsSearchOutput | WebSearchOutput,
    failed_urls: list[str],
) -> str:
    if output.error:
        message = f"{tool} failed: {output.error}"
    elif output.placeholder:
        message = (
            f"Placeholder {tool} returned {len(output.results)} hit(s). "
            "Live search is not connected."
        )
    elif not output.results:
        message = f"{tool} returned no results."
    else:
        message = f"Public search returned {len(output.results)} hit(s)."
    if failed_urls:
        message += f" fetch_company_page failed for {', '.join(failed_urls)}."
    return message
