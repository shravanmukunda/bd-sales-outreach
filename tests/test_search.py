"""Public-search parsing. Default tests do not call DuckDuckGo.

The live check is marked network. Run it with: pytest -m network
"""

import pytest

from webknot_bd.config import settings
from webknot_bd.graph.nodes.respond import respond_node
from webknot_bd.graph.nodes.tool_node import tool_node
from webknot_bd.schemas.lead import Signal
from webknot_bd.schemas.tool_io import JobNewsSearchInput, PageFetchOutput
from webknot_bd.tools import web_search
from webknot_bd.tools.hosts import company_domain_for
from webknot_bd.tools.job_news_search import (
    company_names_from_html,
    ddg_query,
    hit_from_row,
    order_hits,
    search_jobs_or_news as live_search_jobs_or_news,
    strip_legal_suffix,
)
from webknot_bd.tools.search_brief import baseline_brief, search_phrase
from webknot_bd.tools.page_fetch import excerpt_from_html
from webknot_bd.tools.registry import TOOL_REGISTRY
from webknot_bd.tools.web_search import search_provider


def test_hiring_signal_keeps_hiring_rows_in_order():
    rows = [
        _row("Engineer at Harbor Ledger", "https://harbor.example/news", "funding"),
        _row("React Developer at Northwind Pay", "https://northwind.example/jobs", "hiring"),
        _row("Launch at Koel Checkout", "https://koel.example/blog", "launch"),
        _row("React Developer at Sable Mint", "https://sable.example/jobs", "hiring"),
    ]
    kept = order_hits(rows, signal=Signal.hiring, count=5)
    assert [hit.company for hit in kept] == ["Northwind Pay", "Sable Mint"]
    assert [hit.signal.value for hit in kept] == ["hiring", "hiring"]


def test_open_signal_prefers_hiring_then_funding_then_launch():
    rows = [
        _row("Launch at Koel Checkout", "https://koel.example/blog", "launch"),
        _row("Engineer at Harbor Ledger", "https://harbor.example/news", "funding"),
        _row("React Developer at Northwind Pay", "https://northwind.example/jobs", "hiring"),
        _row("React Developer at Sable Mint", "https://sable.example/jobs", "hiring"),
    ]
    kept = order_hits(rows, signal=None, count=3)
    assert [(hit.company, hit.signal.value) for hit in kept] == [
        ("Northwind Pay", "hiring"),
        ("Sable Mint", "hiring"),
        ("Harbor Ledger", "funding"),
    ]


def test_job_board_title_is_not_a_company():
    row = _row(
        "React Developer Jobs in Bengaluru - 114 Open Roles",
        "https://www.onlyfrontendjobs.com/react-developer-jobs-bengaluru",
        "hiring",
    )
    assert hit_from_row(row, Signal.hiring) is None


def test_search_phrase_drops_the_find_instruction():
    phrase = ddg_query(
        "Find 5 fintech startups hiring React developers in Bengaluru",
        Signal.hiring,
        "Bengaluru",
    )
    assert phrase == "fintech hiring React developers Bengaluru jobs"
    assert not phrase.lower().startswith("find")


def test_india_and_australia_sentences_become_search_slots():
    india = baseline_brief("Search me companies hiring Java Spring Boot devs in India")
    assert india.signal is Signal.hiring
    assert india.role == "Java Spring Boot"
    assert india.location == "India"
    assert india.remote is False
    india_phrase = search_phrase(india, signal=india.signal)
    assert india_phrase == "hiring Java Spring Boot India jobs"
    assert "search me" not in india_phrase.lower()

    australia = baseline_brief("Search me startups looking for remote devs in Australia")
    assert australia.signal is Signal.hiring
    assert australia.remote is True
    assert australia.location == "Australia"
    australia_phrase = search_phrase(australia, signal=australia.signal)
    assert australia_phrase == "hiring remote Australia jobs"
    assert "search me" not in australia_phrase.lower()


def test_open_company_request_is_find_leads():
    from webknot_bd.graph.builder import run_query

    result = run_query("Get me firms that need Spring developers in Sydney")
    assert result["intent"]["intent"] == "find_leads"
    assert result["decision"]["route"] == "tool"
    data = next(event for event in result["trace"] if event["node"] == "tool")["data"]
    assert data["location"] == "Sydney"
    assert data["role"] == "Spring developers"
    assert data["signal"] == "hiring"
    assert data["remote"] is False
    assert data["fallback"] is False


