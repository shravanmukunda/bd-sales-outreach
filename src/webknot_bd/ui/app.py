"""Streamlit shell. Shows the decision trace, lead cards, and drafts waiting for approval."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st

from webknot_bd.evals.queries import CASES
from webknot_bd.graph.builder import run_query
from webknot_bd.tools.crm import export_csv, list_companies, set_status

st.set_page_config(page_title="Webknot BD Agent", layout="wide")
st.title("Webknot BD Agent")
st.info(
    "Drafts stay pending until you approve or reject them here. "
    "This app never sends email, and it does not collect personal contact details."
)

preset = st.selectbox("Test query", options=[case["query"] for case in CASES], index=1)
query = st.text_area("Query", value=preset, key=f"query::{preset}", height=80)

if st.button("Run", type="primary"):
    with st.spinner("Running the graph"):
        try:
            st.session_state["result"] = run_query(query)
            st.session_state["ran_query"] = query
        except Exception as exc:
            st.exception(exc)

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

    if decision.get("route") == "tool":
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
    leads = result.get("leads") or []
    if not leads:
        st.caption("No lead cards on this route.")
    for lead in leads:
        with st.container(border=True):
            st.markdown(
                f"**{lead['company']}** · {lead['signal']} · fit {lead['fit_score']} · {lead['matched_service']}"
            )
            st.write(lead["reasoning"])
            st.markdown(f"[Evidence]({lead['evidence_url']})")

    st.subheader("Drafts")
    drafts = result.get("drafts") or []
    if not drafts:
        st.caption("No drafts. Either this route does not write one, or the company is already in the CRM.")
    for index, draft in enumerate(drafts):
        with st.container(border=True):
            st.markdown(f"**{draft['company']}** · `{draft['status']}`")
            st.write(draft["subject"])
            if draft.get("case_study_used"):
                st.caption(f"Case study: {draft['case_study_used']}")
            else:
                st.caption("No case study cited.")
            st.write("Hooks: " + "; ".join(draft.get("personalization_hooks") or []))
            st.text_area("Body", value=draft["body"], height=180, key=f"body-{index}-{draft['status']}")
            approve, reject = st.columns(2)
            if approve.button("Approve", key=f"approve-{index}"):
                set_status(draft["company"], "approved")
                st.session_state["result"]["drafts"][index]["status"] = "approved"
                st.rerun()
            if reject.button("Reject", key=f"reject-{index}"):
                set_status(draft["company"], "rejected")
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
