# Decisions — Webknot BD Agent

Status of the capstone build as of 11 Nov 2026. The other agent is scaffolding `/home/shravan/Developer/webknot-bd-agent` against these choices. D1–D8 come from the plan and the code already in the repo. D9–D18 are your answers from the same day. Nothing in this file is still open.

The product, in one line: a person describes a target, the agent finds public companies that match, scores them against Webknot’s offerings, and drafts an email that stays `pending_approval` until a human accepts it. The app never sends mail.

## Decided

### D1 — Local LangGraph app, not a hosted product

Python 3.12, a project-local virtualenv (not the existing `rag-env`), LangGraph 1.2.5, LangChain 1.3.9, Pydantic 2.13, Streamlit. Chat model is Ollama `llama3` at `http://127.0.0.1:11434`. Embeddings are `nomic-embed-text`. Settings live in `pydantic-settings` and `.env.example`.

Why: the capstone brief asks for LangGraph, structured JSON, RAG, and Streamlit, and this machine already has that stack. Tests must route the three required queries without calling Ollama (`USE_LLM=false`).

### D2 — One graph, four intents, three routes

Shared `GraphState`: query, intent, decision, retrieved chunks, tool results, leads, drafts, append-only trace, final response, optional industry and service filters.

Intents: `find_leads`, `research_company`, `draft_outreach`, `ask_webknot`.

Routes: `retrieve`, `tool`, `direct`. Each decision carries `reason` and `confidence`.

```
START → classify → decide
  direct  → respond → END
  tool    → tools → retrieve
  retrieve → outreach (find_leads or draft_outreach) → judge → guardrails → respond
          → respond (ask_webknot or research_company)
```

Fixed routing for the rubric queries, covered by tests without a model:

| Query | Route |
| --- | --- |
| Which Webknot case study fits a logistics company? | `retrieve` |
| Find 5 fintech startups hiring React developers in Bengaluru | `tool`, then `retrieve` for fit |
| What makes a good cold email subject line? | `direct` |

Classifier and decider share one function signature. Tests use a deterministic baseline. The same signature accepts Ollama structured output when `USE_LLM=true`.

### D3 — Schemas are the contract between nodes

Pydantic models, already in `src/webknot_bd/schemas/`:

- `LeadCard`: company, signal (`hiring` | `funding` | `launch`), `evidence_url` (http/https only), `fit_score` 0–100, `matched_service`, reasoning.
- `OutreachDraft`: company, subject, body, `personalization_hooks`, `case_study_used`, status `pending_approval` | `approved` | `rejected`. New drafts always start at `pending_approval`.
- `FinalResponse`: answer, leads, drafts, trace, decision, intent.
- Tool I/O for web search, page fetch, job/news search, lead scoring, and CRM upsert. Search and fetch outputs carry `placeholder=true` until the live tools land.

### D4 — RAG: two chunkers, one Chroma store, metadata filters

| Corpus | Folder | Splitter | Size / overlap |
| --- | --- | --- | --- |
| Case studies and service pages | `data/raw/web/` | `RecursiveCharacterTextSplitter` | 800 / 150 |
| ICP, proposals, other internal docs | `data/raw/docs/` | `CharacterTextSplitter` (fixed window) | 1000 / 0 |

Chunk metadata: `source`, `doc_type` (`web` | `doc`), `industry`, `service`, `sample`, `chunk_strategy`. Retrieval is Chroma similarity search, `TOP_K=4`, with an industry/service metadata filter when the query or the lead supplies one. Persistent store on disk (`CHROMA_DIR=chroma`), behind a retriever wrapper so the store can change later.

Rerank is off (`RERANK=false`). Turning it on asks the same Ollama chat model to reorder the top-k. No extra torch dependency.

The seed files are the whole corpus for this capstone (see D9): a labeled ICP, a services page, and one case study with `sample=true`. Outreach must not cite `sample=true` chunks as real client work.

### D5 — Tools see public business information only

Registered tools, each with a typed input and output:

- `web_search` — DuckDuckGo for this demo (see D17). The settings field for a Tavily key stays in config, and Tavily is not called.
- `fetch_company_page` — one public company or job/news URL.
- `search_jobs_or_news` — hiring, funding, and launch signals. No people search and no personal-contact scraping.
- `score_lead` — returns a `LeadCard`. The scaffold returns a fixed score; the real scorer is a later phase.
- `crm_upsert` — SQLite at `data/crm.sqlite` (gitignored), deduped on normalized company domain, plus CSV export.

### D6 — A human approves every draft; the app does not send email

