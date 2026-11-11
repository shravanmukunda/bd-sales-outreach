"""Final response returned to the UI and the trace of how it was built."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from webknot_bd.schemas.decision import Decision
from webknot_bd.schemas.intent import Intent
from webknot_bd.schemas.lead import LeadCard
from webknot_bd.schemas.outreach import OutreachDraft


class TraceEvent(BaseModel):
    node: str = Field(min_length=1)
    message: str = Field(min_length=1)
    data: dict[str, Any] = Field(default_factory=dict)


class FinalResponse(BaseModel):
    answer: str = Field(min_length=1)
    leads: list[LeadCard] = Field(default_factory=list)
    drafts: list[OutreachDraft] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)
    decision: Decision | None = None
    intent: Intent | None = None
