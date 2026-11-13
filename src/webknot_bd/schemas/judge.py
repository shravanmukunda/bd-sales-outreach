"""Judge notes. They describe a draft and do not approve it."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Relevance(str, Enum):
    strong = "strong"
    adequate = "adequate"
    weak = "weak"


class JudgeNote(BaseModel):
    company: str = Field(min_length=1)
    relevance: Relevance
    unsupported_claims: list[str] = Field(default_factory=list)


class JudgeReport(BaseModel):
    """One note per draft, in draft order."""

    notes: list[JudgeNote] = Field(default_factory=list)
