"""Public web search. The scaffold returns a schema-valid placeholder and does not call the network."""

from __future__ import annotations

from webknot_bd.config import settings
from webknot_bd.schemas.tool_io import SearchHit, WebSearchInput, WebSearchOutput


def search_provider() -> str:
    """Tavily when an API key is configured, otherwise DuckDuckGo."""
    if settings.tavily_api_key.strip():
        return "tavily"
    return "duckduckgo"


def web_search(payload: WebSearchInput) -> WebSearchOutput:
    return WebSearchOutput(
        provider=search_provider(),
        query=payload.query,
        results=[
            SearchHit(
                title="Placeholder search result",
                url="https://example.com/search",
                snippet=(
                    "Live web search is not connected yet. "
                    "This hit only proves the tool schema. It is not a real company."
                ),
            )
        ],
        placeholder=True,
    )
