"""Outreach draft. Status stays pending until a person approves it."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DraftStatus(str, Enum):
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"


class DraftCopy(BaseModel):
    """Subject and body from the writer, before status is applied."""

    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    personalization_hooks: list[str] = Field(default_factory=list)
    case_study_used: str | None = None


class OutreachDraft(BaseModel):
    company: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    personalization_hooks: list[str] = Field(default_factory=list)
    case_study_used: str | None = None
    status: DraftStatus = DraftStatus.pending_approval
