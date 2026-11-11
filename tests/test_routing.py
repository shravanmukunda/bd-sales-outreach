"""Routing for the three required queries, plus dedupe and the approval gate's draft status."""

from webknot_bd.evals.queries import CASES
from webknot_bd.graph.builder import run_query
from webknot_bd.graph.nodes.guardrails import guardrails_node
from webknot_bd.graph.nodes.outreach import usable_case_study


def _nodes(result: dict) -> list[str]:
    return [event["node"] for event in result["trace"]]


def test_required_queries_take_the_expected_route():
    expected_nodes = {
        "retrieve": ["classify", "decide", "retrieve", "respond"],
        "tool": ["classify", "decide", "tool", "retrieve", "outreach", "judge", "guardrails", "respond"],
        "direct": ["classify", "decide", "respond"],
    }
    for case in CASES:
        result = run_query(case["query"])
        assert result["decision"]["route"] == case["route"]
        assert result["intent"]["intent"] == case["intent"]
        assert _nodes(result) == expected_nodes[case["route"]]


def test_direct_answer_talks_about_subject_lines_without_tools():
    result = run_query("What makes a good cold email subject line?")
    assert "public signal" in result["answer"].lower()
    assert result["leads"] == []
    assert result["drafts"] == []


def test_tool_path_drafts_placeholders_once_then_dedupes():
    query = "Find 5 fintech startups hiring React developers in Bengaluru"
    first = run_query(query)
    assert len(first["leads"]) == 5
    assert len(first["drafts"]) == 5
    assert all(lead["fit_score"] == 70 for lead in first["leads"])
    assert all(lead["reasoning"].startswith("PLACEHOLDER") for lead in first["leads"])
    assert all(draft["status"] == "pending_approval" for draft in first["drafts"])
    assert all(draft["case_study_used"] is None for draft in first["drafts"])
    assert all("reply stop" in draft["body"].lower() for draft in first["drafts"])
    assert all("example.com" in lead["evidence_url"] for lead in first["leads"])

    second = run_query(query)
    assert second["leads"]
    assert second["drafts"] == []
    assert any("already in the CRM" in event["message"] for event in second["trace"])


def test_research_stops_before_outreach_and_draft_request_does_not():
    research = run_query("Research the company page for Acme Payments")
    assert research["decision"]["route"] == "tool"
    assert "outreach" not in _nodes(research)
    assert research["drafts"] == []

    draft = run_query("Draft an outreach email for a logistics company")
    assert draft["decision"]["route"] == "retrieve"
    assert "tool" not in _nodes(draft)
    assert len(draft["drafts"]) == 1
    assert draft["drafts"][0]["status"] == "pending_approval"
    assert draft["drafts"][0]["case_study_used"] is None


def test_sample_case_studies_are_not_cited():
    assert usable_case_study(
        [{"source": "case_study_logistics.md", "sample": True, "doc_type": "web"}]
    ) is None
    assert (
        usable_case_study(
            [{"source": "case_study_logistics.md", "sample": False, "doc_type": "web"}]
        )
        == "case_study_logistics.md"
    )


def test_guardrails_node_rewrites_a_dirty_draft():
    updated = guardrails_node(
        {
            "drafts": [
                {
                    "company": "Acme",
                    "subject": "Hello",
                    "body": "Ping jane@acme.com or +91 98765 43210.",
                    "personalization_hooks": [],
                    "case_study_used": None,
                    "status": "pending_approval",
                }
            ]
        }
    )
    body = updated["drafts"][0]["body"]
    assert "jane@acme.com" not in body
    assert "98765" not in body
    assert "reply stop" in body.lower()
    assert updated["drafts"][0]["status"] == "pending_approval"
