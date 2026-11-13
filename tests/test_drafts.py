"""Grounded drafts: length, one ask, sign-off, and a model reply that fails the rules."""

import pytest

from webknot_bd.graph.nodes.guardrails import OPT_OUT_LINE, guardrails_node
from webknot_bd.graph.nodes.outreach import (
    accept_draft,
    build_draft,
    outreach_node,
    word_count,
)
from webknot_bd.schemas.lead import LeadCard
from webknot_bd.schemas.outreach import DraftCopy
from webknot_bd.tools.lead_scorer import score_lead
from webknot_bd.schemas.tool_io import ScoreLeadInput

RUBRIC_QUERY = "Find 5 fintech startups hiring React developers in Bengaluru"
SNIPPET = (
    "PLACEHOLDER. Not a real company and not a live job or news result. "
    f"The query was: {RUBRIC_QUERY}"
)
SAMPLE_CHUNKS = [
    {
        "source": "case_study_logistics.md",
        "sample": True,
        "doc_type": "web",
        "text": (
            "A made-up logistics company, Parcel North, needed a dispatch board. "
            "None of those facts are real."
        ),
    }
]


def _rubric_lead(placeholder: bool) -> LeadCard:
    return score_lead(
        ScoreLeadInput(
            company="Northwind Pay",
            signal="hiring",
            evidence_url="https://example.com/jobs/northwind-pay-react",
            snippet=SNIPPET,
            query=RUBRIC_QUERY,
            chunks=SAMPLE_CHUNKS,
            placeholder=placeholder,
        )
    ).lead


def test_rubric_lead_meets_the_voice_rules_without_the_sample_story():
    lead = _rubric_lead(False)
    draft = build_draft(lead, SNIPPET, SAMPLE_CHUNKS, False)
    accept_draft(
        DraftCopy(
            subject=draft.subject,
            body=draft.body,
            personalization_hooks=draft.personalization_hooks,
            case_study_used=draft.case_study_used,
        ),
        company=lead.company,
        signal=lead.signal.value,
        snippet=SNIPPET,
        chunks=SAMPLE_CHUNKS,
        placeholder=False,
    )
    assert 120 <= word_count(draft.body) <= 160
    assert draft.body.count("20-minute call") == 1
    assert [line.strip() for line in draft.body.splitlines() if line.strip()][-1] == "Webknot Technologies"
    assert draft.case_study_used is None
    assert "Parcel North" not in draft.body
    assert draft.personalization_hooks[0].startswith("Public signal: hiring")
    assert draft.status == "pending_approval"
    assert "Webknot" not in draft.subject
    assert len(draft.subject) <= 80


def test_placeholder_subject_is_labeled():
    lead = _rubric_lead(True)
    draft = build_draft(lead, SNIPPET, SAMPLE_CHUNKS, True)
    assert draft.subject.startswith("[sample]")
    assert len(draft.subject) <= 80


def test_fit_gate_keeps_the_low_score_card_and_drafts_the_other():
    result = outreach_node(
        {
            "query": "score gate",
            "leads": [
                {
                    "company": "Weak Co",
                    "signal": "funding",
                    "evidence_url": "https://example.com/news/weak",
                    "fit_score": 50,
                    "matched_service": "product engineering",
                    "reasoning": "below the gate",
                },
                {
                    "company": "Strong Co",
                    "signal": "hiring",
                    "evidence_url": "https://example.com/jobs/strong",
                    "fit_score": 80,
                    "matched_service": "product engineering",
                    "reasoning": "above the gate",
                },
            ],
            "retrieved_chunks": [],
            "tool_results": [],
        }
    )
    assert [lead["company"] for lead in result["leads"]] == ["Weak Co", "Strong Co"]
    assert [draft["company"] for draft in result["drafts"]] == ["Strong Co"]
    assert 120 <= word_count(result["drafts"][0]["body"]) <= 160


def test_non_sample_case_study_is_named_in_a_hook():
    chunks = [
        {
            "source": "case_study_logistics.md",
            "sample": False,
            "doc_type": "web",
            "text": "A logistics dispatch board shipped with the client team.",
        }
    ]
    lead = _rubric_lead(False)
    draft = build_draft(lead, SNIPPET, chunks, False)
    assert draft.case_study_used == "case_study_logistics.md"
    assert "Case study on file: case_study_logistics.md" in draft.personalization_hooks
    assert "Parcel North" not in draft.body


def test_priced_model_reply_is_replaced_by_the_baseline(monkeypatch):
    from webknot_bd.config import settings
    from webknot_bd.graph import llm

    calls = {"n": 0}

    def priced(schema, prompt):
        calls["n"] += 1
        body = " ".join(["word"] * 36) + " is $9.\nWebknot Technologies"
        return schema(
            subject="Hiring at Northwind Pay",
            body=body,
            personalization_hooks=[],
            case_study_used=None,
        )

    monkeypatch.setattr(settings, "use_llm", True)
    monkeypatch.setattr(llm, "structured_invoke", priced)
    result = outreach_node(
        {
            "query": "draft one",
            "leads": [_rubric_lead(False).model_dump(mode="json")],
            "retrieved_chunks": SAMPLE_CHUNKS,
            "tool_results": [],
        }
    )
    draft = result["drafts"][0]
    assert calls["n"] == 2
    assert result["trace"][0]["data"]["fallback"] is True
    assert "$" not in draft["body"]
    assert 120 <= word_count(draft["body"]) <= 160
    assert draft["status"] == "pending_approval"
    assert draft["case_study_used"] is None


def test_guardrails_append_the_opt_out_once_after_the_writer_count():
    lead = _rubric_lead(False)
    draft = build_draft(lead, SNIPPET, SAMPLE_CHUNKS, False)
    before = word_count(draft.body)
    assert OPT_OUT_LINE not in draft.body
    updated = guardrails_node({"drafts": [draft.model_dump(mode="json")]})
    body = updated["drafts"][0]["body"]
    assert body.count(OPT_OUT_LINE) == 1
    assert word_count(draft.body) == before
    assert 120 <= before <= 160


def test_accept_draft_rejects_a_short_priced_body():
    lead = _rubric_lead(False)
    bad = DraftCopy(
        subject="Hiring at Northwind Pay",
        body=" ".join(["word"] * 36) + " is $9.\nWebknot Technologies",
        personalization_hooks=[],
        case_study_used=None,
    )
    with pytest.raises(ValueError):
        accept_draft(
            bad,
            company=lead.company,
            signal=lead.signal.value,
            snippet=SNIPPET,
            chunks=SAMPLE_CHUNKS,
            placeholder=False,
        )
