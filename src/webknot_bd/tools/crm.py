"""SQLite CRM. One row per company domain, so the same company is not drafted twice."""

from __future__ import annotations

import csv
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from webknot_bd.config import settings
from webknot_bd.schemas.tool_io import CrmUpsertInput, CrmUpsertOutput

_ALLOWED_STATUS = {"pending_approval", "approved", "rejected"}


def normalize_domain(value: str) -> str:
    """Turn a company name or URL into a stable dedupe key."""
    text = value.strip().lower()
    text = re.sub(r"^https?://", "", text)
    text = text.split("/")[0]
    if text.startswith("www."):
        text = text[4:]
    if "." in text and " " not in text:
        return text
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return f"{slug or 'unknown'}.local"


def connect(path: Path | None = None) -> sqlite3.Connection:
    database = path or settings.crm_path
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS companies (
            domain TEXT PRIMARY KEY,
            company TEXT NOT NULL,
            status TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            note TEXT DEFAULT ''
        )
        """
    )
    return conn


def lookup(company_or_domain: str) -> dict | None:
    domain = normalize_domain(company_or_domain)
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM companies WHERE domain = ?", (domain,)).fetchone()
    return dict(row) if row else None


def crm_upsert(payload: CrmUpsertInput) -> CrmUpsertOutput:
    domain = normalize_domain(payload.domain or payload.company)
    if payload.status not in _ALLOWED_STATUS:
        raise ValueError(f"Unsupported CRM status: {payload.status}")
    now = datetime.now(timezone.utc).isoformat()
    with closing(connect()) as conn:
        existing = conn.execute(
            "SELECT status FROM companies WHERE domain = ?",
            (domain,),
        ).fetchone()
        if existing:
            return CrmUpsertOutput(
                domain=domain,
                created=False,
                duplicate=True,
                status=existing["status"],
            )
        conn.execute(
            """
            INSERT INTO companies (domain, company, status, updated_at, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (domain, payload.company, payload.status, now, payload.note),
        )
        conn.commit()
    return CrmUpsertOutput(domain=domain, created=True, duplicate=False, status=payload.status)


def set_status(company_or_domain: str, status: str) -> str:
    """Approve or reject a company. Does not send email."""
    if status not in _ALLOWED_STATUS:
        raise ValueError(f"Unsupported CRM status: {status}")
    domain = normalize_domain(company_or_domain)
    now = datetime.now(timezone.utc).isoformat()
    with closing(connect()) as conn:
        updated = conn.execute(
            "UPDATE companies SET status = ?, updated_at = ? WHERE domain = ?",
            (status, now, domain),
        )
        if updated.rowcount == 0:
            conn.execute(
                """
                INSERT INTO companies (domain, company, status, updated_at, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (domain, company_or_domain, status, now, ""),
            )
        conn.commit()
    return domain


def list_companies() -> list[dict]:
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT domain, company, status, updated_at, note FROM companies ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def export_csv(dest: Path | None = None) -> Path:
    target = dest or settings.crm_path.with_name("crm_export.csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = list_companies()
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["domain", "company", "status", "updated_at", "note"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return target
