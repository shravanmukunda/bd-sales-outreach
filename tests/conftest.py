"""Keep tests off the real CRM, the real Chroma directory, Ollama, and the network.

Live DuckDuckGo is marked `network`. The default suite skips that mark.
Run it with `pytest -m network`.
"""

from __future__ import annotations

import pytest

from offline_tools import offline_fetch_company_page, offline_search_jobs_or_news, offline_web_search


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "network: calls DuckDuckGo; run with pytest -m network",
    )


def pytest_collection_modifyitems(config, items):
    selected = config.option.markexpr or ""
    if "network" in selected.split() and "not network" not in selected:
        return
    skip = pytest.mark.skip(reason="Live DuckDuckGo. Run: pytest -m network")
    for item in items:
        if item.get_closest_marker("network"):
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    from webknot_bd.config import settings
    from webknot_bd.tools.registry import TOOL_REGISTRY

    monkeypatch.setattr(settings, "use_llm", False)
    monkeypatch.setattr(settings, "rerank", False)
    monkeypatch.setattr(settings, "crm_path", tmp_path / "crm.sqlite")
    monkeypatch.setattr(settings, "chroma_dir", tmp_path / "chroma")
    monkeypatch.setattr(settings, "tavily_api_key", "")
    monkeypatch.setitem(TOOL_REGISTRY, "web_search", offline_web_search)
    monkeypatch.setitem(TOOL_REGISTRY, "fetch_company_page", offline_fetch_company_page)
    monkeypatch.setitem(TOOL_REGISTRY, "search_jobs_or_news", offline_search_jobs_or_news)
    monkeypatch.setattr("webknot_bd.tools.web_search.web_search", offline_web_search)
    monkeypatch.setattr("webknot_bd.tools.page_fetch.fetch_company_page", offline_fetch_company_page)
    monkeypatch.setattr("webknot_bd.tools.job_news_search.search_jobs_or_news", offline_search_jobs_or_news)
    return settings