Guardrails always append an opt-out line and strip text that looks like a personal email address or phone number. Approve and reject update SQLite only. The Streamlit shell shows the route, the reason, the per-node trace, the lead cards, and drafts stuck at `pending_approval`.

### D7 — Judge scores drafts; it does not invent facts

LLM-as-judge runs after the outreach node and before guardrails. It scores relevance and flags claims that are not supported by the retrieved chunks or the evidence URL. It is a later phase. The scaffold returns a schema-valid placeholder and a trace event.

### D8 — Build order

Schemas → RAG ingestion → tools → graph and routing → outreach node → UI → evals. This scaffold pass stops at a compiling graph, real chunking, typed tool stubs, a Streamlit trace shell, and routing tests. Live search, grounded email prose, and judge scores come after the skeleton compiles.

## Decided from your answers (11 Nov 2026)

These replace the working defaults. The scaffold should follow this list.

### D9 — The capstone corpus is the labeled seed

Do not crawl a Webknot site and do not block on real case-study PDFs. Ingest only the seed files in `data/raw/` (ICP, services, and one sample case study).

The sample case study stays `sample=true`. Retrieval may quote it only as sample data. Outreach must not present it as a real client engagement. For “Which Webknot case study fits a logistics company?”, the honest answer is that the corpus has no real case study yet, and the sample must not be offered as one.

### D10 — ICP filters come from the query

No standing geography filter. Apply a place only when the query names one (for example Bengaluru). Any funding stage is acceptable when the signal is strong. Industries stay open: filter on `industry` metadata only when the query names an industry. There is no company-size floor.

### D11 — Service lines the draft may offer

`matched_service` is one of:

- product engineering
- dedicated squads
- MVP build
- React / frontend
- backend and APIs
- mobile
- AI / ML implementation

Staff augmentation is not an allowed line. Do not invent a service outside this list.

### D12 — Voice, length, and the ask

Generic Webknot sign-off. No personal name, no job title. English only. About 120–160 words, direct tone, one ask (a 20-minute call). No pricing and no invented metrics.

### D13 — What gets a card, and what gets a draft

Show every lead the tools return, up to the cap below. Write a draft only when `fit_score >= 60`. A lead under 60 still appears, without a draft.

If the query gives a count, use that count. Otherwise return 5. Never return more than 10, matching `max_results` on the search tools.

If the query names a signal, search for that signal. Otherwise prefer hiring, then funding, then launch. Every lead needs one public http(s) evidence URL.

### D14 — Dedupe expires after 90 days

SQLite still keys on the normalized company domain. A second draft for that domain is skipped while the last contact row is less than 90 days old, and the trace says why. After 90 days a new draft is allowed. Rejected rows count as contact for this window. Approving or rejecting does not delete the lead.

### D15 — The human can edit, and approval only updates SQLite

The Streamlit UI lets the person edit subject and body, then approve or reject. Approval stores the edited text and sets status to `approved`. Reject sets `rejected`. No mailto link, no SMTP, no clipboard requirement.

### D16 — A failed judge flags; it does not block or rewrite

Unsupported claims or a weak relevance score leave the draft at `pending_approval`. The judge notes go on the trace. There is no automatic rewrite. The human may still approve.

### D17 — Demo search and demo model

Search uses Tavily when `TAVILY_API_KEY` is set, and DuckDuckGo when it is empty. A hiring search on Tavily checks public Greenhouse, Lever, and Ashby job posts first. No LinkedIn, no people databases, no login-gated boards.

Chat, when `USE_LLM=true`, is local Ollama `llama3` for classify, decide, the find-leads search brief, draft, and judge. If structured output fails validation, retry once, then fall back to the deterministic stub and record that fallback on the trace. The search phrase is built in code from the brief. An empty hiring search reads a public startup list and labels those cards `funding`.

### D18 — Opt-out line and the eval bar

Guardrails append this sentence verbatim. The model must not rewrite it:

> If you'd rather not hear from Webknot, reply 'stop' and we won't contact this address again.

Beyond routing, a passing eval looks like this:

- Retrieval: state that no real case study is in the corpus, and do not present the sample as client work.
- Tool: return up to 5 `LeadCard`s, each with an evidence URL.
- Direct: answer the question with no lead cards and no draft.

Judge thresholds stay qualitative until the judge node is real.

## Explicitly out of scope

- Sending email, sequences, or follow-ups.
- Scraping personal emails, phone numbers, or non-public profiles.
- Multi-user auth, hosted deployment, or a shared CRM.
- Auto-approval, even when the judge score is high.
- Citing `sample=true` corpus rows as real Webknot work.
