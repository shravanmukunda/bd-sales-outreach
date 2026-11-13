"""Streamlit shell. Shows the decision trace, lead cards, and drafts waiting for approval."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import uuid

import streamlit as st
from langgraph.checkpoint.memory import MemorySaver

from webknot_bd.evals.queries import CASES
from webknot_bd.graph.builder import build_graph
from webknot_bd.graph.nodes.classify import FALLBACK_NOTE
from webknot_bd.graph.nodes.outreach import visible_leads
from webknot_bd.tools.crm import approve_draft, export_csv, list_companies, reject_draft

def _page_label(signal: str) -> str:
    if signal == "hiring":
        return "Job hiring page"
    if signal == "funding":
        return "Funding page"
    if signal == "launch":
        return "Launch page"
    return "Source page"


def _source_link(signal: str, url: str) -> None:
    """Open the public page that justified this company."""
    if url:
        st.link_button(_page_label(signal), url)


def _brief_caption(data: dict) -> str:
    """One line for the slots the find-leads search actually used."""
    parts: list[str] = []
    if data.get("count"):
        parts.append(str(data["count"]))
    if data.get("role"):
        parts.append(str(data["role"]))
    if data.get("sector"):
        parts.append(str(data["sector"]))
    if data.get("location"):
        parts.append(str(data["location"]))
    if data.get("remote"):
        parts.append("remote")
    if data.get("signal"):
        parts.append(str(data["signal"]))
    line = "Looking for " + " · ".join(parts)
    if data.get("fallback"):
        line = f"{line}. {FALLBACK_NOTE}"
    return line


def _ui_graph():
    if "lead_graph" not in st.session_state:
        st.session_state["lead_graph"] = build_graph(
            checkpointer=MemorySaver(),
            interrupt_before=["outreach"],
        )
    return st.session_state["lead_graph"]


def _thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _preview(values: dict) -> dict:
    """Page payload after search and scoring, before any email is written."""
    leads = visible_leads(values)
    count = len(leads)
    if count:
        answer = f"Found {count} companies. Emails are still being written."
    else:
        answer = "Search finished. Emails are still being written."
    return {
        "answer": answer,
        "decision": values.get("decision") or {},
        "intent": values.get("intent") or {},
        "trace": list(values.get("trace") or []),
        "leads": leads,
        "drafts": [],
    }


st.set_page_config(page_title="Webknot BD Agent", layout="wide")
st.title("Webknot BD Agent")
st.info(
    "Drafts stay pending until you approve or reject them here. "
    "This app never sends email, and it does not collect personal contact details."
)

preset = st.selectbox("Test query", options=[case["query"] for case in CASES], index=1)
query = st.text_area("Query", value=preset, key=f"query::{preset}", height=80)

if st.button("Run", type="primary"):
    graph = _ui_graph()
    thread_id = uuid.uuid4().hex
    config = _thread_config(thread_id)
    try:
        with st.spinner("Searching"):
            graph.invoke({"query": query, "trace": []}, config)
        snapshot = graph.get_state(config)
        st.session_state["thread_id"] = thread_id
        st.session_state["ran_query"] = query
        if snapshot.next:
            st.session_state["result"] = _preview(snapshot.values)
            st.session_state["needs_drafts"] = True
        else:
            st.session_state["result"] = snapshot.values.get("final_response")
            st.session_state["needs_drafts"] = False
    except Exception as exc:
        st.session_state["needs_drafts"] = False
        st.exception(exc)
    else:
        st.rerun()

result = st.session_state.get("result")
if result:
    st.subheader("Query")
    st.write(st.session_state.get("ran_query", ""))

    decision = result.get("decision") or {}
    intent = result.get("intent") or {}
    left, right = st.columns(2)
    with left:
        st.subheader("Decision")
        st.write(f"Route: `{decision.get('route', '')}`")
        st.write(decision.get("reason", ""))
        st.write(f"Confidence: {decision.get('confidence', '')}")
    with right:
        st.subheader("Intent")
        st.write(f"`{intent.get('intent', '')}`")
        st.write(intent.get("rationale", ""))
        st.write(f"Confidence: {intent.get('confidence', '')}")

    tool_events = [event for event in (result.get("trace") or []) if event.get("node") == "tool"]
    if any((event.get("data") or {}).get("placeholder") for event in tool_events):
        st.warning(
            "Tool results in this build are fictional placeholders. "
            "They are not live fintech companies and must not be contacted."
        )

    st.subheader("Answer")
    st.write(result.get("answer", ""))

    st.subheader("Trace")
    for event in result.get("trace") or []:
        with st.expander(f"{event.get('node')}: {event.get('message')}", expanded=False):
            if event.get("data"):
                st.json(event["data"])

    st.subheader("Leads")
    if intent.get("intent") == "find_leads" and tool_events:
        st.caption(_brief_caption(tool_events[0].get("data") or {}))
    leads = result.get("leads") or []
    if not leads:
        st.caption("No lead cards on this route.")
    for lead in leads:
        with st.container(border=True):
            st.markdown(
                f"**{lead['company']}** · {lead['signal']} · fit {lead['fit_score']} · {lead['matched_service']}"
            )
            st.write(lead["reasoning"])
            _source_link(lead.get("signal", ""), lead.get("evidence_url", ""))

    st.subheader("Drafts")
    if st.session_state.get("needs_drafts"):
        graph = _ui_graph()
        config = _thread_config(st.session_state["thread_id"])
        try:
            with st.spinner("Writing emails"):
                graph.invoke(None, config)
            finished = graph.get_state(config)
            st.session_state["result"] = finished.values.get("final_response")
            st.session_state["needs_drafts"] = False
        except Exception as exc:
            st.session_state["needs_drafts"] = False
            st.exception(exc)
        else:
            st.rerun()
    drafts = result.get("drafts") or []
    if not drafts:
        st.caption("No drafts. Either this route does not write one, or the company is already in the CRM.")
    for index, draft in enumerate(drafts):
        with st.container(border=True):
            st.markdown(f"**{draft['company']}** · `{draft['status']}`")
            matched = next((item for item in leads if item.get("company") == draft["company"]), None)
            if matched:
                _source_link(matched.get("signal", ""), matched.get("evidence_url", ""))
            if draft.get("case_study_used"):
                st.caption(f"Case study: {draft['case_study_used']}")
            else:
                st.caption("No case study cited.")
            st.write("Hooks: " + "; ".join(draft.get("personalization_hooks") or []))
            card_key = f"{draft['company']}-{draft['status']}-{index}"
            subject = st.text_input("Subject", value=draft["subject"], key=f"subject-{card_key}")
            body = st.text_area("Body", value=draft["body"], height=180, key=f"body-{card_key}")
            approve, reject = st.columns(2)
            if approve.button("Approve", key=f"approve-{index}"):
                if not subject.strip() or not body.strip():
                    st.error("Enter a subject and a body before approving.")
                else:
                    approve_draft(draft["company"], subject, body)
                    saved = st.session_state["result"]["drafts"][index]
                    saved["status"] = "approved"
                    saved["subject"] = subject
                    saved["body"] = body
                    st.rerun()
            if reject.button("Reject", key=f"reject-{index}"):
                reject_draft(draft["company"])
                st.session_state["result"]["drafts"][index]["status"] = "rejected"
                st.rerun()

st.subheader("CRM")
if st.button("Export CSV"):
    path = export_csv()
    st.success(f"Wrote {path}")

rows = list_companies()
if rows:
    st.dataframe(rows, width="stretch")
else:
    st.caption("No companies stored yet.")
