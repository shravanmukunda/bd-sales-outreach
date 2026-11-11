# Implementation plan through phase 2

**Stop line:** Phase 2 done, `pytest` green, `USE_LLM=false`. Do not start [phase 3](phase-3-live-search.md).  
**Spec:** [phase-2-lead-policy.md](phase-2-lead-policy.md). Phase 1 is already built. This plan is the order to land phase 2 on the current tree.  
**Check after every step:** `pytest` from the repo root, with `.venv` active. The fixture in `tests/conftest.py` keeps the CRM and Chroma in a temp directory and forces `use_llm=false`.

Phase 1 stays as it is except where a step below edits a file. Search hits stay the fictional `example.com` list. The Streamlit banner that those cards are fictional stays.

## What is already true

Leave these alone:

- Graph shape and node order in `graph/builder.py`.
- Routing baselines in `graph/router.py` (`baseline_intent`, `baseline_decision`).
- Chunkers, ingest, retriever, and `tests/test_chunking.py`.
- Placeholder search and page fetch. They still do not call the network.
- `usable_case_study` and the rule that a `sample=true` chunk never fills `case_study_used`.
- Judge node. It still records `not_scored` and does not change drafts.
- Approve and reject. They still update status only.

## Order

Six steps. Each one is small enough to review on its own. Schema breaks and their callers land in the same step so `pytest` is never run against a half-updated import.

### 1. Opt-out sentence

`graph/nodes/guardrails.py`

- Set `OPT_OUT_LINE` to: `If you'd rather not hear from Webknot, reply 'stop' and we won't contact this address again.`
- `ensure_opt_out` treats the draft as already opted-out only when that full sentence is present. The old substring `reply stop` does not match the new sentence, because of the quotes around `stop`.

Update the three assertions that look for `reply stop`:

- `tests/test_routing.py`: the tool-path draft check, and `test_guardrails_node_rewrites_a_dirty_draft`
- `tests/test_schemas.py`: `test_guardrails_redact_contact_details_and_keep_opt_out_once`

Assert the full sentence once. Keep the email and phone redaction checks.

### 2. Case-study answer

`graph/nodes/respond.py`, in `_answer`, when the route is `retrieve` and `"case study"` is in the query.

- Add the sentence `The corpus has no real case study yet.`
- Tests run against an empty Chroma directory, so this sentence has to appear even when `retrieved_chunks` is empty.
- Keep the existing sample label in `_chunk_lines`. With no chunks, that label simply does not appear.
- Do not describe `case_study_logistics.md` or Parcel North as client work. The empty-store path already avoids that. Leave it that way.

Add a routing test on `Which Webknot case study fits a logistics company?`: the answer contains `no real case study`, `leads` and `drafts` are empty, and the route is still `retrieve`.

### 3. Structured-output retry

`graph/llm.py`

```text
invoke_or_baseline(schema, prompt, baseline) -> tuple[BaseModel, bool]
```

`baseline` is a zero-arg callable returning the schema.

| `settings.use_llm` | Behavior | Second value |
| --- | --- | --- |
| false | Call `baseline` only. Do not import or call the chat model | `False` |
| true, first call validates | Return that value | `False` |
| true, first call raises or fails validation | Call `structured_invoke` once more | |
| true, second call validates | Return that value | `False` |
| true, second call fails | Return `baseline()` | `True` |

Validate with `schema.model_validate` when the client returns a dict. An instance of `schema` is already valid.

`graph/router.py`: `classify_intent` and `decide` call the helper and return `(model, fallback)`. `baseline_intent` and `baseline_decision` stay the callables passed in. Their keyword rules do not change.

`graph/nodes/classify.py` and `decide.py`: unpack the tuple. Put `fallback` on the trace `data`. When it is true, the trace message says the baseline was used after structured output failed twice. When it is false, keep today's message (rationale or reason).

Outreach and the judge do not call the helper in this phase.

New test, with `settings.use_llm` monkeypatched to true and `structured_invoke` monkeypatched to raise:

- The mock was called twice.
- The result is the baseline intent or decision.
- `fallback` is true.
- A classify or decide trace event records `fallback: true`.

