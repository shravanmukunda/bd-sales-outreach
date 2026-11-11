"""Schema contracts shared by every node."""

import pytest
from pydantic import ValidationError

from webknot_bd.graph.nodes.guardrails import apply_guardrails
from webknot_bd.schemas import (
    Decision,
    DraftStatus,
    FinalResponse,
    Intent,
    LeadCard,
    OutreachDraft,
    Route,
)
from webknot_bd.schemas.tool_io import CrmUpsertInput
from webknot_bd.tools.crm import crm_upsert, export_csv, lookup, normalize_domain, set_status


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
    assert cleaned.lower().count("reply stop") == 1
    assert apply_guardrails(cleaned).lower().count("reply stop") == 1


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
