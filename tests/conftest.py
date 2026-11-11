"""Keep tests off the real CRM, the real Chroma directory, and Ollama."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    from webknot_bd.config import settings

    monkeypatch.setattr(settings, "use_llm", False)
    monkeypatch.setattr(settings, "rerank", False)
    monkeypatch.setattr(settings, "crm_path", tmp_path / "crm.sqlite")
    monkeypatch.setattr(settings, "chroma_dir", tmp_path / "chroma")
    monkeypatch.setattr(settings, "tavily_api_key", "")
    return settings