def test_whole_sentence_location_falls_back_to_the_baseline(monkeypatch):
    from webknot_bd.config import settings
    from webknot_bd.graph import llm

    query = "Search me companies hiring Java Spring Boot devs in India"
    calls = {"n": 0}

    def echo_sentence(schema, prompt):
        calls["n"] += 1
        return schema(
            count=5,
            location=query,
            role="Java Spring Boot",
            signal="hiring",
            remote=False,
        )

    monkeypatch.setattr(settings, "use_llm", True)
    monkeypatch.setattr(llm, "structured_invoke", echo_sentence)
    state = tool_node({"query": query, "intent": {"intent": "find_leads"}})
    assert calls["n"] == 2
    data = state["trace"][0]["data"]
    assert data["fallback"] is True
    assert data["location"] == "India"
    assert data["role"] == "Java Spring Boot"
    assert data["signal"] == "hiring"
    assert "Baseline used after structured output failed twice." in state["trace"][0]["message"]


def test_empty_hiring_search_tries_the_top_startups_list_next(monkeypatch):
    calls: list[str] = []

    def fake_text(query: str, _max_results: int):
        calls.append(query)
        if "jobs" in query:
            return []
        if query.startswith("top "):
            return [
                {
                    "title": "A news roundup",
                    "href": "https://example.com/roundup",
                    "body": "Nothing numbered.",
                }
            ]
        return [
            {
                "title": "Top funded fintech startups in Bengaluru",
                "href": "https://inc42.com/lists/top-funded-fintech-startups",
                "body": "A public list.",
            }
        ]

    def fake_html(url: str) -> str:
        if "inc42" not in url:
            return "<p>no companies</p>"
        return "<h2>1 . PhonePe</h2><h2>2 . CRED</h2>"

    monkeypatch.setattr(web_search, "duckduckgo_text", fake_text)
    monkeypatch.setattr("webknot_bd.tools.job_news_search._fetch_html", fake_html)
    result = live_search_jobs_or_news(
        JobNewsSearchInput(
            query="Find 5 fintech startups hiring Java developers in Bengaluru",
            location="Bengaluru",
            signal=Signal.hiring,
            max_results=5,
            role="Java developers",
            sector="fintech",
            use_brief=True,
        )
    )
    assert calls == [
        "fintech hiring Java developers Bengaluru jobs",
        "top fintech startups Bengaluru",
        "funded fintech startups Bengaluru",
    ]
    assert [hit.company for hit in result.results] == ["PhonePe", "CRED"]
    assert [hit.signal.value for hit in result.results] == ["funding", "funding"]


def test_numbered_list_becomes_companies_when_job_boards_are_the_only_hits(monkeypatch):
    calls = {"n": 0}

    def fake_text(query: str, _max_results: int):
        calls["n"] += 1
        if calls["n"] == 1:
            return [
                {
                    "title": "React Developer Jobs in Bengaluru - 114 Open Roles",
                    "href": "https://www.onlyfrontendjobs.com/react-developer-jobs-bengaluru",
                    "body": "Open roles.",
                }
            ]
        return [
            {
                "title": "Top funded fintech startups in Bengaluru",
                "href": "https://inc42.com/lists/top-funded-fintech-startups",
                "body": "A public list.",
            }
        ]

    def fake_html(_url: str) -> str:
        return "<h2>1 . PhonePe</h2><h2>2 . CRED</h2><h2>Top funded fintech startups</h2>"

    monkeypatch.setattr(web_search, "duckduckgo_text", fake_text)
    monkeypatch.setattr("webknot_bd.tools.job_news_search._fetch_html", fake_html)
    result = live_search_jobs_or_news(
        JobNewsSearchInput(
            query="Find 5 fintech startups hiring React developers in Bengaluru",
            location="Bengaluru",
            signal=Signal.hiring,
            max_results=5,
        )
    )
    assert [hit.company for hit in result.results] == ["PhonePe", "CRED"]
    assert [hit.signal.value for hit in result.results] == ["funding", "funding"]
    assert result.results[0].url == "https://inc42.com/lists/top-funded-fintech-startups"
    assert company_names_from_html(fake_html("")) == ["PhonePe", "CRED"]


