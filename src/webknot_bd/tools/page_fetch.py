"""Fetch a public company page. Placeholder only: no HTTP call and no personal-data scraping."""

from __future__ import annotations

from webknot_bd.schemas.tool_io import PageFetchInput, PageFetchOutput


def fetch_company_page(payload: PageFetchInput) -> PageFetchOutput:
    return PageFetchOutput(
        url=payload.url,
        title="Placeholder company page",
        text_excerpt=(
            "Page fetch is not connected yet. When it is, it will keep only public business "
            "information from the company page and will not collect personal contact details."
        ),
        placeholder=True,
    )
