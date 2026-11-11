"""Dedupe policy: a company already stored in the CRM does not get a new draft."""

from __future__ import annotations

from webknot_bd.tools.crm import lookup


def should_skip(company: str) -> tuple[bool, str]:
    row = lookup(company)
    if row is None:
        return False, ""
    return True, str(row["status"])
