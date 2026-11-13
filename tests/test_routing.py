"""Routing for the three required queries, plus dedupe and the approval gate's draft status."""

from webknot_bd.evals.queries import CASES
from webknot_bd.graph.builder import run_query
from webknot_bd.graph.nodes.guardrails import OPT_OUT_LINE, guardrails_node
from webknot_bd.graph.nodes.outreach import outreach_node, usable_case_study


def _nodes(result: dict) -> list[str]:
    return [event["node"] for event in result["trace"]]


def test_structured_output_retries_once_then_uses_the_baseline(monkeypatch):
    from webknot_bd.config import settings
    from webknot_bd.graph import llm
    from webknot_bd.graph.nodes.classify import classify_node

    calls = {"n": 0}

    def boom(schema, prompt):
        calls["n"] += 1
        raise RuntimeError("ollama down")

    monkeypatch.setattr(settings, "use_llm", True)
    monkeypatch.setattr(llm, "structured_invoke", boom)
    state = classify_node({"query": "Find 5 fintech startups hiring React developers in Bengaluru"})
    assert calls["n"] == 2
    assert state["intent"]["intent"] == "find_leads"
    assert state["trace"][0]["data"]["fallback"] is True
    assert "Baseline used after structured output failed twice." in state["trace"][0]["message"]


def test_search_pauses_before_the_emails_are_written():
    from langgraph.checkpoint.memory import MemorySaver

    from webknot_bd.graph.builder import build_graph
    from webknot_bd.graph.nodes.outreach import visible_leads

    graph = build_graph(checkpointer=MemorySaver(), interrupt_before=["outreach"])
    config = {"configurable": {"thread_id": "search-first"}}
    graph.invoke(
        {"query": "Find 5 fintech startups hiring React developers in Bengaluru", "trace": []},
        config,
    )
    paused = graph.get_state(config)
    assert paused.next == ("outreach",)
    assert paused.values.get("final_response") is None
    assert len(visible_leads(paused.values)) == 5

    graph.invoke(None, config)
    finished = graph.get_state(config)
    assert finished.next == ()
    assert len(finished.values["final_response"]["drafts"]) == 5
    assert len(finished.values["final_response"]["leads"]) == 5


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


def test_logistics_answer_says_there_is_no_real_case_study():
    result = run_query("Which Webknot case study fits a logistics company?")
    assert result["decision"]["route"] == "retrieve"
    assert "no real case study" in result["answer"].lower()
    assert "parcel north" not in result["answer"].lower()
    assert result["leads"] == []
    assert result["drafts"] == []


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
    scores = {lead["company"]: lead["fit_score"] for lead in first["leads"]}
    assert scores["Northwind Pay"] == 80
    assert scores["Sable Mint"] == 80
    assert scores["Harbor Ledger"] == 70
    assert scores["Brightline Kash"] == 70
    assert scores["Koel Checkout"] == 70
    assert all(lead["matched_service"] == "React / frontend" for lead in first["leads"])
    assert all(lead["reasoning"].startswith("PLACEHOLDER") for lead in first["leads"])
    assert all(draft["status"] == "pending_approval" for draft in first["drafts"])
    assert all(draft["case_study_used"] is None for draft in first["drafts"])
    assert all(draft["body"].count(OPT_OUT_LINE) == 1 for draft in first["drafts"])
    assert all("example.com" in lead["evidence_url"] for lead in first["leads"])
    assert "fictional" in first["answer"].lower()
    tool_event = next(event for event in first["trace"] if event["node"] == "tool")
    assert tool_event["data"]["count"] == 5
    assert tool_event["data"]["location"] == "Bengaluru"
    assert tool_event["data"]["role"] == "React developers"
    assert tool_event["data"]["sector"] == "fintech"
    assert tool_event["data"]["remote"] is False
    assert tool_event["data"]["signal"] == "hiring"
    assert tool_event["data"]["fallback"] is False

    second = run_query(query)
    assert second["leads"]
    assert second["drafts"] == []
    assert any("90-day" in event["message"] for event in second["trace"])
    assert "90-day window" in second["answer"]


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


def test_requested_count_is_clamped():
    three = run_query("Find 3 fintech startups")
    assert len(three["leads"]) == 3
    assert next(event for event in three["trace"] if event["node"] == "tool")["data"]["count"] == 3

    twelve = run_query("Find 12 fintech startups")
    assert len(twelve["leads"]) == 10
    assert next(event for event in twelve["trace"] if event["node"] == "tool")["data"]["count"] == 10


def test_low_fit_lead_is_shown_without_a_draft():
    strong = {
        "company": "Strong Co",
        "signal": "hiring",
        "evidence_url": "https://example.com/jobs/strong",
        "fit_score": 80,
        "matched_service": "product engineering",
        "reasoning": "PLACEHOLDER strong",
    }
    weak = {
        "company": "Weak Co",
        "signal": "funding",
        "evidence_url": "https://example.com/news/weak",
        "fit_score": 50,
        "matched_service": "product engineering",
        "reasoning": "PLACEHOLDER weak",
    }
    result = outreach_node(
        {"query": "score gate", "leads": [weak, strong], "retrieved_chunks": [], "tool_results": []}
    )
    assert [lead["company"] for lead in result["leads"]] == ["Weak Co", "Strong Co"]
    assert [draft["company"] for draft in result["drafts"]] == ["Strong Co"]


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
    assert body.count(OPT_OUT_LINE) == 1
    assert updated["drafts"][0]["status"] == "pending_approval"
