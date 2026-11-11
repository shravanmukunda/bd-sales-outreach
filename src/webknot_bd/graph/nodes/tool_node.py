"""Tool node. Calls registered tools with structured inputs and stores their outputs."""

from __future__ import annotations

from webknot_bd.graph.trace import trace_event
from webknot_bd.schemas.tool_io import JobNewsSearchInput, PageFetchInput, ScoreLeadInput, WebSearchInput
from webknot_bd.schemas.state import GraphState
from webknot_bd.tools.registry import run_tool


def _location(query: str) -> str | None:
    if "bengaluru" in query.lower() or "bangalore" in query.lower():
        return "Bengaluru"
    return None


def tool_node(state: GraphState) -> dict:
    query = state["query"]
    intent = (state.get("intent") or {}).get("intent")
    results: list[dict] = []
    leads: list[dict] = []

    if intent == "find_leads":
        searched = run_tool(
            "search_jobs_or_news",
            JobNewsSearchInput(query=query, location=_location(query), max_results=5),
        )
        results.append({"tool": "search_jobs_or_news", "output": searched.model_dump(mode="json")})
        for hit in searched.results:
            scored = run_tool(
                "score_lead",
                ScoreLeadInput(
                    company=hit.company,
                    signal=hit.signal,
                    evidence_url=hit.url,
                    snippet=hit.snippet,
                    matched_service="product engineering",
                    fit_score=70,
                ),
            )
            leads.append(scored.lead.model_dump(mode="json"))
            results.append({"tool": "score_lead", "output": scored.model_dump(mode="json")})
        message = (
            f"Placeholder job and news search returned {len(leads)} fictional lead card(s). "
            "Live search is not connected."
        )
    elif intent == "research_company":
        searched = run_tool("web_search", WebSearchInput(query=query, max_results=5))
        results.append({"tool": "web_search", "output": searched.model_dump(mode="json")})
        page = run_tool("fetch_company_page", PageFetchInput(url=searched.results[0].url))
        results.append({"tool": "fetch_company_page", "output": page.model_dump(mode="json")})
        message = "Placeholder web search and company-page fetch. No personal contact data was collected."
    else:
        searched = run_tool("web_search", WebSearchInput(query=query, max_results=5))
        results.append({"tool": "web_search", "output": searched.model_dump(mode="json")})
        message = "Placeholder web search."

    return {
        "tool_results": results,
        "leads": leads,
        "trace": [
            trace_event(
                "tool",
                message,
                tools=[item["tool"] for item in results],
                placeholder=True,
            )
        ],
    }
