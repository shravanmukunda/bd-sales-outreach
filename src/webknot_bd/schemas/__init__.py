"""JSON schemas shared by every node."""

from webknot_bd.schemas.decision import Decision, Route
from webknot_bd.schemas.intent import Intent, IntentLabel
from webknot_bd.schemas.lead import LeadCard, Signal
from webknot_bd.schemas.outreach import DraftStatus, OutreachDraft
from webknot_bd.schemas.response import FinalResponse, TraceEvent
from webknot_bd.schemas.state import GraphState
from webknot_bd.schemas.tool_io import (
    CrmUpsertInput,
    CrmUpsertOutput,
    JobNewsSearchInput,
    JobNewsSearchOutput,
    PageFetchInput,
    PageFetchOutput,
    ScoreLeadInput,
    ScoreLeadOutput,
    WebSearchInput,
    WebSearchOutput,
)

__all__ = [
    "CrmUpsertInput",
    "CrmUpsertOutput",
    "Decision",
    "DraftStatus",
    "FinalResponse",
    "GraphState",
    "Intent",
    "IntentLabel",
    "JobNewsSearchInput",
    "JobNewsSearchOutput",
    "LeadCard",
    "OutreachDraft",
    "PageFetchInput",
    "PageFetchOutput",
    "Route",
    "ScoreLeadInput",
    "ScoreLeadOutput",
    "Signal",
    "TraceEvent",
    "WebSearchInput",
    "WebSearchOutput",
]
