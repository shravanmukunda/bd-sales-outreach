"""Trace events stored on the shared graph state."""

from __future__ import annotations

from typing import Any

from webknot_bd.schemas.response import TraceEvent


def trace_event(node: str, message: str, **data: Any) -> dict:
    return TraceEvent(node=node, message=message, data=data).model_dump(mode="json")
