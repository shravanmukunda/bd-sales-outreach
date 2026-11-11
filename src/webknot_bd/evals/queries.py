"""The three capstone queries and the route each one must take."""

from __future__ import annotations

CASES = [
    {
        "name": "retrieval",
        "query": "Which Webknot case study fits a logistics company?",
        "route": "retrieve",
        "intent": "ask_webknot",
    },
    {
        "name": "tool",
        "query": "Find 5 fintech startups hiring React developers in Bengaluru",
        "route": "tool",
        "intent": "find_leads",
    },
    {
        "name": "direct",
        "query": "What makes a good cold email subject line?",
        "route": "direct",
        "intent": "draft_outreach",
    },
]
