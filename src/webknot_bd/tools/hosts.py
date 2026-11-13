"""Host rules for public company, job, and news URLs."""

from __future__ import annotations

from urllib.parse import urlparse

# People search, social networks, and login-gated job boards.
BLOCKED_HOSTS = frozenset(
    {
        "linkedin.com",
        "lnkd.in",
        "facebook.com",
        "instagram.com",
        "twitter.com",
        "x.com",
        "zoominfo.com",
        "apollo.io",
        "lusha.com",
        "hunter.io",
        "rocketreach.co",
        "signalhire.com",
        "contactout.com",
        "naukri.com",
        "instahyre.com",
        "indeed.com",
        "wellfound.com",
        "angel.co",
    }
)

# Article hosts. They can be evidence, and they are not the company's own domain.
PUBLISHER_HOSTS = frozenset(
    {
        "techcrunch.com",
        "yourstory.com",
        "economictimes.com",
        "inc42.com",
        "entrackr.com",
        "moneycontrol.com",
        "livemint.com",
        "bloomberg.com",
        "reuters.com",
        "forbes.com",
    }
)


def host_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        return host[4:]
    return host


def _matches(host: str, names: frozenset[str]) -> bool:
    return any(host == name or host.endswith("." + name) for name in names)


def url_allowed(url: str) -> bool:
    """True for an http(s) URL whose host is not blocked."""
    if not url.startswith(("http://", "https://")):
        return False
    host = host_of(url)
    if not host:
        return False
    return not _matches(host, BLOCKED_HOSTS)


def company_domain_for(url: str) -> str:
    """The company host, or empty when the URL is a publisher, blocked, or not http(s)."""
    if not url_allowed(url):
        return ""
    host = host_of(url)
    if _matches(host, PUBLISHER_HOSTS) or _matches(host, BLOCKED_HOSTS):
        return ""
    return host
