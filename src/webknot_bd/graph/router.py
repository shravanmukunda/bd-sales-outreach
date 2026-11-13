"""Intent labels and the retrieve / tool / direct decision.

The baseline is deterministic so tests do not need Ollama. When `use_llm` is true,
the same functions ask Ollama for a schema-valid result. A failed call is retried
once. If the retry fails, the baseline is used and the caller records that fallback.
"""

from __future__ import annotations

import re

from webknot_bd.config import settings
from webknot_bd.graph.llm import invoke_or_baseline
from webknot_bd.schemas.decision import Decision, Route
from webknot_bd.schemas.intent import Intent, IntentLabel


def _use_model(use_llm: bool | None) -> bool:
    if use_llm is None:
        return settings.use_llm
    return use_llm


def _is_direct_advice(query: str) -> bool:
    text = query.lower().strip()
    if text.startswith("draft ") or text.startswith("write "):
        return False
    patterns = (
        "what makes a good",
        "how do i",
        "how to ",
        "best practice",
        "tips for",
    )
    return any(pattern in text for pattern in patterns)


_FIND_WORDS = ("search", "developers", "devs", "engineers", "openings", "roles")


def _wants_leads(text: str) -> bool:
    if any(token in text for token in ("find ", "hiring", "startup", "leads", "looking for")):
        return True
    return any(re.search(rf"\b{word}\b", text) for word in _FIND_WORDS)


def baseline_intent(query: str) -> Intent:
    text = query.lower()
    if "case study" in text or ("webknot" in text and "find " not in text and "hiring" not in text):
        return Intent(
            intent=IntentLabel.ask_webknot,
            confidence=0.9,
            rationale="The question is about Webknot's own material.",
        )
    if any(token in text for token in ("draft ", "write an email", "write a cold email", "outreach email")):
        return Intent(
            intent=IntentLabel.draft_outreach,
            confidence=0.88,
            rationale="The user wants an outreach draft.",
        )
    if _wants_leads(text):
        return Intent(
            intent=IntentLabel.find_leads,
            confidence=0.92,
            rationale="The user wants companies that match a target.",
        )
    if "research" in text or "company page" in text:
        return Intent(
            intent=IntentLabel.research_company,
            confidence=0.86,
            rationale="The user wants public information about a company.",
        )
    return Intent(
        intent=IntentLabel.draft_outreach,
        confidence=0.55,
        rationale=(
            "General outreach question. It does not ask for leads, research, "
            "a draft, or Webknot documents."
        ),
    )


def baseline_decision(query: str, intent: Intent) -> Decision:
    if _is_direct_advice(query) and intent.intent not in {
        IntentLabel.find_leads,
        IntentLabel.ask_webknot,
    }:
        return Decision(
            route=Route.direct,
            reason="General advice. No Webknot documents and no live company search are required.",
            confidence=0.9,
        )
    if intent.intent is IntentLabel.find_leads:
        return Decision(
            route=Route.tool,
            reason="Finding companies needs a search of public hiring, funding, or launch signals.",
            confidence=0.92,
        )
    if intent.intent is IntentLabel.research_company:
        return Decision(
            route=Route.tool,
            reason="Researching a company starts from public pages, then Webknot fit from the knowledge base.",
            confidence=0.86,
        )
    if intent.intent is IntentLabel.ask_webknot:
        return Decision(
            route=Route.retrieve,
            reason="The question is about Webknot case studies, services, or the ICP.",
            confidence=0.9,
        )
    return Decision(
        route=Route.retrieve,
        reason="A draft should be grounded in Webknot material before it is written.",
        confidence=0.84,
    )


def classify_intent(query: str, *, use_llm: bool | None = None) -> tuple[Intent, bool]:
    result, fallback = invoke_or_baseline(
        Intent,
        (
            "Classify the user query into exactly one intent: "
            "find_leads, research_company, draft_outreach, or ask_webknot. "
            "Use ask_webknot when the question is about Webknot services, case studies, or the ICP. "
            "Use find_leads when the person asks for companies, startups, or people to contact, "
            "including a place, a role, or remote work, however they phrase it. "
            "Include confidence from 0 to 1 and a short rationale.\n"
            "Examples:\n"
            "- Find 5 fintech startups hiring React developers in Bengaluru -> find_leads\n"
            "- Which Webknot case study fits a logistics company? -> ask_webknot\n"
            "- What makes a good cold email subject line? -> draft_outreach\n"
            "- Search me companies hiring Java Spring Boot devs in India -> find_leads\n"
            "- Search me startups looking for remote devs in Australia -> find_leads\n"
            "- Get me firms that need Spring developers in Sydney -> find_leads\n"
            "- Research the company page for Acme Payments -> research_company\n"
            "- Draft an outreach email for a logistics company -> draft_outreach\n"
            f"Query: {query}"
        ),
        lambda: baseline_intent(query),
        enabled=_use_model(use_llm),
    )
    if isinstance(result, Intent):
        return result, fallback
    return Intent.model_validate(result), fallback


def decide(query: str, intent: Intent, *, use_llm: bool | None = None) -> tuple[Decision, bool]:
    result, fallback = invoke_or_baseline(
        Decision,
        (
            "Choose one route. "
            "retrieve = answer from Webknot documents. "
            "tool = search or fetch public company information. "
            "direct = general knowledge, with no documents and no search. "
            "Return route, reason, and confidence from 0 to 1.\n"
            f"Intent: {intent.intent.value}\nQuery: {query}"
        ),
        lambda: baseline_decision(query, intent),
        enabled=_use_model(use_llm),
    )
    if isinstance(result, Decision):
        return result, fallback
    return Decision.model_validate(result), fallback


def route_after_decision(state: dict) -> str:
    return state["decision"]["route"]


def route_after_retrieve(state: dict) -> str:
    intent = (state.get("intent") or {}).get("intent")
    if intent in {IntentLabel.find_leads.value, IntentLabel.draft_outreach.value}:
        return "outreach"
    return "respond"
