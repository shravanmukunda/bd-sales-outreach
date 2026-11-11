"""Shared LangGraph state. Trace events accumulate; other fields are replaced."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class GraphState(TypedDict, total=False):
    query: str
    intent: dict[str, Any] | None
    decision: dict[str, Any] | None
    retrieved_chunks: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    leads: list[dict[str, Any]]
    drafts: list[dict[str, Any]]
    trace: Annotated[list[dict[str, Any]], operator.add]
    final_response: dict[str, Any] | None
    industry: str | None
    service: str | None
