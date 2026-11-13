"""Judge notes stay on the trace. The draft text is not rewritten."""

from webknot_bd.evals.queries import CASES
from webknot_bd.graph.builder import run_query
from webknot_bd.graph.nodes.judge import (
    CLAIM_CASE,
    CLAIM_PRICE,
    CLAIM_SAMPLE,
    judge_node,
)
from webknot_bd.graph.nodes.outreach import build_draft
from webknot_bd.schemas.tool_io import ScoreLeadInput
from webknot_bd.tools.lead_scorer import score_lead

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


def _rubric_lead(fit: int | None = None):
    lead = score_lead(
        ScoreLeadInput(
            company="Northwind Pay",
            signal="hiring",
            evidence_url="https://example.com/jobs/northwind-pay-react",
            snippet=SNIPPET,
            query=RUBRIC_QUERY,
            chunks=SAMPLE_CHUNKS,
            placeholder=False,
        )
    ).lead
    if fit is not None:
        lead = lead.model_copy(update={"fit_score": fit})
    return lead


def _state(lead, draft, chunks=None) -> dict:
    return {
        "query": RUBRIC_QUERY,
        "leads": [lead.model_dump(mode="json")],
        "drafts": [draft.model_dump(mode="json")],
        "retrieved_chunks": SAMPLE_CHUNKS if chunks is None else chunks,
        "tool_results": [
            {
                "tool": "search_jobs_or_news",
                "output": {
                    "provider": "duckduckgo",
                    "query": RUBRIC_QUERY,
                    "results": [
                        {
                            "company": lead.company,
                            "signal": lead.signal.value,
                            "title": "Hiring",
                            "url": lead.evidence_url,
                            "snippet": SNIPPET,
                        }
                    ],
                    "placeholder": False,
                },
            }
        ],
    }


def test_hiring_baseline_is_strong_and_leaves_the_body_unchanged():
    lead = _rubric_lead()
    draft = build_draft(lead, SNIPPET, SAMPLE_CHUNKS, False)
    original = draft.body
    result = judge_node(_state(lead, draft))
    note = result["trace"][0]["data"]["notes"][0]
    assert note["company"] == "Northwind Pay"
    assert note["relevance"] == "strong"
    assert note["unsupported_claims"] == []
    assert result["trace"][0]["data"]["status"] == "scored"
    assert "drafts" not in result
    assert draft.body == original


def test_fit_seventy_is_adequate():
    lead = _rubric_lead(70)
    draft = build_draft(_rubric_lead(), SNIPPET, SAMPLE_CHUNKS, False)
    note = judge_node(_state(lead, draft))["trace"][0]["data"]["notes"][0]
    assert note["relevance"] == "adequate"
    assert note["unsupported_claims"] == []


def test_sample_case_study_and_parcel_north_are_both_flagged():
    lead = _rubric_lead()
    draft = build_draft(lead, SNIPPET, SAMPLE_CHUNKS, False).model_copy(
        update={
            "body": "Parcel North is not a client.\n\n" + build_draft(lead, SNIPPET, SAMPLE_CHUNKS, False).body,
            "case_study_used": "case_study_logistics.md",
        }
    )
    stored = draft.model_dump(mode="json")
    result = judge_node(_state(lead, draft))
    claims = result["trace"][0]["data"]["notes"][0]["unsupported_claims"]
    assert claims == [CLAIM_CASE, CLAIM_SAMPLE]
    assert stored["status"] == "pending_approval"
    assert stored["body"] == draft.body
    assert "drafts" not in result


def test_unsupported_percent_is_noted_and_left_in_the_body():
    lead = _rubric_lead()
    draft = build_draft(lead, SNIPPET, SAMPLE_CHUNKS, False).model_copy(
        update={"body": build_draft(lead, SNIPPET, SAMPLE_CHUNKS, False).body.replace(
            "20-minute call",
            "20-minute call about a 30% gain",
        )}
    )
    result = judge_node(_state(lead, draft))
    claims = result["trace"][0]["data"]["notes"][0]["unsupported_claims"]
    assert CLAIM_PRICE in claims
    assert "30%" in draft.body
    assert "drafts" not in result


def test_ask_webknot_skips_the_judge_and_an_empty_call_scores_nothing():
    ask = next(case["query"] for case in CASES if case["intent"] == "ask_webknot")
    result = run_query(ask)
    assert "judge" not in [event["node"] for event in result["trace"]]
    scored = judge_node({"drafts": [], "leads": [], "retrieved_chunks": [], "tool_results": []})
    data = scored["trace"][0]["data"]
    assert data["notes"] == []
    assert data["status"] == "scored"
    assert data["draft_count"] == 0


def test_model_failure_keeps_the_baseline_note(monkeypatch):
    from webknot_bd.config import settings
    from webknot_bd.graph import llm

    calls = {"n": 0}

    def boom(schema, prompt):
        calls["n"] += 1
        raise RuntimeError("ollama down")

    monkeypatch.setattr(settings, "use_llm", True)
    monkeypatch.setattr(llm, "structured_invoke", boom)
    lead = _rubric_lead()
    draft = build_draft(lead, SNIPPET, SAMPLE_CHUNKS, False)
    result = judge_node(_state(lead, draft))
    data = result["trace"][0]["data"]
    assert calls["n"] == 2
    assert data["fallback"] is True
    assert data["notes"][0]["relevance"] == "strong"
    assert data["notes"][0]["unsupported_claims"] == []
    assert data["status"] == "scored"


def test_schema_valid_report_with_the_wrong_company_falls_back(monkeypatch):
    from webknot_bd.config import settings
    from webknot_bd.graph import llm

    calls = {"n": 0}

    def wrong(schema, prompt):
        calls["n"] += 1
        return schema(
            notes=[
                {
                    "company": "Other Co",
                    "relevance": "strong",
                    "unsupported_claims": [""],
                }
            ]
        )

    monkeypatch.setattr(settings, "use_llm", True)
    monkeypatch.setattr(llm, "structured_invoke", wrong)
    lead = _rubric_lead()
    draft = build_draft(lead, SNIPPET, SAMPLE_CHUNKS, False)
    result = judge_node(_state(lead, draft))
    data = result["trace"][0]["data"]
    assert calls["n"] == 2
    assert data["fallback"] is True
    assert data["notes"][0]["company"] == "Northwind Pay"
