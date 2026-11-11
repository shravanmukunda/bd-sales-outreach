# Phase 1 — Scaffolding

**Status:** Done as of 11 Nov 2026.  
**Decisions:** D1–D8. D9–D18 are accepted and are the work of later phases.  
**Spec:** [PRD.md](../PRD.md), [architecture.md](../architecture.md).

This phase makes the capstone runnable on one machine with the chat model off. A query goes through a real LangGraph, comes back as a schema-valid `FinalResponse`, and shows up in Streamlit. Search hits, fit scores, draft prose, and judge scores are placeholders. The graph shape they will plug into is already compiled.

## What this phase delivered

Python 3.12, a project-local `.venv`, and the pins in `requirements.txt`: LangGraph 1.2.5, LangChain 1.3.9, Pydantic 2.13, Chroma, Streamlit. Settings live in `src/webknot_bd/config.py` and `.env.example`. `USE_LLM` defaults to false. `RERANK` defaults to false.

### Schemas

`src/webknot_bd/schemas/` is the contract between nodes.

| Model | What the scaffold enforces |
| --- | --- |
| `Intent` | `find_leads`, `research_company`, `draft_outreach`, `ask_webknot`, plus confidence and rationale |
| `Decision` | `retrieve`, `tool`, or `direct`, plus reason and confidence |
| `LeadCard` | Signal `hiring` / `funding` / `launch`, http(s) `evidence_url`, fit 0–100 |
| `OutreachDraft` | New drafts start at `pending_approval`. Later statuses are `approved` and `rejected` |
| `FinalResponse` | Answer, leads, drafts, trace, decision, intent |
| Tool I/O | Typed input and output for search, page fetch, job/news search, scoring, and CRM upsert. Search and fetch outputs carry `placeholder=true` |

`matched_service` is still a free string. Closing it to the seven allowed lines is phase 2.

### Graph

`graph/builder.py` compiles this graph:

```
START → classify → decide
  direct   → respond → END
  tool     → tool → retrieve
  retrieve → outreach → judge → guardrails → respond   (find_leads, draft_outreach)
           → respond                                    (ask_webknot, research_company)
```

`GraphState` holds the query, intent, decision, chunks, tool results, leads, drafts, an append-only trace, the final response, and optional industry and service filters. Nodes dump Pydantic models onto the state and validate them again at the next boundary.

`graph/router.py` classifies and routes with keyword baselines so tests never call Ollama. The same functions call `llama3` structured output when `USE_LLM=true`. A failed call logs a warning and uses the baseline. It does not retry, and the fallback is not written on the trace. Both of those are phase 2.

Rubric routes, asserted by `tests/test_routing.py`:

| Query | Intent | Route | Nodes |
| --- | --- | --- | --- |
| Which Webknot case study fits a logistics company? | `ask_webknot` | `retrieve` | classify, decide, retrieve, respond |
| Find 5 fintech startups hiring React developers in Bengaluru | `find_leads` | `tool` | classify, decide, tool, retrieve, outreach, judge, guardrails, respond |
| What makes a good cold email subject line? | `draft_outreach` | `direct` | classify, decide, respond |

`research_company` searches and fetches, then retrieves, and stops before outreach. `draft_outreach` retrieves and writes one draft.

### RAG

`data/raw/` is the whole corpus: `docs/icp.md`, `web/services.md`, `web/case_study_logistics.md`. All three are `sample: true`.

| Folder | Splitter | Size / overlap | Metadata `chunk_strategy` |
| --- | --- | --- | --- |
| `data/raw/web/` | Recursive | 800 / 150 | `recursive` |
| `data/raw/docs/` | Fixed character window | 1000 / 0 | `fixed` |

Chunk metadata also includes `source`, `doc_type` (`web` or `doc`), `industry`, `service`, and `sample`. `scripts/ingest.py` rebuilds `chroma/` collection `webknot_knowledge` with `nomic-embed-text`. Retrieval is similarity search, `TOP_K=4`, with an industry or service filter only when `detect_industry` or `detect_service` finds one. A missing store, or a failed embedder call, returns no chunks and the route still finishes. `tests/conftest.py` points tests at an empty temp Chroma directory, so routing tests do not call Ollama.

`rag/rerank.py` can ask the chat model to reorder the top-k. It stays off.

Outreach will not put a `sample=true` chunk in `case_study_used`. The logistics answer does not yet say, in its own sentence, that the corpus has no real case study. That sentence is phase 2.

### Tools and memory

`tools/registry.py` exposes `web_search`, `fetch_company_page`, `search_jobs_or_news`, `score_lead`, and `crm_upsert`. Search and fetch return schema-valid placeholders and do not touch the network. Job/news search returns five fictional `example.com` companies. The tool node scores each one at fit 70 with `matched_service` set to `product engineering`, before retrieval runs.

SQLite at `data/crm.sqlite` (gitignored) has one `companies` row per normalized domain, plus CSV export. `memory/dedupe.py` skips a draft whenever that domain already has a row, with no 90-day check. Approve and reject update the status and do not delete the row. Tests monkeypatch `settings.crm_path` to a temp file.

### UI and guardrails

`ui/app.py` is one Streamlit page: preset queries, route, reason, confidence, intent, answer, per-node trace, lead cards, draft body, approve / reject, CRM table, CSV export. Tool runs show a warning that the cards are fictional.

Guardrails redact personal emails and phone numbers and append an opt-out line. The line in code is shorter than the sentence locked in D18. Phase 2 replaces it with the verbatim sentence.

The judge node records `status=not_scored` and leaves drafts unchanged.

## How to run what phase 1 built

```bash
cd /home/shravan/Developer/webknot-bd-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest
```

Ingest, once Ollama is up and `nomic-embed-text` is pulled:

```bash
python scripts/ingest.py
streamlit run src/webknot_bd/ui/app.py
```

Approve and reject write SQLite only. Export writes `data/crm_export.csv`.

## Tests that lock the scaffold

| File | What it holds still |
| --- | --- |
| `tests/test_routing.py` | The three rubric routes and node orders, placeholder cards, draft-once dedupe, sample case studies left uncited, guardrail redaction |
| `tests/test_schemas.py` | Lead URL and score bounds, default draft status, CRM domain key, CSV export |
| `tests/test_chunking.py` | Fixed vs recursive strategy, seed metadata, industry filter, rerank index parser |
| `tests/conftest.py` | `USE_LLM=false`, `RERANK=false`, temp CRM, temp Chroma, empty Tavily key |

## What phase 1 left open

These are specified in the architecture and are not bugs in the scaffold. Later phases pick them up in order.

| Item | Phase |
| --- | --- |
| Case-study answer states that no real case study is in the corpus | 2 |
| `matched_service` is one of the seven allowed lines, chosen after retrieval | 2 |
| A lead under 60 is shown and gets no draft | 2 |
| Dedupe lasts 90 days, and rejected rows count | 2 |
| Structured output retries once, then the baseline is written on the trace | 2 |
| Opt-out sentence is the D18 sentence, verbatim | 2 |
| DuckDuckGo search, page fetch, requested count, signal order | 3 |
| Drafts of 120–160 words with one 20-minute-call ask | 4 |
| Judge notes for relevance and unsupported claims | 5 |
| Approve stores the edited subject and body | 6 |
| End-to-end checks on the three rubric answers | 6 |
