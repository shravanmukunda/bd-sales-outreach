"""Optional Ollama structured-output calls. Callers fall back to the baseline on any failure."""

from __future__ import annotations

from pydantic import BaseModel

from webknot_bd.config import settings


def structured_invoke(schema: type[BaseModel], prompt: str) -> BaseModel:
    from langchain_ollama import ChatOllama

    model = ChatOllama(
        model=settings.ollama_model,
        temperature=0,
        base_url=settings.ollama_base_url,
    )
    return model.with_structured_output(schema).invoke(prompt)