The default fixture stays `use_llm=false`. The rubric tests still make zero chat calls.

### 4. Count, location, and signal

Add `LeadRequest` in `schemas/tool_io.py`: `count` (1–10), `location` (str or null), `signal` (`hiring`, `funding`, `launch`, or null).

Add `parse_lead_request` in `graph/nodes/tool_node.py`.

| Rule | Result |
| --- | --- |
| First integer in the query, clamped to 1–10 | `count`. No integer means 5. `0` becomes 1. `12` becomes 10 |
| `bengaluru` or `bangalore` | `location="Bengaluru"` |
| First of `hiring`, `funding`, `launch` in the query text | `signal`. None of them means null |

`tool_node` passes `count` as `max_results` and `location` into `JobNewsSearchInput`. Put `count`, `location`, and `signal` on the tool trace `data`. Do not filter the placeholder list by signal. Phase 3 does that against live results. Filtering now would turn the “find 5 … hiring” query into two cards.

This step still scores inside the tool node at fit 70. That move is step 5.

Tests:

- `Find 3 fintech startups` returns 3 leads.
- `Find 12 fintech startups` returns 10 leads.
- The rubric query still returns 5, with location Bengaluru and signal hiring on the tool trace.

### 5. Service enum, and scoring after retrieve

This step moves fit off the tool node. Land the schema, the scorer, the tool node, and the outreach node together.

`schemas/lead.py`: add `MatchedService` with the seven D11 values, and type `LeadCard.matched_service` as that enum. Export it from `schemas/__init__.py`.

`schemas/tool_io.py`: `ScoreLeadInput` keeps `company`, `signal`, `evidence_url`, and `snippet`. Add `query: str = ""` and `chunks: list[dict] = []`. Remove `fit_score` and `matched_service`. The only production caller today is `tool_node`, and this step deletes that call.

`tools/lead_scorer.py` decides both fields. Match keywords with word boundaries, in this order, against `query + " " + snippet`. First hit wins. `ai` must not match inside another word.

| Pattern | Line |
| --- | --- |
| `react`, `frontend`, `front-end`, `front end` | React / frontend |
| `ios`, `android`, `mobile` | mobile |
| `api`, `backend`, `back-end`, `node` | backend and APIs |
| `mvp` | MVP build |
| `dedicated`, `squad` | dedicated squads |
| `ai`, `ml`, `machine learning` | AI / ML implementation |
| no hit | product engineering |

Points, capped at 100:

| Condition | Points |
| --- | --- |
| http(s) evidence URL and a signal | 50 |
| Query or snippet hits the chosen service's keywords | 20 |
| A chunk's `industry` equals the industry detected on the query, or its `service` equals the chosen line | 15 |
| Signal is `hiring` | 10 |

Reasoning still starts with `PLACEHOLDER`. `ScoreLeadOutput.placeholder` stays true.

`tool_node` on `find_leads` only calls `search_jobs_or_news` and appends that output to `tool_results`. It does not write `leads`. `research_company` is unchanged: search, fetch, no cards, no drafts.

`outreach_node` then:

1. Read the `search_jobs_or_news` output from `tool_results`.
2. For each hit, call `score_lead` with the hit fields, `state["query"]`, and `state["retrieved_chunks"]`.
3. Put every card on `leads`.
4. Draft only when `fit_score >= 60` and dedupe allows it.

The `draft_outreach` path has no search hits. Keep today's branch: one draft built from the query, no lead card, no fit gate. `test_research_stops_before_outreach_and_draft_request_does_not` depends on that. Dedupe still applies. An empty evidence string stays off `LeadCard`, because that model requires an http URL.

Pytest chroma is empty, and the placeholder snippet contains the operator query, so the rubric cards score as follows:

| Placeholder signal | Score | Draft |
| --- | --- | --- |
| hiring (Northwind Pay, Sable Mint) | 80 | yes |
| funding (Harbor Ledger, Brightline Kash) | 70 | yes |
| launch (Koel Checkout) | 70 | yes |

`matched_service` on all five is `React / frontend`.

