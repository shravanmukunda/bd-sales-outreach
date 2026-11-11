"""Job-board and news search. Returns fictional placeholders so the graph can be demoed offline."""

from __future__ import annotations

from webknot_bd.schemas.lead import Signal
from webknot_bd.schemas.tool_io import JobNewsHit, JobNewsSearchInput, JobNewsSearchOutput
from webknot_bd.tools.web_search import search_provider

# Fictional names and example.com URLs. They are not research results.
_PLACEHOLDERS: tuple[tuple[str, Signal, str], ...] = (
    ("Northwind Pay", Signal.hiring, "https://example.com/jobs/northwind-pay-react"),
    ("Harbor Ledger", Signal.funding, "https://example.com/news/harbor-ledger-series-a"),
    ("Koel Checkout", Signal.launch, "https://example.com/blog/koel-checkout-launch"),
    ("Sable Mint", Signal.hiring, "https://example.com/jobs/sable-mint-react"),
    ("Brightline Kash", Signal.funding, "https://example.com/news/brightline-kash-round"),
)


def search_jobs_or_news(payload: JobNewsSearchInput) -> JobNewsSearchOutput:
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
        provider=search_provider(),
        query=payload.query,
        results=hits,
        placeholder=True,
    )
