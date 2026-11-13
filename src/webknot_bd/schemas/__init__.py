"""JSON schemas shared by every node."""

from webknot_bd.schemas.decision import Decision, Route
from webknot_bd.schemas.intent import Intent, IntentLabel
from webknot_bd.schemas.judge import JudgeNote, JudgeReport, Relevance
from webknot_bd.schemas.lead import LeadCard, MatchedService, Signal
from webknot_bd.schemas.outreach import DraftCopy, DraftStatus, OutreachDraft
from webknot_bd.schemas.response import FinalResponse, TraceEvent
from webknot_bd.schemas.state import GraphState
from webknot_bd.schemas.tool_io import (
    LeadRequest,
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
    "DraftCopy",
    "DraftStatus",
    "FinalResponse",
    "GraphState",
    "Intent",
    "IntentLabel",
    "JudgeNote",
    "JudgeReport",
    "JobNewsSearchInput",
    "JobNewsSearchOutput",
    "LeadCard",
    "LeadRequest",
    "MatchedService",
    "OutreachDraft",
    "PageFetchInput",
    "PageFetchOutput",
    "Relevance",
    "Route",
    "ScoreLeadInput",
    "ScoreLeadOutput",
    "Signal",
    "TraceEvent",
    "WebSearchInput",
    "WebSearchOutput",
]
