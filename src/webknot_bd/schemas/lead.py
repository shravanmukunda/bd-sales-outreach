"""Lead card shown to a human before any outreach is drafted."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Signal(str, Enum):
    hiring = "hiring"
    funding = "funding"
    launch = "launch"


class MatchedService(str, Enum):
    product_engineering = "product engineering"
    dedicated_squads = "dedicated squads"
    mvp_build = "MVP build"
    react_frontend = "React / frontend"
    backend_apis = "backend and APIs"
    mobile = "mobile"
    ai_ml = "AI / ML implementation"


class LeadCard(BaseModel):
    company: str = Field(min_length=1)
    signal: Signal
    evidence_url: str
    fit_score: int = Field(ge=0, le=100)
    matched_service: MatchedService
    reasoning: str = Field(min_length=1)

    @field_validator("evidence_url")
    @classmethod
    def _public_http_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("evidence_url must be an http(s) URL")
        return value
