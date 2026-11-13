# PRD — Webknot BD Agent

**Status:** Current as of 13 Nov 2026. Decisions are in [Decisions.md](Decisions.md). How the pieces fit is in [architecture.md](architecture.md).  
**Owner:** Webknot Technologies Pvt. Ltd.  
**Product:** A local agent that turns a target description into scored lead cards and outreach drafts a person must approve. The app never sends email.

## 1. Problem

Business development at Webknot finds companies that need development work by hand: hiring posts, funding news, and product launches. Research and outreach are slow, generic, and inconsistent from one person to the next.

## 2. Product

A person types a target, for example “Series A fintech startups in India hiring React devs.” The agent:

1. Classifies the request.
2. Finds matching public companies when the request is a lead search.
3. Scores each company against Webknot’s allowed services, using the local knowledge base.
4. Drafts one email per company that clears the fit bar.
5. Leaves every draft at `pending_approval` until a person edits it and approves or rejects it.

The same app also answers questions about the Webknot corpus and general outreach advice, without inventing leads.

## 3. User

One Webknot operator on this machine. There is no login, no shared CRM, and no hosted deployment.

## 4. Goals

- Cut the manual loop of search, research, and first-draft writing.
- Keep every company claim tied to a public URL, and every Webknot claim tied to retrieved text.
- Make the route for each run visible in the UI.
- Keep a person in the loop before any draft is treated as ready.

## 5. Stack

| Piece | Choice |
| --- | --- |
| Runtime | Python 3.12, project-local virtualenv |
| Workflow | LangGraph 1.2.5, shared `GraphState` |
| Schemas | Pydantic 2.13 |
| Documents | LangChain 1.3.9 loaders and splitters |
| Vectors | Persistent Chroma (`CHROMA_DIR=chroma`) |
| Embeddings | Ollama `nomic-embed-text` |
| Chat | Ollama `llama3` at `http://127.0.0.1:11434`, only when `USE_LLM=true` |
| UI | Streamlit |
| Memory | SQLite at `data/crm.sqlite`, plus CSV export |
| Config | `pydantic-settings` and `.env.example` |

Tests for the three rubric queries must pass with `USE_LLM=false`. They must not call Ollama.

## 6. Graph

Intents: `find_leads`, `research_company`, `draft_outreach`, `ask_webknot`.

Routes: `retrieve`, `tool`, `direct`. Every decision stores `reason` and `confidence`.

```
START → classify → decide
  direct   → respond → END
  tool     → tools → retrieve
  retrieve → outreach (find_leads or draft_outreach) → judge → guardrails → respond
           → respond (ask_webknot or research_company)
```

`GraphState` holds the query, intent, decision, retrieved chunks, tool results, leads, drafts, an append-only trace, the final response, and optional industry and service filters.

Classifier and decider share one signature. The deterministic baseline is the default. With `USE_LLM=true`, the same functions call `llama3` structured output. If validation fails, retry once, then use the baseline and write that fallback on the trace. The same retry-then-baseline rule applies to draft and judge calls.

Required routes:

| Query | Route |
| --- | --- |
| Which Webknot case study fits a logistics company? | `retrieve` |
| Find 5 fintech startups hiring React developers in Bengaluru | `tool`, then `retrieve` for fit |
| What makes a good cold email subject line? | `direct` |

## 7. Functional requirements

### 7.1 Corpus

Ingest only the seed files in `data/raw/`: the ICP, the services page, and one case study. Do not crawl a Webknot site and do not wait on real case-study PDFs.

| Corpus | Folder | Splitter | Size / overlap |
| --- | --- | --- | --- |
| Case studies and service pages | `data/raw/web/` | Recursive | 800 / 150 |
| ICP and other internal docs | `data/raw/docs/` | Fixed-size character window | 1000 / 0 |

Chunk metadata: `source`, `doc_type` (`web` or `doc`), `industry`, `service`, `sample`, `chunk_strategy`.

Retrieval is Chroma similarity search, `TOP_K=4`. Apply an industry or service metadata filter only when the query or the lead names that value. There is no standing geography filter, no funding-stage filter, and no company-size floor. A place such as Bengaluru is a search constraint only when the query names it. Any funding stage is acceptable when the signal is strong.

Rerank stays off (`RERANK=false`). If turned on, the same Ollama chat model reorders the top-k. Do not add a torch reranker.

The sample case study stays `sample=true`. Retrieval may quote it only as sample data. Outreach must not present it as a real client engagement. For the logistics case-study query, the answer states that the corpus has no real case study yet.

### 7.2 Tools

Each tool has a typed input and output. Tools may use public company pages, public job posts, and public news. They must not search people, scrape personal emails or phone numbers, or open LinkedIn, people databases, or login-gated boards.

