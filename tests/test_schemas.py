"""Schema contracts shared by every node."""

from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from webknot_bd.graph.nodes.guardrails import OPT_OUT_LINE, apply_guardrails
from webknot_bd.graph.nodes.outreach import outreach_node
from webknot_bd.schemas import (
    Decision,
    DraftStatus,
    FinalResponse,
    Intent,
    LeadCard,
    OutreachDraft,
    Route,
)
from webknot_bd.schemas.tool_io import CrmUpsertInput, ScoreLeadInput
from webknot_bd.tools.crm import (
    approve_draft,
    connect,
    crm_upsert,
    export_csv,
    lookup,
    normalize_domain,
    reject_draft,
    set_status,
)
from webknot_bd.tools.lead_scorer import score_lead


def test_lead_card_rejects_bad_score_and_url():
    with pytest.raises(ValidationError):
        LeadCard(
            company="Acme",
            signal="hiring",
            evidence_url="https://example.com/jobs",
            fit_score=101,
            matched_service="product engineering",
            reasoning="too high",
        )
    with pytest.raises(ValidationError):
        LeadCard(
            company="Acme",
            signal="hiring",
            evidence_url="not-a-url",
            fit_score=70,
            matched_service="product engineering",
            reasoning="bad url",
        )
    with pytest.raises(ValidationError):
        LeadCard(
            company="Acme",
            signal="hiring",
            evidence_url="https://example.com/jobs",
            fit_score=70,
            matched_service="staff augmentation",
            reasoning="not an allowed line",
        )


def test_draft_defaults_to_pending_approval():
    draft = OutreachDraft(company="Acme", subject="Hiring at Acme", body="Hello")
    assert draft.status is DraftStatus.pending_approval


def test_decision_and_intent_round_trip():
    decision = Decision(route="retrieve", reason="The question is about Webknot.", confidence=0.9)
    intent = Intent(intent="ask_webknot", confidence=0.8, rationale="Case study question.")
    assert decision.route is Route.retrieve
    response = FinalResponse(answer="ok", decision=decision, intent=intent)
    dumped = response.model_dump(mode="json")
    assert dumped["decision"]["route"] == "retrieve"
    assert dumped["intent"]["intent"] == "ask_webknot"
    assert FinalResponse.model_validate(dumped).answer == "ok"


def test_guardrails_redact_contact_details_and_keep_opt_out_once():
    cleaned = apply_guardrails("Email jane.doe@gmail.com or call +91 98765 43210 about the 2026 plan.")
    assert "jane.doe@gmail.com" not in cleaned
    assert "98765" not in cleaned
    assert "2026" in cleaned
    assert cleaned.count(OPT_OUT_LINE) == 1
    assert apply_guardrails(cleaned).count(OPT_OUT_LINE) == 1


def test_crm_dedupes_on_domain_and_exports(tmp_path):
    assert normalize_domain("https://www.Example.com/jobs") == "example.com"
    assert normalize_domain("Northwind Pay") == "northwind-pay.local"
    first = crm_upsert(CrmUpsertInput(company="Northwind Pay", status="pending_approval"))
    second = crm_upsert(CrmUpsertInput(company="Northwind Pay", status="pending_approval"))
    assert first.created and not first.duplicate
    assert second.duplicate and second.status == "pending_approval"
    set_status("Northwind Pay", "approved")
    assert lookup("Northwind Pay")["status"] == "approved"
    exported = export_csv(tmp_path / "crm_export.csv")
    text = exported.read_text(encoding="utf-8")
    assert "northwind-pay.local" in text
    assert "approved" in text


def test_empty_evidence_scores_fifty_on_the_default_service():
    scored = score_lead(
        ScoreLeadInput(
            company="Acme",
            signal="funding",
            evidence_url="https://example.com/acme",
            snippet="",
            query="",
            chunks=[],
        )
    )
    assert scored.placeholder is True
    assert scored.lead.fit_score == 50
    assert scored.lead.matched_service == "product engineering"
    assert scored.lead.reasoning.startswith("PLACEHOLDER")


def _age_row(company: str, *, days: int, status: str) -> None:
    row = lookup(company)
    assert row is not None
    stamped = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with closing(connect()) as conn:
        conn.execute(
            "UPDATE companies SET updated_at = ?, status = ? WHERE domain = ?",
            (stamped, status, row["domain"]),
        )
        conn.commit()


