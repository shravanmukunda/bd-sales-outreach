"""Structured inputs and outputs for every tool the graph can call."""

from __future__ import annotations

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


class PageFetchInput(BaseModel):
    url: str = Field(min_length=1)


class PageFetchOutput(BaseModel):
    url: str
    title: str
    text_excerpt: str
    placeholder: bool = True


class JobNewsSearchInput(BaseModel):
    query: str = Field(min_length=1)
    location: str | None = None
    max_results: int = Field(default=5, ge=1, le=10)


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


class ScoreLeadInput(BaseModel):
    company: str = Field(min_length=1)
    signal: Signal
    evidence_url: str
    snippet: str = ""
    matched_service: str = "product engineering"
    fit_score: int = Field(default=70, ge=0, le=100)


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
