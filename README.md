# Webknot BD Agent

Scaffold for a business-development agent at Webknot Technologies Pvt. Ltd. Given a target such as "Series A fintech startups in India hiring React devs", the finished agent will find matching companies, score them against Webknot's work, and draft a personal email for a person to approve.

This repository is the skeleton: schemas, both chunking strategies, tool interfaces, a compiling LangGraph, a Streamlit trace, and the three routing checks. Live search, real lead scoring, outreach prose, and LLM-as-judge scoring come next. Nothing in this app sends email.

## Stack

- Python 3.12
- LangGraph 1.2 and LangChain, for the graph and document pipeline
- Pydantic 2, for every intermediate and final payload
- Chroma on disk, with Ollama `nomic-embed-text` embeddings
- Ollama `llama3` for optional routing and optional reranking
- Streamlit for the trace and the approval buttons
- SQLite for the CRM and dedupe memory

Routing defaults to a deterministic baseline so the app runs without a model. Set `USE_LLM=true` to ask Ollama first; if the model is down or the JSON is invalid, the baseline is used. Set `RERANK=true` to reorder retrieved chunks with the same chat model.

Web search is selected as Tavily when `TAVILY_API_KEY` is set, otherwise DuckDuckGo. The search functions do not call the network yet. They return schema-valid placeholders.

## Layout

```
src/webknot_bd/schemas/    Intent, Decision, LeadCard, OutreachDraft, tool I/O, graph state
src/webknot_bd/rag/        Loaders, recursive and fixed chunkers, ingest, retriever
src/webknot_bd/tools/      Search, page fetch, job/news search, scorer, CRM
src/webknot_bd/memory/     Dedupe on company domain
src/webknot_bd/graph/      Nodes, router, compiled graph
src/webknot_bd/evals/      The three required test queries
src/webknot_bd/ui/app.py   Streamlit trace and approval gate
data/raw/web/              Service pages and case studies (recursive chunks)
data/raw/docs/             ICP and proposals (fixed-size chunks)
```

`data/raw` is seed text, marked `sample: true`. Replace it with real Webknot pages and proposals. The outreach node will not cite a chunk with `sample: true` as a client engagement.

## Setup

```bash
cd /home/shravan/Developer/webknot-bd-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest
```

Ingest the seed documents once Ollama is running and `nomic-embed-text` is pulled:

```bash
python scripts/ingest.py
```

Start the UI:

```bash
streamlit run src/webknot_bd/ui/app.py
```

Approve and reject update SQLite only. Export CSV writes `data/crm_export.csv`.

## Routes

| Query | Route |
| --- | --- |
| Which Webknot case study fits a logistics company? | retrieve |
| Find 5 fintech startups hiring React developers in Bengaluru | tool, then retrieve, then a draft |
| What makes a good cold email subject line? | direct |

A find-leads run produces fictional `example.com` cards so the graph and the UI can be exercised. Do not contact those names. Running the same target again skips companies already stored in the CRM.

## Compliance

- Every draft includes an opt-out line.
- Personal email addresses and phone numbers are stripped from drafts.
- Tools are limited to public business information. There is no people search.
- A human approves a draft before it is considered ready. There is no send step.

## Next

1. Point ingestion at real Webknot case studies, service pages, and the ICP.
2. Replace the search and page-fetch placeholders with DuckDuckGo or Tavily, still public pages only.
3. Score leads from the retrieved ICP and services, then write the email from those chunks.
4. Add the judge (relevance, and no claims that are not in the evidence or the retrieved text).
5. Assert the three eval queries end to end, not only their routes.