Replace `assert fit_score == 70` in `test_tool_path_drafts_placeholders_once_then_dedupes` with those scores and the service line. Keep five leads, five drafts, `PLACEHOLDER` reasoning, `example.com` URLs, `pending_approval`, and `case_study_used is None`.

Add a direct test that does not go through the placeholder list:

- `score_lead` with an empty snippet, an empty query, and no chunks returns fit 50 and `product engineering`.
- `outreach_node` given one pre-scored card at 50 and one at 80 returns both leads and one draft. Build that state without `tool_results` search hits, and pass the cards in `leads`, so this test covers the gate itself. If outreach only scores from `tool_results`, have it draft from cards already on `leads` when their fit is at least 60, and still return every card. That keeps the gate testable without a second search.

### 6. Ninety-day dedupe

`memory/dedupe.py` and `tools/crm.py`.

`should_skip(company) -> tuple[bool, str]` reads `updated_at` as a timezone-aware UTC datetime. The window is `timedelta(days=90)`.

| Row | Skip | Reason contains |
| --- | --- | --- |
| None | no | empty reason |
| `updated_at` younger than 90 days, any status including `rejected` | yes | company, status, and `90-day` |
| `updated_at` 90 days or older | no | `expired` |

`crm_upsert` stays insert-or-report-duplicate. Add `refresh_contact(company, note="draft created")`. It sets status `pending_approval`, `updated_at` to now, and the note. Outreach calls it only when `should_skip` is false and `lookup` already found a row.

Skipped trace entries gain `reason` beside `company` and `status`. The outreach message for a skip says the 90-day window is still open, and names the companies. `respond.py` currently says `already in the CRM` when every lead was skipped. Change that sentence to the same 90-day reason so the answer matches the trace.

`tests/test_routing.py` second-run assertion changes from `already in the CRM` to the 90-day wording.

Add CRM tests on the temp database:

- Insert a row, set `updated_at` to 91 days ago, status `rejected`. The next outreach draft is created, and `refresh_contact` brings status back to `pending_approval`.
- A row with `updated_at` one day ago and status `rejected` produces no draft, and the trace names the open window.

Set `updated_at` with an `UPDATE` in the test. Do not sleep.

## Files touched

| Step | Files |
| --- | --- |
| 1 | `graph/nodes/guardrails.py`, `tests/test_routing.py`, `tests/test_schemas.py` |
| 2 | `graph/nodes/respond.py`, `tests/test_routing.py` |
| 3 | `graph/llm.py`, `graph/router.py`, `graph/nodes/classify.py`, `graph/nodes/decide.py`, a new fallback test in `tests/test_routing.py` or `tests/test_schemas.py` |
| 4 | `schemas/tool_io.py`, `graph/nodes/tool_node.py`, `tests/test_routing.py` |
| 5 | `schemas/lead.py`, `schemas/__init__.py`, `schemas/tool_io.py`, `tools/lead_scorer.py`, `graph/nodes/tool_node.py`, `graph/nodes/outreach.py`, `tests/test_routing.py`, `tests/test_schemas.py` |
| 6 | `memory/dedupe.py`, `tools/crm.py`, `graph/nodes/outreach.py`, `graph/nodes/respond.py`, `tests/test_routing.py`, `tests/test_schemas.py` |

No new dependency. No change to `requirements.txt`, `ui/app.py` beyond the existing placeholder banner, or the judge.

## Exit check

`pytest` passes, and a manual read of one rubric run confirms:

| Query | Still true |
| --- | --- |
| Logistics case study | Route `retrieve`. Answer says there is no real case study. No leads, no drafts |
| Find 5 fintech startups hiring React developers in Bengaluru | Route `tool`, same eight nodes. Five cards, `React / frontend`, scores 80 or 70, five drafts, verbatim opt-out, sample case study unused. Second run drafts nothing and the trace cites the 90-day window |
| Cold email subject line | Route `direct`. No leads, no drafts |

`Find 3` returns three cards. `Find 12` returns ten. An empty-snippet score is 50 and produces no draft.

Then stop. Live DuckDuckGo, the 120–160 word body, judge scores, and storing edited subject and body are phases 3–6.
