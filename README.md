# Webknot BD Agent

Business-development agent for Webknot Technologies Pvt. Ltd. Give it a target such as "fintech startups hiring React developers in Bengaluru". It finds public companies, scores them against the Webknot corpus, and drafts an email for a person to approve.

Nothing in this app sends email. Approve stores the edited subject and body in SQLite. Reject stores the decision and leaves the last saved text as it was.

## What a find-leads run does

With `USE_LLM=false`, which is the default, classify, decide, the search brief, the draft, and the judge use fixed rules. `llama3` is not called. Retrieval still uses the local embedding model when the Chroma store exists. The fixed brief reader still pulls a count, a place, a role, a sector, and a signal out of a find-leads sentence, then builds the search phrase from those slots.

1. The query is routed. A find-leads question goes to search. A Webknot question goes to the corpus. A general writing question is answered directly.
2. Search uses Tavily when `TAVILY_API_KEY` is set. Hiring queries look at public Greenhouse, Lever, and Ashby job posts first. With no key, search stays on DuckDuckGo. LinkedIn, Indeed, and other blocked hosts are dropped.
3. Each kept company is scored after retrieval. A draft is written only when the fit score is at least 60. The same company is skipped while its 90-day window is open, including after a reject.
4. The draft is 120–160 words, asks once for a 20-minute call, and ends with `Webknot Technologies`. Sample case studies are not cited as client work.
5. The judge writes relevance and unsupported-claim notes on the trace and does not change the draft.
6. Guardrails append the opt-out line and remove personal emails and phone numbers.

If a hiring search returns no company, the app reads names from a public startup list. It searches "top {sector} startups" in that place, then "funded {sector} startups", and marks the signal `funding`, because that page is a startup list rather than a job ad.

Set `USE_LLM=true` to ask `llama3` for classify, decide, the search brief, the draft, and the judge. A failed or rule-breaking reply is tried once more, then the same baseline is used and the trace records `fallback: true`. The lead screen shows the slots that were actually searched.

## Stack

- Python 3.12
- LangGraph and LangChain, for the graph and document pipeline
- Pydantic 2, for every intermediate and final payload
- Chroma on disk, with Ollama `nomic-embed-text` embeddings
- Ollama `llama3`, optional, for chat calls and optional reranking
- Tavily when `TAVILY_API_KEY` is set, otherwise DuckDuckGo, for public web and job/news search
- Streamlit for the trace, the draft editors, and approve or reject
- SQLite for the CRM, the saved subject and body, and the 90-day window

## Layout

```
src/webknot_bd/schemas/    Intent, Decision, LeadCard, OutreachDraft, judge notes, tool I/O
src/webknot_bd/rag/        Loaders, recursive and fixed chunkers, ingest, retriever
src/webknot_bd/tools/      Tavily or DuckDuckGo search, page fetch, scorer, CRM
src/webknot_bd/memory/     90-day dedupe on company domain
src/webknot_bd/graph/      Nodes, router, compiled graph
src/webknot_bd/evals/      The three required queries
src/webknot_bd/ui/app.py   Streamlit trace and approval gate
data/raw/web/              Service pages and case studies (recursive chunks)
data/raw/docs/             ICP and proposals (fixed-size chunks)
```

`data/raw` is seed text, marked `sample: true`. The logistics answer says the corpus has no real case study. Swap in real Webknot pages when you have them. Outreach will not cite a `sample: true` chunk as a client engagement.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest
```

`pytest` stays offline. The default suite uses a fictional search fixture and does not call Ollama or DuckDuckGo. `pytest -m network` runs the one live search check.

Ingest the seed documents once Ollama is running and `nomic-embed-text` is pulled:

```bash
python scripts/ingest.py
```

Start the UI with the chat model on so an open lead sentence is read by `llama3`. Leave the flag unset to keep the fixed reader.

```bash
USE_LLM=true streamlit run src/webknot_bd/ui/app.py
```

Open http://localhost:8501. Export CSV writes `data/crm_export.csv` with `subject` and `body`.

## Routes

| Query | What you get |
| --- | --- |
| Which Webknot case study fits a logistics company? | Corpus answer. It says there is no real case study. No leads and no drafts |
| Find 5 fintech startups hiring React developers in Bengaluru | Public search, up to 5 cards, a draft for each card at fit 60 or above |
| What makes a good cold email subject line? | A direct answer about a subject line tied to a public signal. No leads and no drafts |

## Compliance

- Every draft includes: `If you'd rather not hear from Webknot, reply 'stop' and we won't contact this address again.`
- Personal email addresses and phone numbers are stripped from drafts.
- Tools stay on public business pages. There is no people search.
- A person approves or rejects in the app. There is no mailto link, no SMTP call, and no copy-to-clipboard control.
