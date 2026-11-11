"""Chroma retriever with metadata filters. Degrades to an empty list if the store is missing."""

from __future__ import annotations

import re
from pathlib import Path

from webknot_bd.config import logger, settings
from webknot_bd.rag.loaders import as_bool
from webknot_bd.rag.rerank import maybe_rerank

INDUSTRIES = ("logistics", "fintech", "healthcare", "ecommerce", "edtech")
COLLECTION_NAME = "webknot_knowledge"


def chroma_ready(path: Path | None = None) -> bool:
    directory = path or settings.chroma_dir
    return (directory / "chroma.sqlite3").exists()


def detect_industry(query: str) -> str | None:
    lowered = query.lower()
    for name in INDUSTRIES:
        if re.search(rf"\b{name}\b", lowered):
            return name
    return None


def detect_service(query: str) -> str | None:
    if "product engineering" in query.lower():
        return "product engineering"
    return None


def build_filter(industry: str | None, service: str | None) -> dict | None:
    clauses = []
    if industry:
        clauses.append({"industry": industry})
    if service:
        clauses.append({"service": service})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _to_chunk(document) -> dict:
    metadata = document.metadata or {}
    return {
        "text": document.page_content,
        "source": metadata.get("source", ""),
        "doc_type": metadata.get("doc_type", ""),
        "industry": metadata.get("industry", "general"),
        "service": metadata.get("service", "general"),
        "sample": as_bool(metadata.get("sample", False)),
        "chunk_strategy": metadata.get("chunk_strategy", ""),
    }


def retrieve(
    query: str,
    *,
    industry: str | None = None,
    service: str | None = None,
    k: int | None = None,
) -> list[dict]:
    """Top-k similarity search. Industry and service filters are optional."""
    if not chroma_ready():
        return []
    try:
        from langchain_chroma import Chroma
        from langchain_ollama import OllamaEmbeddings

        store = Chroma(
            collection_name=COLLECTION_NAME,
            persist_directory=str(settings.chroma_dir),
            embedding_function=OllamaEmbeddings(
                model=settings.ollama_embed_model,
                base_url=settings.ollama_base_url,
            ),
        )
        metadata_filter = build_filter(industry, service)
        documents = store.similarity_search(
            query,
            k=k or settings.top_k,
            filter=metadata_filter,
        )
    except Exception:
        logger.warning("Retrieval failed", exc_info=True)
        return []
    return maybe_rerank(query, [_to_chunk(document) for document in documents])
