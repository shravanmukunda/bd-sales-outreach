"""Intent labels and the retrieve / tool / direct decision.

The baseline is deterministic so tests do not need Ollama. When `use_llm` is true,
the same functions ask Ollama for a schema-valid result and fall back to the baseline
if the model is down or the payload does not validate.
"""

from __future__ import annotations

from webknot_bd.config import logger, settings
from webknot_bd.graph.llm import structured_invoke
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


def baseline_intent(query: str) -> Intent:
    text = query.lower()
    if "case study" in text or ("webknot" in text and "find " not in text and "hiring" not in text):
        return Intent(
            intent=IntentLabel.ask_webknot,
            confidence=0.9,
            rationale="The question is about Webknot's own material.",
        )
    if any(token in text for token in ("find ", "hiring", "startup", "leads")):
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
    if any(token in text for token in ("draft ", "write an email", "write a cold email", "outreach email")):
        return Intent(
            intent=IntentLabel.draft_outreach,
            confidence=0.88,
            rationale="The user wants an outreach draft.",
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


def classify_intent(query: str, *, use_llm: bool | None = None) -> Intent:
    if _use_model(use_llm):
        try:
            result = structured_invoke(
                Intent,
                (
                    "Classify the user query into exactly one intent: "
                    "find_leads, research_company, draft_outreach, or ask_webknot. "
                    "Use ask_webknot when the question is about Webknot services, case studies, or the ICP. "
                    "Include confidence from 0 to 1 and a short rationale.\n"
                    f"Query: {query}"
                ),
            )
            if isinstance(result, Intent):
                return result
            return Intent.model_validate(result)
        except Exception:
            logger.warning("LLM intent classification failed; using the baseline", exc_info=True)
    return baseline_intent(query)


def decide(query: str, intent: Intent, *, use_llm: bool | None = None) -> Decision:
    if _use_model(use_llm):
        try:
            result = structured_invoke(
                Decision,
                (
                    "Choose one route. "
                    "retrieve = answer from Webknot documents. "
                    "tool = search or fetch public company information. "
                    "direct = general knowledge, with no documents and no search. "
                    "Return route, reason, and confidence from 0 to 1.\n"
                    f"Intent: {intent.intent.value}\nQuery: {query}"
                ),
            )
            if isinstance(result, Decision):
                return result
            return Decision.model_validate(result)
        except Exception:
            logger.warning("LLM routing failed; using the baseline", exc_info=True)
    return baseline_decision(query, intent)


def route_after_decision(state: dict) -> str:
    return state["decision"]["route"]


def route_after_retrieve(state: dict) -> str:
    intent = (state.get("intent") or {}).get("intent")
    if intent in {IntentLabel.find_leads.value, IntentLabel.draft_outreach.value}:
        return "outreach"
    return "respond"
