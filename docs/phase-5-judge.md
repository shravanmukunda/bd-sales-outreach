# Phase 5 — Judge

**Status:** Spec written. Build after phase 4.  
**Decisions:** D7 and D16.  
**Depends on:** [phase-4-grounded-drafts.md](phase-4-grounded-drafts.md). The judge reads the draft the writer just produced, plus the chunks and the evidence URL.  
**Spec:** [PRD.md](../PRD.md) section 7.4, [architecture.md](../architecture.md) section 7.

The judge runs after outreach and before guardrails. It writes relevance and unsupported-claim notes onto the trace. It does not change the subject, the body, the hooks, or the status. A weak note leaves the draft at `pending_approval`, and the operator can still approve it in phase 6.

Thresholds are qualitative labels, not a cutoff. Nothing in this phase blocks a draft or sends it back to the writer.

The opt-out sentence is not on the body yet, because guardrails append it on the next node. The judge does not look for that sentence and does not add it.

## Done when

- Every draft on the run has one judge note in the trace: company, relevance (`strong`, `adequate`, or `weak`), and a list of unsupported-claim strings.
- The drafts list that enters the judge node is the drafts list that leaves it.
- A sample case study named as client work is an unsupported claim.
- A price or a percent that is not in the evidence snippet or a non-sample chunk is an unsupported claim.
- `USE_LLM=false` uses the baseline below and makes no chat call.
- `USE_LLM=true` uses `invoke_or_baseline`. A failed model reply retries once, then the baseline note is stored with `fallback: true`.
- The node trace status is `scored`, replacing the phase 1 `not_scored` event.

## Note schema

Add `JudgeNote` and `JudgeReport` in `schemas/response.py` (or a new `schemas/judge.py` re-exported from `schemas/__init__.py`).

| Field | Rule |
| --- | --- |
| `company` | The draft’s company |
| `relevance` | `strong`, `adequate`, or `weak` |
| `unsupported_claims` | Short strings a person can check. Empty when nothing failed |

`JudgeReport` is the list of notes, one per draft, in the same order as `state["drafts"]`. The judge node writes the report onto the trace `data` and does not add a new state field. The UI already prints trace `data`, so the notes show up in the existing expander.

## Baseline

For each draft, find the matching `LeadCard` by company. Compare the body and subject with that card’s evidence URL, snippet (from `tool_results`), and `retrieved_chunks`.

Relevance:

| Label | When |
| --- | --- |
| `strong` | Fit is at least 80, the company name is in the body, and the evidence URL is in the body or the hooks |
| `adequate` | Fit is at least 60 and the company name is in the body |
| `weak` | Anything else, including a missing lead card |

Unsupported claims, each appended as its own string when the condition is true:

| Check | Note text |
| --- | --- |
| `case_study_used` is set and that source is missing or `sample=true` in the chunks | `Case study is sample data or missing from the retrieved chunks.` |
| Body contains `Parcel North` | `Body names the sample logistics story.` |
| Body or subject contains `$`, `₹`, `€`, `%`, `pricing`, or `per hour`, and that token is not in the snippet or a non-sample chunk | `Price or metric is not in the evidence or the retrieved text.` |
| A digit sequence of 2 or more digits appears in the body and is not in the evidence URL, the snippet, or a non-sample chunk | `A figure in the draft is not in the evidence or the retrieved text.` |

The service blurbs from phase 4 have no digits, so a baseline draft with sample-only chunks produces an empty claim list and, for a hiring rubric card at fit 80 or above, relevance `strong`. A card at fit 70 with the company name and URL in the body is `adequate`.

The baseline does not call the model. It does not edit the draft.

## Model path

When `USE_LLM=true`, call `invoke_or_baseline` with `JudgeReport`. The prompt includes the drafts, the evidence URLs, the snippets, and the chunk texts with their `sample` flags. It asks for the same labels and for claim strings that quote the unsupported phrase.

`accept_report` checks:

- The note count equals the draft count, and the companies match in order.
- Each relevance is one of the three labels.
- Claim strings are non-empty when present.

A report that fails `accept_report` is a validation failure, so the helper retries once and then stores the baseline report with `fallback: true`.

After either path, copy the drafts through unchanged. Assert this in the node by building the return value without a `drafts` key, so the previous drafts stay on state.

## Tests

| Case | Expectation |
| --- | --- |
| Phase 4 baseline draft for a hiring card at fit 80, sample-only chunks | `strong`, no claim strings, body byte-for-byte unchanged, trace `status` is `scored` |
| Same draft with the fit forced to 70 | `adequate` |
| Body with `Parcel North` and `case_study_used` set to the sample file | Both case-study claim strings, status still `pending_approval` |
| Body containing `30%` with no chunk or snippet containing `30%` | The metric claim is present. The body still contains `30%` afterward |
| No drafts on an ask-Webknot run | The judge node is not on that path (phase 1 route). A direct call of `judge_node` with an empty draft list writes zero notes and `scored` |
| `structured_invoke` raises twice | Baseline note, `fallback: true`, two attempts |

Guardrails tests from phase 2 still see the opt-out sentence added after this node.

## Files

| File | Change |
| --- | --- |
| `schemas/judge.py` | `JudgeNote`, `JudgeReport` |
| `graph/nodes/judge.py` | Baseline checks, model path, trace payload |
| `tests/test_judge.py` | Labels, claim flags, draft unchanged, fallback |

## Out of this phase

Phase 6 stores the operator’s edits and adds the answer-level eval. The judge never sets `approved` or `rejected`, including when relevance is `strong` and the claim list is empty.
