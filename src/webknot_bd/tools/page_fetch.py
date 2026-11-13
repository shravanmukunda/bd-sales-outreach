"""Fetch one public company, job, or news page."""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from webknot_bd.graph.nodes.guardrails import redact
from webknot_bd.schemas.tool_io import PageFetchInput, PageFetchOutput
from webknot_bd.tools.hosts import company_domain_for, url_allowed
from webknot_bd.tools.web_search import TIMEOUT_SECONDS

MAX_BYTES = 1_000_000
EXCERPT_CHARS = 1500
USER_AGENT = "webknot-bd-agent/0.1"


def excerpt_from_html(html: str) -> tuple[str, str]:
    """Title and the first 1,500 characters of visible text, with contact details removed."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "nav"]):
        tag.decompose()
    title = ""
    if soup.title and soup.title.string:
        title = " ".join(soup.title.get_text(" ", strip=True).split())
    text = " ".join(soup.get_text(" ", strip=True).split())
    excerpt = redact(f"{title}\n{text}".strip()) if title else redact(text)
    return title, excerpt[:EXCERPT_CHARS]


def fetch_company_page(payload: PageFetchInput) -> PageFetchOutput:
    if not url_allowed(payload.url):
        return PageFetchOutput(
            url=payload.url,
            title="",
            text_excerpt="",
            placeholder=False,
            error="blocked or non-http URL",
        )
    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=True, max_redirects=3) as client:
            with client.stream("GET", payload.url, headers={"User-Agent": USER_AGENT}) as response:
                response.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    if not chunk:
                        continue
                    room = MAX_BYTES - total
                    if room <= 0:
                        break
                    chunks.append(chunk[:room])
                    total += len(chunk[:room])
                body = b"".join(chunks)
                final_url = str(response.url)
    except Exception as exc:
        return PageFetchOutput(
            url=payload.url,
            title="",
            text_excerpt="",
            placeholder=False,
            error=f"{type(exc).__name__}: {exc}",
        )
    if not url_allowed(final_url):
        return PageFetchOutput(
            url=payload.url,
            title="",
            text_excerpt="",
            placeholder=False,
            error=f"blocked host after redirect: {final_url}",
        )
    if not body.strip():
        return PageFetchOutput(
            url=final_url,
            title="",
            text_excerpt="",
            placeholder=False,
            error="empty body",
        )
    html = body.decode("utf-8", errors="replace")
    title, excerpt = excerpt_from_html(html)
    if not excerpt.strip():
        return PageFetchOutput(
            url=final_url,
            title=title,
            text_excerpt="",
            placeholder=False,
            company_domain=company_domain_for(final_url),
            error="empty body",
        )
    return PageFetchOutput(
        url=final_url,
        title=title,
        text_excerpt=excerpt,
        placeholder=False,
        company_domain=company_domain_for(final_url),
    )
