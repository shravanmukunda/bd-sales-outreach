"""Intent classification output."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class IntentLabel(str, Enum):
    find_leads = "find_leads"
    research_company = "research_company"
    draft_outreach = "draft_outreach"
    ask_webknot = "ask_webknot"


class Intent(BaseModel):
    intent: IntentLabel
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1)
