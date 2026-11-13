"""Structured inputs and outputs for every tool the graph can call."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from webknot_bd.schemas.lead import LeadCard, Signal


class WebSearchInput(BaseModel):
    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=10)


class SearchHit(BaseModel):
    title: str
    url: str
    snippet: str


class WebSearchOutput(BaseModel):
    provider: str
    query: str
    results: list[SearchHit]
    placeholder: bool = True
    error: str = ""


class PageFetchInput(BaseModel):
    url: str = Field(min_length=1)


class PageFetchOutput(BaseModel):
    url: str
    title: str
    text_excerpt: str
    placeholder: bool = True
    company_domain: str = ""
    error: str = ""


class JobNewsSearchInput(BaseModel):
    query: str = Field(min_length=1)
    location: str | None = None
    signal: Signal | None = None
    max_results: int = Field(default=5, ge=1, le=10)
    role: str = ""
    sector: str = ""
    remote: bool = False
    use_brief: bool = False


class JobNewsHit(BaseModel):
    company: str
    signal: Signal
    title: str
    url: str
    snippet: str


class JobNewsSearchOutput(BaseModel):
    provider: str
    query: str
    results: list[JobNewsHit]
    placeholder: bool = True
    error: str = ""


class LeadRequest(BaseModel):
    """Slots read from a find-leads sentence. The search phrase is built from these, not from the raw text."""

    count: int = Field(default=5, ge=1, le=10)
    location: str | None = None
    remote: bool = False
    role: str = ""
    sector: str = ""
    signal: Signal | None = None


class ScoreLeadInput(BaseModel):
    company: str = Field(min_length=1)
    signal: Signal
    evidence_url: str
    snippet: str = ""
    query: str = ""
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    placeholder: bool = True


class ScoreLeadOutput(BaseModel):
    lead: LeadCard
    placeholder: bool = True


class CrmUpsertInput(BaseModel):
    company: str = Field(min_length=1)
    status: str = "pending_approval"
    domain: str = ""
    note: str = ""


class CrmUpsertOutput(BaseModel):
    domain: str
    created: bool
    duplicate: bool
    status: str