def test_linkedin_is_dropped_before_the_name_is_read(monkeypatch):
    def boom(_title: str):
        raise AssertionError("company name was read for a blocked host")

    monkeypatch.setattr("webknot_bd.tools.job_news_search.company_name_from_title", boom)
    row = {
        "title": "React Developer at Northwind Pay - LinkedIn",
        "href": "https://www.linkedin.com/jobs/view/1",
        "body": "React Developer at Northwind Pay",
    }
    assert hit_from_row(row, Signal.hiring) is None


def test_zoominfo_url_is_dropped():
    row = _row("Engineer at Northwind Pay", "https://www.zoominfo.com/c/northwind", "hiring")
    assert order_hits([row], signal=Signal.hiring, count=5) == []


def test_techcrunch_hit_keeps_the_evidence_url_and_not_the_publisher_domain():
    row = {
        "title": "Northwind Pay raises Series A - TechCrunch",
        "href": "https://techcrunch.com/2026/northwind",
        "body": "The company raised a round.",
        "signal": "funding",
    }
    hit = hit_from_row(row, Signal.funding)
    assert hit is not None
    assert hit.company == "Northwind Pay"
    assert hit.url == "https://techcrunch.com/2026/northwind"
    assert company_domain_for(hit.url) == ""
    assert strip_legal_suffix("Northwind Pay Inc") == "Northwind Pay"


def test_html_excerpt_strips_personal_contact_details():
    html = """
    <html><head><title>Northwind</title></head>
    <body>
      <nav>skip me</nav>
      <script>secret</script>
      <p>Email jane@acme.com or call +91 98765 43210 about the board.</p>
    </body></html>
    """
    title, excerpt = excerpt_from_html(html)
    assert title == "Northwind"
    assert "jane@acme.com" not in excerpt
    assert "98765" not in excerpt
    assert "skip me" not in excerpt
    assert "secret" not in excerpt


def test_duckduckgo_exception_returns_no_invented_companies(monkeypatch):
    def boom(_query: str, _max_results: int):
        raise RuntimeError("down")

    monkeypatch.setattr(web_search, "duckduckgo_text", boom)
    result = live_search_jobs_or_news(
        JobNewsSearchInput(query="fintech hiring", max_results=5, signal=Signal.hiring)
    )
    assert result.placeholder is False
    assert result.results == []
    assert "down" in result.error
    assert "example.com" not in result.model_dump_json()


def test_provider_uses_tavily_when_a_key_is_set(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "secret")
    assert search_provider() == "tavily"
    monkeypatch.setattr(settings, "tavily_api_key", "")
    assert search_provider() == "duckduckgo"


def test_company_name_comes_from_a_public_job_url():
    from webknot_bd.tools.job_news_search import company_name_from_url

    assert company_name_from_url("https://jobs.lever.co/razorpay/abc") == "Razorpay"
    assert company_name_from_url("https://jobs.ashbyhq.com/groww/role") == "Groww"
    assert company_name_from_url("https://boards.greenhouse.io/phonepe/jobs/1") == "Phonepe"
    assert company_name_from_url("https://example.com/jobs") is None


def test_tavily_hiring_searches_public_job_boards_first(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "secret")
    calls: list[tuple[str, list[str] | None]] = []

    def fake(query: str, _max_results: int, *, include_domains: list[str] | None = None):
        calls.append((query, include_domains))
        if include_domains:
            return [
                {
                    "title": "Backend Engineer",
                    "href": "https://jobs.lever.co/razorpay/abc",
                    "body": "Golang role in Bengaluru",
                }
            ]
        return []

    monkeypatch.setattr(web_search, "search_text", fake)
    result = live_search_jobs_or_news(
        JobNewsSearchInput(
            query="Find companies hiring golang developers in Bengaluru",
            location="Bengaluru",
            signal=Signal.hiring,
            max_results=5,
            role="golang developers",
            sector="",
            use_brief=True,
        )
    )
    assert calls[0][0] == "golang developers Bengaluru"
    assert calls[0][1] == [
        "boards.greenhouse.io",
        "job-boards.greenhouse.io",
        "jobs.lever.co",
        "jobs.ashbyhq.com",
    ]
    assert result.provider == "tavily"
    assert [hit.company for hit in result.results] == ["Razorpay"]
    assert result.results[0].signal.value == "hiring"
    assert result.results[0].url == "https://jobs.lever.co/razorpay/abc"


