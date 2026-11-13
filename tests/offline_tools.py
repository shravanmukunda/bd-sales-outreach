"""Fictional search results for the default test suite. They do not call the network."""

from __future__ import annotations

from webknot_bd.schemas.lead import Signal
from webknot_bd.schemas.tool_io import (
    JobNewsHit,
    JobNewsSearchInput,
    JobNewsSearchOutput,
    PageFetchInput,
    PageFetchOutput,
    SearchHit,
    WebSearchInput,
    WebSearchOutput,
)

# The first five stay in this order because the rubric query asks for five.
_PLACEHOLDERS: tuple[tuple[str, Signal, str], ...] = (
    ("Northwind Pay", Signal.hiring, "https://example.com/jobs/northwind-pay-react"),
    ("Harbor Ledger", Signal.funding, "https://example.com/news/harbor-ledger-series-a"),
    ("Koel Checkout", Signal.launch, "https://example.com/blog/koel-checkout-launch"),
    ("Sable Mint", Signal.hiring, "https://example.com/jobs/sable-mint-react"),
    ("Brightline Kash", Signal.funding, "https://example.com/news/brightline-kash-round"),
    ("Nimbus Till", Signal.launch, "https://example.com/blog/nimbus-till-launch"),
    ("Cinder Wallet", Signal.hiring, "https://example.com/jobs/cinder-wallet"),
    ("Orchard Mint", Signal.funding, "https://example.com/news/orchard-mint-round"),
    ("Velora Books", Signal.launch, "https://example.com/blog/velora-books-launch"),
    ("Pebble Path", Signal.hiring, "https://example.com/jobs/pebble-path"),
)


def offline_web_search(payload: WebSearchInput) -> WebSearchOutput:
    return WebSearchOutput(
        provider="duckduckgo",
        query=payload.query,
        results=[
            SearchHit(
                title="Placeholder search result",
                url="https://example.com/search",
                snippet=(
                    "Live web search is not connected for this test run. "
                    "This hit only proves the tool schema. It is not a real company."
                ),
            )
        ],
        placeholder=True,
    )


def offline_fetch_company_page(payload: PageFetchInput) -> PageFetchOutput:
    return PageFetchOutput(
        url=payload.url,
        title="Placeholder company page",
        text_excerpt=(
            "Page fetch is not connected for this test run. "
            "No personal contact details were collected."
        ),
        placeholder=True,
    )


def offline_search_jobs_or_news(payload: JobNewsSearchInput) -> JobNewsSearchOutput:
    hits = [
        JobNewsHit(
            company=company,
            signal=signal,
            title=f"Placeholder {signal.value} signal for {company}",
            url=url,
            snippet=(
                "PLACEHOLDER. Not a real company and not a live job or news result. "
                f"The query was: {payload.query}"
            ),
        )
        for company, signal, url in _PLACEHOLDERS[: payload.max_results]
    ]
    return JobNewsSearchOutput(
        provider="duckduckgo",
        query=payload.query,
        results=hits,
        placeholder=True,
    )
