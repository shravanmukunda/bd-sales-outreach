"""Retrieval node. Reads the Chroma store and records the filter it used."""

from __future__ import annotations

from webknot_bd.config import settings
from webknot_bd.graph.trace import trace_event
from webknot_bd.rag.retriever import chroma_ready, detect_industry, detect_service, retrieve
from webknot_bd.schemas.state import GraphState


def retrieve_node(state: GraphState) -> dict:
    query = state["query"]
    industry = detect_industry(query)
    service = detect_service(query)
    if not chroma_ready():
        return {
            "retrieved_chunks": [],
            "industry": industry,
            "service": service,
            "trace": [
                trace_event(
                    "retrieve",
                    f"Vector store not found at {settings.chroma_dir}. Retrieval returned nothing.",
                    industry=industry,
                    service=service,
                    count=0,
                )
            ],
        }
    chunks = retrieve(query, industry=industry, service=service)
    return {
        "retrieved_chunks": chunks,
        "industry": industry,
        "service": service,
        "trace": [
            trace_event(
                "retrieve",
                f"Retrieved {len(chunks)} chunk(s).",
                industry=industry,
                service=service,
                count=len(chunks),
                sources=[chunk.get("source") for chunk in chunks],
            )
        ],
    }