def test_failed_page_fetch_stays_on_the_trace_and_keeps_the_hit(monkeypatch):
    from webknot_bd.schemas.tool_io import JobNewsHit, JobNewsSearchOutput, PageFetchInput

    def short_search(payload):
        return JobNewsSearchOutput(
            provider="duckduckgo",
            query=payload.query,
            results=[
                JobNewsHit(
                    company="Northwind Pay",
                    signal="hiring",
                    title="React Developer at Northwind Pay",
                    url="https://northwind.example/jobs",
                    snippet="short",
                )
            ],
            placeholder=False,
        )

    def bad_fetch(payload: PageFetchInput):
        return PageFetchOutput(
            url=payload.url,
            title="",
            text_excerpt="",
            placeholder=False,
            error="timed out",
        )

    monkeypatch.setitem(TOOL_REGISTRY, "search_jobs_or_news", short_search)
    monkeypatch.setitem(TOOL_REGISTRY, "fetch_company_page", bad_fetch)
    state = tool_node({"query": "Find fintech startups hiring React developers", "intent": {"intent": "find_leads"}})
    message = state["trace"][0]["message"]
    assert "fetch_company_page failed for https://northwind.example/jobs" in message
    assert state["trace"][0]["data"]["placeholder"] is False
    stored = state["tool_results"][0]["output"]["results"][0]
    assert stored["url"] == "https://northwind.example/jobs"


def test_live_answer_says_public_search_when_the_tool_is_not_a_placeholder():
    state = respond_node(
        {
            "query": "Find fintech startups",
            "decision": {"route": "tool", "reason": "Finding companies needs a search.", "confidence": 0.9},
            "intent": {"intent": "find_leads", "confidence": 0.9, "rationale": "The user wants companies."},
            "leads": [],
            "drafts": [],
            "retrieved_chunks": [],
            "trace": [
                {
                    "node": "tool",
                    "message": "Public search returned 1 hit(s).",
                    "data": {"placeholder": False},
                }
            ],
        }
    )
    answer = state["final_response"]["answer"]
    assert "public search" in answer.lower()
    assert "fictional" not in answer.lower()


def test_outreach_stores_the_fetched_company_domain():
    from webknot_bd.graph.nodes.outreach import outreach_node
    from webknot_bd.tools.crm import lookup

    snippet = "Hiring React developers for the product. " * 4
    state = outreach_node(
        {
            "query": "Find fintech startups hiring React developers",
            "retrieved_chunks": [],
            "leads": [],
            "tool_results": [
                {
                    "tool": "search_jobs_or_news",
                    "output": {
                        "provider": "duckduckgo",
                        "query": "fintech",
                        "placeholder": False,
                        "error": "",
                        "results": [
                            {
                                "company": "Northwind Pay",
                                "signal": "hiring",
                                "title": "React Developer at Northwind Pay",
                                "url": "https://northwind.example/jobs",
                                "snippet": snippet,
                            }
                        ],
                    },
                },
                {
                    "tool": "fetch_company_page",
                    "output": {
                        "url": "https://northwind.example/jobs",
                        "title": "Jobs",
                        "text_excerpt": snippet,
                        "placeholder": False,
                        "company_domain": "northwind.example",
                        "error": "",
                    },
                },
            ],
        }
    )
    assert len(state["drafts"]) == 1
    assert lookup("northwind.example")["domain"] == "northwind.example"
    assert lookup("Northwind Pay") is None


@pytest.mark.network
def test_live_bengaluru_search_keeps_public_urls_only():
    result = live_search_jobs_or_news(
        JobNewsSearchInput(
            query="Find 5 fintech startups hiring React developers in Bengaluru",
            location="Bengaluru",
            signal=Signal.hiring,
            max_results=5,
        )
    )
    assert result.error == ""
    assert result.placeholder is False
    assert result.provider == "duckduckgo"
    for hit in result.results:
        assert hit.url.startswith(("http://", "https://"))
        assert company_domain_for(hit.url) or hit.url
        from webknot_bd.tools.hosts import url_allowed

        assert url_allowed(hit.url)


def _row(title: str, href: str, signal: str) -> dict:
    return {"title": title, "href": href, "body": "Public page.", "signal": signal}