| Tool | Behavior |
| --- | --- |
| `web_search` | Tavily when `TAVILY_API_KEY` is set, otherwise DuckDuckGo |
| `fetch_company_page` | One public company, job, or news URL |
| `search_jobs_or_news` | Hiring, funding, and launch. A hiring search on Tavily checks public Greenhouse, Lever, and Ashby posts first and reads the company name from the job URL |
| `score_lead` | One `LeadCard` from the evidence URL, the query, and the retrieved chunks |
| `crm_upsert` | Insert or detect a company by normalized domain |

A find-leads sentence is read into count, place, remote, role, sector, and signal. Code builds the search phrase from those slots. Words such as hiring, developers, engineers, and devs select hiring, unless the sentence is about funding or a launch. When a hiring search keeps no company, the app reads a public startup list and marks those cards `funding`.

`matched_service` is exactly one of:

- product engineering
- dedicated squads
- MVP build
- React / frontend
- backend and APIs
- mobile
- AI / ML implementation

Staff augmentation is not an allowed line. Do not invent a service outside this list.

### 7.3 Lead cards and drafts

Show every lead the tools return, up to the cap. Write a draft only when `fit_score >= 60`. A lead under 60 still appears, without a draft.

If the query gives a count, use that count. Otherwise return 5. Never return more than 10, matching `max_results` on the search tools.

If the query names a signal, search for that signal. Otherwise prefer hiring, then funding, then launch. Every lead needs one public http(s) evidence URL.

`LeadCard` fields: company, signal (`hiring`, `funding`, or `launch`), `evidence_url`, `fit_score` (0–100), `matched_service`, reasoning.

`OutreachDraft` fields: company, subject, body, `personalization_hooks`, `case_study_used`, status. New drafts start at `pending_approval`. Later statuses are `approved` and `rejected`.

Draft voice:

- Generic Webknot sign-off. No personal name and no job title.
- English only.
- About 120–160 words, direct tone.
- One ask: a 20-minute call.
- No pricing and no invented metrics.
- `case_study_used` is empty when the only supporting chunk is `sample=true`.

### 7.4 Judge

The judge runs after outreach and before guardrails. It scores relevance and flags claims that are not supported by the retrieved chunks or the evidence URL.

A weak score or an unsupported claim stays on the trace. The draft remains `pending_approval`. The judge does not rewrite the draft and does not block approval. There is no numeric cutoff.

### 7.5 Guardrails and approval

Guardrails append this sentence verbatim. The model must not rewrite it:

> If you'd rather not hear from Webknot, reply 'stop' and we won't contact this address again.

Guardrails also strip text that looks like a personal email address or phone number.

The Streamlit screen shows the route, the reason, the per-node trace, the lead cards, and the drafts. The person can edit subject and body, then approve or reject.

- Approve stores the edited text and sets status to `approved`.
- Reject sets status to `rejected`.
- There is no mailto link, no SMTP send, and no clipboard step.

### 7.6 Dedupe

SQLite keys on the normalized company domain. A new draft for that domain is skipped while the last contact row is less than 90 days old, and the trace says why. After 90 days a new draft is allowed. Rejected rows count as contact for this window. Approving or rejecting does not delete the lead. CSV export remains available.

## 8. UI

One Streamlit page:

- Query box, including the three rubric queries.
- Decision route, reason, and confidence.
- Intent and rationale.
- Expandable trace, one event per node.
- Lead cards appear as soon as search and scoring finish. Emails are written after that.
- Each card shows signal, fit score, matched service, and reasoning. A hiring card has a Job hiring page button. Funding and launch cards use Funding page and Launch page. The same button is on the draft.
- Drafts with editable subject and body, hooks, case study used, and approve / reject.
- CRM table and CSV export.

Placeholder or sample results must be labeled as such whenever the live tools are not the source.

## 9. Eval bar

Routing tests already cover the three queries with the model off. A passing product eval also checks the answer:

| Case | Pass |
| --- | --- |
| Retrieval — logistics case study | Says the corpus has no real case study. Does not offer the sample as client work. |
| Tool — five Bengaluru fintech React roles | Returns up to 5 `LeadCard`s. Each card has an http(s) evidence URL. Drafts exist only for scores of 60 or higher. |
| Direct — cold email subject line | Answers the question. Returns no lead cards and no draft. |

## 10. Out of scope

- Sending email, sequences, or follow-ups.
- Scraping personal emails, phone numbers, or non-public profiles.
- Multi-user auth, hosted deployment, or a shared CRM.
- Auto-approval, even when the judge score is high.
- Citing `sample=true` corpus rows as real Webknot work.
- LinkedIn, people databases, and login-gated job boards.

## 11. What is in the tree

Sections 7 through 9 match the code. [architecture.md](architecture.md) is the map of the running app.

The lead screen shows the slots that were searched. With `USE_LLM=true`, a search-brief, draft, or judge reply that fails its check is tried once more, then the fixed baseline is used and the trace records `fallback: true`.