def _one_lead(company: str) -> dict:
    return outreach_node(
        {
            "query": company,
            "retrieved_chunks": [],
            "tool_results": [],
            "leads": [
                {
                    "company": company,
                    "signal": "hiring",
                    "evidence_url": "https://example.com/jobs/window",
                    "fit_score": 80,
                    "matched_service": "product engineering",
                    "reasoning": "PLACEHOLDER window",
                }
            ],
        }
    )


def test_rejected_row_blocks_a_draft_until_the_window_expires():
    crm_upsert(CrmUpsertInput(company="Recent Co", status="pending_approval"))
    _age_row("Recent Co", days=1, status="rejected")
    blocked = _one_lead("Recent Co")
    assert blocked["drafts"] == []
    assert blocked["leads"]
    assert "90-day" in blocked["trace"][0]["message"]
    assert blocked["trace"][0]["data"]["skipped"][0]["status"] == "rejected"
    assert lookup("Recent Co")["status"] == "rejected"

    crm_upsert(CrmUpsertInput(company="Old Co", status="pending_approval"))
    _age_row("Old Co", days=91, status="rejected")
    allowed = _one_lead("Old Co")
    assert len(allowed["drafts"]) == 1
    assert lookup("Old Co")["status"] == "pending_approval"


def test_approve_draft_stores_the_edited_text_and_reject_leaves_it(tmp_path):
    crm_upsert(CrmUpsertInput(company="Northwind Pay", status="pending_approval", note="draft created"))
    before = lookup("Northwind Pay")
    with pytest.raises(ValueError):
        approve_draft("Northwind Pay", "  ", "Edited body")
    assert lookup("Northwind Pay") == before

    approve_draft("Northwind Pay", "Hiring at Northwind Pay", "Edited body")
    approved = lookup("Northwind Pay")
    assert approved["status"] == "approved"
    assert approved["subject"] == "Hiring at Northwind Pay"
    assert approved["body"] == "Edited body"
    assert approved["note"] == "approved"
    assert approved["updated_at"] != before["updated_at"]

    approve_draft("Northwind Pay", "New subject", "New body")
    again = lookup("Northwind Pay")
    assert again["status"] == "approved"
    assert again["subject"] == "New subject"
    assert again["body"] == "New body"

    reject_draft("Northwind Pay")
    rejected = lookup("Northwind Pay")
    assert rejected["status"] == "rejected"
    assert rejected["note"] == "rejected"
    assert rejected["subject"] == "New subject"
    assert rejected["body"] == "New body"

    exported = export_csv(tmp_path / "crm_export.csv")
    lines = exported.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    assert "subject" in header
    assert "body" in header
    assert any("New subject" in line and "New body" in line for line in lines[1:])


def test_approve_draft_inserts_a_missing_company():
    approve_draft("Fresh Co", "Hello Fresh", "Body text")
    row = lookup("Fresh Co")
    assert row is not None
    assert row["status"] == "approved"
    assert row["subject"] == "Hello Fresh"
    assert row["body"] == "Body text"


def test_older_database_gains_subject_and_body_without_dropping_rows(monkeypatch, tmp_path):
    import sqlite3

    from webknot_bd.config import settings

    path = tmp_path / "legacy.sqlite"
    raw = sqlite3.connect(path)
    raw.execute(
        """
        CREATE TABLE companies (
            domain TEXT PRIMARY KEY,
            company TEXT NOT NULL,
            status TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            note TEXT DEFAULT ''
        )
        """
    )
    raw.execute(
        "INSERT INTO companies (domain, company, status, updated_at, note) VALUES (?, ?, ?, ?, ?)",
        (
            "northwind-pay.local",
            "Northwind Pay",
            "pending_approval",
            "2020-01-01T00:00:00+00:00",
            "draft created",
        ),
    )
    raw.commit()
    raw.close()
    monkeypatch.setattr(settings, "crm_path", path)
    row = lookup("Northwind Pay")
    assert row is not None
    assert row["status"] == "pending_approval"
    assert row["subject"] == ""
    assert row["body"] == ""
    assert row["note"] == "draft created"
