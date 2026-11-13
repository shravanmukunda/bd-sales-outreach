"""Dedupe policy: a company contacted inside 90 days does not get a new draft."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from webknot_bd.tools.crm import lookup

WINDOW = timedelta(days=90)


def _as_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def should_skip(company: str, domain: str = "") -> tuple[bool, str]:
    """Return whether a new draft is blocked, and a reason a person can read.

    A missing row is not a skip. A row younger than 90 days is a skip, including
    when its status is rejected. A row at least 90 days old is allowed, and the
    reason says the window has expired. `domain` is the company host when a page
    fetch confirmed one; otherwise the company-name slug is the key.
    """
    row = lookup(domain) if domain else None
    if row is None:
        row = lookup(company)
    if row is None:
        return False, ""
    age = datetime.now(timezone.utc) - _as_utc(str(row["updated_at"]))
    status = str(row["status"])
    if age < WINDOW:
        return True, (
            f"{company} has status {status} and the 90-day window is still open."
        )
    return False, f"The 90-day window for {company} has expired."
