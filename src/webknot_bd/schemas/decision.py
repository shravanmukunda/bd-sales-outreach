"""Decision-node output. Route is retrieve, tool, or direct."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Route(str, Enum):
    retrieve = "retrieve"
    tool = "tool"
    direct = "direct"


class Decision(BaseModel):
    route: Route
    reason: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
