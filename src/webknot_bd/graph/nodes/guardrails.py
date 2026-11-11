"""Compliance guardrails applied to every draft before it is shown."""

from __future__ import annotations

import re

from webknot_bd.graph.trace import trace_event
from webknot_bd.schemas.outreach import OutreachDraft
from webknot_bd.schemas.state import GraphState

OPT_OUT_LINE = (
    "If you'd rather not hear from Webknot, reply stop and we won't contact you again."
)

# Personal inboxes. Evidence URLs are not passed through this.
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# At least 10 digits, so years and fit scores are left alone.
PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s-]?)?(?:\d[\s\-()]?){9,14}\d")


def redact(text: str) -> str:
    text = EMAIL_RE.sub("[removed]", text)
    text = PHONE_RE.sub("[removed]", text)
    return text


def ensure_opt_out(body: str) -> str:
    if "reply stop" in body.lower():
        return body
    return body.rstrip() + "\n\n" + OPT_OUT_LINE


def apply_guardrails(body: str) -> str:
    return ensure_opt_out(redact(body))


def guardrails_node(state: GraphState) -> dict:
    cleaned: list[dict] = []
    for raw in state.get("drafts") or []:
        draft = OutreachDraft.model_validate(raw)
        updated = draft.model_copy(
            update={
                "subject": redact(draft.subject) or draft.subject,
                "body": apply_guardrails(draft.body),
                "personalization_hooks": [redact(hook) for hook in draft.personalization_hooks],
            }
        )
        cleaned.append(updated.model_dump(mode="json"))
    return {
        "drafts": cleaned,
        "trace": [
            trace_event(
                "guardrails",
                "Added the opt-out line and removed personal emails and phone numbers.",
                drafts=len(cleaned),
            )
        ],
    }
