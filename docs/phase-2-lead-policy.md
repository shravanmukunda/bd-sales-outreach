# Phase 2 — Lead policy and honest retrieval

**Status:** Built. Phase 1 is done.  
**Decisions:** D9, D11, the draft gate and the count cap from D13, D14, the retry rule from D17, the opt-out sentence from D18.  
**Depends on:** [phase-1-scaffolding.md](phase-1-scaffolding.md).  
**Spec:** [PRD.md](../PRD.md) sections 6, 7.1, 7.3, 7.5, 7.6, and [architecture.md](../architecture.md) sections 3, 6, 7, and 8.

Phase 2 makes the offline graph obey the product rules. Search stays on the fictional `example.com` hits. Fit, the service line, the draft gate, dedupe, the case-study answer, the opt-out line, and the model fallback become real. Phase 3 can then replace the hits without inventing a second set of rules.

`pytest` still runs with `USE_LLM=false`. The temp CRM and empty Chroma directory from `tests/conftest.py` stay in place.

## Done when

- The logistics case-study answer says the corpus has no real case study, and any quoted sample chunk is labeled as sample.
- `matched_service` accepts only the seven allowed lines. The React rubric query maps to `React / frontend`.
- `score_lead` runs after `retrieve`, and the score depends on the evidence and the chunks.
- Every returned lead is shown. A draft is created only when `fit_score >= 60`.
- A query count is honored from 1 to 10. A missing count means 5.
- A domain contacted less than 90 days ago gets no new draft, including when the row is `rejected`. After 90 days a new draft is allowed. The trace says which rule fired.
- Guardrails append the D18 sentence verbatim.
- A structured-output failure retries once, then uses the baseline, and the trace records that fallback.
- The three rubric routes and node orders from phase 1 still pass.

## Query parsing

Add `parse_lead_request(query) -> LeadRequest` next to the tool node. `LeadRequest` is a small Pydantic model: `count` (int, 1–10), `location` (str or null), `signal` (`hiring`, `funding`, `launch`, or null).

| Input | Result |
| --- | --- |
| “Find 5 fintech startups hiring React developers in Bengaluru” | count 5, location Bengaluru, signal hiring |
| “Find 3 logistics companies” | count 3, location null, signal null |
| “Find 12 fintech startups” | count 10 |
| “Find fintech startups” | count 5 |
| “bangalore” in the query | location Bengaluru |

`count` is the first integer in the query, clamped to 1–10. The tool node passes it as `max_results` on `search_jobs_or_news`. The placeholder list already slices to `max_results`, so “Find 3 …” returns three cards.

`signal` is stored on the trace in this phase and consumed by the live search in phase 3. The placeholder list is a fixed mix of hiring, funding, and launch, so filtering it would make the “find 5 … hiring” query return fewer than five cards. Leave the placeholder mix intact.

## Scoring moves behind retrieval

On `find_leads` the tool node only calls `search_jobs_or_news` and stores the output in `tool_results`. It does not call `score_lead` and it does not write `leads`.

`research_company` is unchanged: `web_search`, then `fetch_company_page`, then retrieve, then respond. No cards and no drafts.

The outreach node, which already runs after retrieve, scores each job/news hit:

1. Read `retrieved_chunks` from state.
2. Call `score_lead` with the company, signal, evidence URL, snippet, and those chunks.
3. Append every `LeadCard` to `leads`.
4. Draft only when `fit_score >= 60` and dedupe allows it.

`score_lead` stops copying `fit_score` and `matched_service` off the input. The input keeps the company, signal, URL, and snippet. Add an optional `chunks` field (list of the chunk dicts already on state). The output `LeadCard` is what the scorer decided. `placeholder` stays true while the hits are the fictional list, and the reasoning still starts with `PLACEHOLDER` so the UI warning remains true.

### Service line

Add `MatchedService` in `schemas/lead.py` and type `LeadCard.matched_service` with it. The values are:

- product engineering
- dedicated squads
- MVP build
- React / frontend
- backend and APIs
- mobile
- AI / ML implementation

Selection uses the query and the snippet, first match wins:

| Keywords | Line |
| --- | --- |
| react, frontend, front-end, front end | React / frontend |
| ios, android, mobile | mobile |
| api, backend, back-end, node | backend and APIs |
| mvp | MVP build |
| dedicated, squad | dedicated squads |
| ai, ml, machine learning | AI / ML implementation |
| anything else | product engineering |

### Fit score

Deterministic, capped at 100. The same function runs when `USE_LLM=false`. Phase 5 may add a model score. This formula stays the baseline.

| Condition | Points |
| --- | --- |
| http(s) evidence URL and a signal | 50 |
| Query or snippet contains the keywords of the chosen service | 20 |
| A retrieved chunk has the same `industry` as the query, or its `service` equals the chosen line | 15 |
| Signal is `hiring` | 10 |

An empty snippet with no supporting chunk scores 50. That card is shown and gets no draft. The placeholder snippets include the query text, so the React rubric hits include the service bonus. Hiring placeholders land at 80 or higher and still draft. Funding and launch placeholders that match a service land at 70 and still draft.

Sample chunks may contribute the industry or service bonus. They still must not be copied into `case_study_used`. That rule from phase 1 stays.

## Dedupe window

`should_skip(company) -> tuple[bool, str]` reads `updated_at`.

- No row: do not skip. Reason is empty.
- Row with `updated_at` younger than 90 days: skip. Reason names the company, the status, and that the 90-day window is still open. `rejected` counts the same as `pending_approval` and `approved`.
- Row 90 days or older: do not skip. Reason says the window has expired.

