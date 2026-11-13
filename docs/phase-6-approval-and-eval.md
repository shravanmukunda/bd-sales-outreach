# Phase 6 — Approval and product eval

**Status:** Built. Phase 5 is in the tree. The six-phase sequence is complete.  
**Decisions:** D15, and the eval bar in D18.  
**Depends on:** [phase-2-lead-policy.md](phase-2-lead-policy.md) for the case-study sentence, the draft gate, and the opt-out line. [phase-4-grounded-drafts.md](phase-4-grounded-drafts.md) for the body the operator edits. [phase-5-judge.md](phase-5-judge.md) for the notes that sit beside that draft. Live search from [phase-3-live-search.md](phase-3-live-search.md) is on in the app. The eval suite uses the offline fixture.  
**Spec:** [PRD.md](../PRD.md) sections 7.5, 8, and 9, [architecture.md](../architecture.md) sections 8, 9, and 11.

This phase is the human loop and the check that the three rubric queries meet the product bar, not only the route bar. Approve writes the edited subject and body into SQLite and sets `approved`. Reject sets `rejected`. The app still has no send step.

## Done when

- The draft card has an editable subject and an editable body.
- Approve persists that subject and body, sets status to `approved`, and updates `updated_at`.
- Reject sets status to `rejected` and leaves the previous stored subject and body as they were.
- An empty subject or an empty body does not write an approval.
- CSV export includes `subject` and `body`.
- The three eval cases in the table below pass with `USE_LLM=false`, the offline search fixture, and no Ollama call.
- The page has no mailto link, no SMTP call, and no clipboard button.

## CRM columns

The `companies` table gains two text columns, `subject` and `body`, defaulting to empty. On startup, `connect` runs `ALTER TABLE` for each column when `PRAGMA table_info` shows it is missing, so an existing `data/crm.sqlite` from earlier phases keeps its rows.

| Column | Written by approve | Written by reject |
| --- | --- | --- |
| `status` | `approved` | `rejected` |
| `updated_at` | now, UTC | now, UTC |
| `subject` | the edited subject | unchanged |
| `body` | the edited body, including the opt-out sentence if it is still in the editor | unchanged |
| `note` | `approved` | `rejected` |

`set_status` remains the status-only writer for callers that have no text. Add `approve_draft(company, subject, body) -> str` and `reject_draft(company) -> str`. Both key off `normalize_domain`. Approving a company that has no row inserts one, matching the current `set_status` insert path, so a draft that was edited before the upsert is not dropped.

`export_csv` fieldnames become `domain`, `company`, `status`, `subject`, `body`, `updated_at`, `note`.

Approving or rejecting does not delete the row. The 90-day window from phase 2 still treats both statuses as contact.

## Streamlit

On each draft card:

- `st.text_input` for the subject, initial value the draft subject.
- `st.text_area` for the body, initial value the draft body.
- Approve calls `approve_draft` with the current contents of those widgets, then sets the session draft’s status, subject, and body from what was saved, then reruns.
- Reject calls `reject_draft`, sets status to `rejected`, and reruns. The widgets can differ from the stored text after a reject. The stored text stays the last approved text, or the original draft text if nobody has approved it.
- If the stripped subject or the stripped body is empty, Approve shows an error on the card and does not call `approve_draft`.

Widget keys include the company and the status so a rerun after approve does not reuse the pre-edit widget state for a different status.

The judge notes are already visible in the trace expander. Leave them there. Do not add a second approval gate based on relevance.

Keep the placeholder banner behavior from phase 3. A `[sample]` subject from phase 4 is editable, and approve stores it with the prefix if the operator leaves the prefix in place.

There is no mailto link, no `smtplib` import, and no copy-to-clipboard control.

## Product eval

Add `tests/test_eval.py`. It runs the three queries in `evals/queries.py` through `run_query`, with the phase 3 fixture and `USE_LLM=false`.

| Case | Pass |
| --- | --- |
| Which Webknot case study fits a logistics company? | Route `retrieve`. The answer says there is no real case study. It does not describe the sample as a client engagement. `leads` and `drafts` are empty |
| Find 5 fintech startups hiring React developers in Bengaluru | Route `tool`. Up to 5 lead cards. Each `evidence_url` is http(s). Every card with `fit_score >= 60` has one draft, and every card under 60 has none. Draft status is `pending_approval`. The body contains the D18 opt-out sentence. `case_study_used` is null on the sample corpus |
| What makes a good cold email subject line? | Route `direct`. The answer describes a specific subject line tied to a public signal. `leads` and `drafts` are empty |

The fixture’s hiring cards score at or above 60, so the tool case still expects a draft per card, up to five. Add one eval-adjacent test that passes a fit-50 card through outreach and asserts the eval rule in isolation: the card is present and the draft list omits it. That locks the gate even though the fixture itself does not contain a weak lead.

Route and node-order assertions from `tests/test_routing.py` stay. `test_eval.py` is the answer bar.

Also test the CRM functions without Streamlit:

| Case | Expectation |
| --- | --- |
| `approve_draft("Northwind Pay", "Hiring at Northwind Pay", "<edited body>")` | Row status `approved`, subject and body match the arguments |
| Second approve with new text | Subject and body replaced, status stays `approved` |
| `reject_draft` after an insert | Status `rejected`, subject and body unchanged |
| `approve_draft` with a blank subject | Raises `ValueError`, and the row is unchanged |
| CSV export | Header contains `subject` and `body`, and the approved text is in the file |

## Files

| File | Change |
| --- | --- |
| `tools/crm.py` | Column migration, `approve_draft`, `reject_draft`, CSV columns |
| `ui/app.py` | Subject input, body area, save edited text, empty-field error |
| `tests/test_eval.py` | The three rubric answers |
| `tests/test_schemas.py` | Approval persistence and CSV columns |

## After this phase

The six-phase sequence is complete. The operator can search public signals, read a grounded draft, see judge notes, edit the text, and approve or reject it. The approved text sits in `data/crm.sqlite` and in the CSV export. Sending mail stays outside the product.
