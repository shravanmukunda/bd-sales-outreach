"""Product bar for the three rubric queries. Routes stay covered in test_routing.py."""

from pathlib import Path

from webknot_bd.graph.builder import run_query
from webknot_bd.graph.nodes.guardrails import OPT_OUT_LINE
from webknot_bd.graph.nodes.outreach import outreach_node

APP_SOURCE = Path(__file__).resolve().parents[1] / "src" / "webknot_bd" / "ui" / "app.py"


def test_logistics_case_study_is_not_offered_as_client_work():
    result = run_query("Which Webknot case study fits a logistics company?")
    answer = result["answer"].lower()
    assert result["decision"]["route"] == "retrieve"
    assert "no real case study" in answer
    assert "parcel north" not in answer
    assert "client engagement" not in answer
    assert result["leads"] == []
    assert result["drafts"] == []


def test_fintech_search_drafts_only_cards_at_or_above_sixty():
    result = run_query("Find 5 fintech startups hiring React developers in Bengaluru")
    assert result["decision"]["route"] == "tool"
    leads = result["leads"]
    drafts = result["drafts"]
    assert 1 <= len(leads) <= 5
    assert all(lead["evidence_url"].startswith(("http://", "https://")) for lead in leads)
    drafted = {draft["company"] for draft in drafts}
    assert len(drafted) == len(drafts)
    for lead in leads:
        if lead["fit_score"] >= 60:
            assert lead["company"] in drafted
        else:
            assert lead["company"] not in drafted
    assert all(draft["status"] == "pending_approval" for draft in drafts)
    assert all(OPT_OUT_LINE in draft["body"] for draft in drafts)
    assert all(draft["case_study_used"] is None for draft in drafts)


def test_subject_line_answer_stays_on_the_direct_route():
    result = run_query("What makes a good cold email subject line?")
    answer = result["answer"].lower()
    assert result["decision"]["route"] == "direct"
    assert "subject line" in answer
    assert "public signal" in answer
    assert result["leads"] == []
    assert result["drafts"] == []


def test_empty_search_does_not_invent_a_company():
    result = outreach_node(
        {
            "query": "Find 5 fintech startups hiring React developers in Bengaluru",
            "leads": [],
            "retrieved_chunks": [],
            "tool_results": [
                {
                    "tool": "search_jobs_or_news",
                    "output": {
                        "provider": "duckduckgo",
                        "query": "Find 5 fintech startups hiring React developers in Bengaluru",
                        "results": [],
                        "placeholder": False,
                    },
                }
            ],
        }
    )
    assert result["leads"] == []
    assert result["drafts"] == []


def test_fit_fifty_card_is_listed_without_a_draft():
    result = outreach_node(
        {
            "query": "eval gate",
            "leads": [
                {
                    "company": "Low Fit Co",
                    "signal": "funding",
                    "evidence_url": "https://example.com/news/low",
                    "fit_score": 50,
                    "matched_service": "product engineering",
                    "reasoning": "below the gate",
                }
            ],
            "retrieved_chunks": [],
            "tool_results": [],
        }
    )
    assert [lead["company"] for lead in result["leads"]] == ["Low Fit Co"]
    assert result["drafts"] == []


def test_draft_card_saves_an_edit_and_reject_keeps_that_text():
    from streamlit.testing.v1 import AppTest

    from webknot_bd.tools.crm import lookup

    app = AppTest.from_file(APP_SOURCE, default_timeout=30)
    app.run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    captions = [element.value for element in app.caption]
    assert any(
        "Looking for" in value and "React developers" in value and "Bengaluru" in value
        for value in captions
    )
    assert any(element.label == "Job hiring page" for element in app.link_button)
    drafts = app.session_state["result"]["drafts"]
    assert drafts
    company = drafts[0]["company"]
    assert lookup(company)["status"] == "pending_approval"
    assert lookup(company)["subject"] == ""

    app.text_input[0].set_value("   ").run()
    next(button for button in app.button if button.label == "Approve").click().run()
    assert any("subject" in error.value.lower() for error in app.error)
    assert lookup(company)["status"] == "pending_approval"
    assert lookup(company)["subject"] == ""

    app.text_input[0].set_value("Edited hiring subject").run()
    next(button for button in app.button if button.label == "Approve").click().run()
    assert not app.exception
    saved = lookup(company)
    assert saved["status"] == "approved"
    assert saved["subject"] == "Edited hiring subject"
    assert saved["body"] == drafts[0]["body"]
    assert app.session_state["result"]["drafts"][0]["status"] == "approved"
    assert app.session_state["result"]["drafts"][0]["subject"] == "Edited hiring subject"

    next(button for button in app.button if button.label == "Reject").click().run()
    rejected = lookup(company)
    assert rejected["status"] == "rejected"
    assert rejected["subject"] == "Edited hiring subject"
    assert rejected["body"] == drafts[0]["body"]


def test_ui_source_has_no_send_path():
    source = APP_SOURCE.read_text(encoding="utf-8").lower()
    assert "mailto:" not in source
    assert "smtplib" not in source
    assert "clipboard" not in source
    assert "approve_draft" in source
    assert "reject_draft" in source