Compare timezone-aware UTC datetimes. The window is 90 × 24 hours.

When a draft is created and the domain is new, `crm_upsert` inserts `pending_approval` as it does now. When a draft is created because the window expired, update that row: status `pending_approval`, `updated_at` now, note `draft created`. Add `refresh_contact` on the CRM module for that update so `crm_upsert` can keep meaning “insert, or report an existing row.”

The outreach trace keeps a skipped list. Each entry has company, status, and the reason string. The existing “already in the CRM” wording becomes the 90-day reason, and `tests/test_routing.py` should assert that reason.

## Case-study answer

In `respond`, when the route is `retrieve` and the query asks for a Webknot case study:

- The answer states that the corpus has no real case study yet.
- If a sample chunk is listed, the line marks it as sample data.
- The answer does not describe the logistics file as a client engagement.

`_chunk_lines` already appends “(sample seed, not a real engagement)”. Keep that, and add the explicit sentence above it. This holds while every case-study chunk is `sample=true`. When a future file is ingested with `sample=false`, the same branch may name that file. Phase 2 does not add that file.

## Opt-out sentence

Replace `OPT_OUT_LINE` in `graph/nodes/guardrails.py` with this sentence, verbatim:

> If you'd rather not hear from Webknot, reply 'stop' and we won't contact this address again.

Append it once, after redaction. Detection of an existing opt-out looks for this sentence, not for the shorter “reply stop” phrase. Email and phone redaction stay as they are.

## Structured-output fallback

Add `invoke_or_baseline` in `graph/llm.py`. Callers pass the schema, the prompt, and a zero-arg baseline callable.

1. When `USE_LLM` is false, call the baseline and return `(value, fallback=False)`.
2. When it is true, call `structured_invoke`. On success, return `(value, fallback=False)`.
3. On failure, call `structured_invoke` one more time.
4. If the second call fails or does not validate, call the baseline and return `(value, fallback=True)`.

`classify_intent` and `decide` use this helper. `classify_node` and `decide_node` write `fallback: true` on their trace event when the flag is set, plus a message that the baseline was used after a failed retry. Draft and judge keep their phase 1 bodies. They will call the same helper in phases 4 and 5.

Tests can force the failure path by monkeypatching `structured_invoke` to raise and setting `use_llm` true on the settings object. Assert two attempts, a baseline `Decision` or `Intent`, and `fallback: true` on the trace. The default test fixture leaves `use_llm` false, so the rubric tests still make zero chat calls.

## Files

| File | Change |
| --- | --- |
| `schemas/lead.py` | `MatchedService` enum. `LeadCard.matched_service` uses it |
| `schemas/tool_io.py` | `ScoreLeadInput` takes chunks and stops requiring a caller-supplied score and service |
| `tools/lead_scorer.py` | Keyword service choice and the point table |
| `graph/nodes/tool_node.py` | Parse the lead request. Search only. Pass `max_results` |
| `graph/nodes/outreach.py` | Score hits, keep every card, draft only at ≥ 60, honor the 90-day window |
| `memory/dedupe.py` | 90-day `should_skip` |
| `tools/crm.py` | `refresh_contact` for an expired window |
| `graph/nodes/respond.py` | No-real-case-study sentence |
| `graph/nodes/guardrails.py` | Verbatim opt-out sentence |
| `graph/llm.py` | `invoke_or_baseline` |
| `graph/router.py` | Classify and decide go through the helper |
| `graph/nodes/classify.py`, `decide.py` | Trace the fallback flag |
| `tests/test_routing.py`, `tests/test_schemas.py` | Expectations below |

## Tests to change or add

Existing tests that encode phase 1 stubs need new expectations:

| Test | New expectation |
| --- | --- |
| Tool-path placeholder run | Still 5 leads for the rubric query. `matched_service` is `React / frontend`. Fit follows the point table and is ≥ 60. Reasoning still starts with `PLACEHOLDER`. Five drafts, each `pending_approval`, `case_study_used` is null |
| Second run of the same query | No new drafts. Trace reason says the 90-day window is still open |
| Guardrail tests | Body contains the full D18 sentence once. Personal email and phone are still removed |

Add:

- “Find 3 fintech startups” returns 3 leads.
- “Find 12 …” returns 10.
- `score_lead` with an empty snippet and no chunks returns fit 50 and an allowed service. Outreach given that card, and one card at 80, writes a single draft and still returns both leads.
- A CRM row with `updated_at` 91 days ago and status `rejected` allows a new draft. A row 1 day old with status `rejected` does not.
- Logistics query answer contains “no real case study” and does not present the sample as client work.
- `invoke_or_baseline` retries once and then returns the baseline with `fallback=True`. The classify or decide trace shows it.

## Out of this phase

| Left for | Work |
| --- | --- |
| [Phase 3](phase-3-live-search.md) | DuckDuckGo, `fetch_company_page` over HTTP, `placeholder=false` on live hits, signal preference applied to real results. `search_provider` stops reporting Tavily |
| [Phase 4](phase-4-grounded-drafts.md) | Draft body of 120–160 words, one 20-minute-call ask, generic Webknot sign-off. The placeholder body stays until then |
| [Phase 5](phase-5-judge.md) | Judge scores and unsupported-claim flags |
| [Phase 6](phase-6-approval-and-eval.md) | Editable subject and body stored on approve. Full answer-level eval of all three rubric queries |

Until phase 3, the Streamlit tool-route warning stays. Cards are still fictional.
