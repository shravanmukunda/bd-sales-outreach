# Phase 4 — Grounded drafts

**Status:** Spec written. Build after phase 3.  
**Decisions:** D12, and the draft half of D17.  
**Depends on:** [phase-2-lead-policy.md](phase-2-lead-policy.md) for the draft gate, the service enum, and `invoke_or_baseline`. [phase-3-live-search.md](phase-3-live-search.md) for real evidence URLs. The writer also has to pass on the offline fixture.  
**Spec:** [PRD.md](../PRD.md) section 7.3, [architecture.md](../architecture.md) section 7.

Phase 4 replaces the placeholder body with a draft a person can edit. The deterministic writer meets the voice rules by itself, because `USE_LLM=false` is how tests and the default app run. When the chat model is on, the same rules are a validator around `llama3`. A draft that fails them is discarded and the baseline writer is used.

Guardrails still own the opt-out sentence. The writer does not append it. The judge still does not rewrite the body. That is phase 5.

## Done when

- Each new draft body is 120–160 words, English, and ends with the sign-off `Webknot Technologies`.
- The body contains the phrase `20-minute call` exactly once.
- The subject names the company or the signal, is at most 80 characters, and does not contain `Webknot`.
- The body contains no price and no metric that was not already in the evidence snippet or a non-sample chunk.
- `case_study_used` is empty when `usable_case_study` returns nothing. The sample logistics story is not quoted.
- `personalization_hooks` includes the public signal. A non-sample case study adds a second hook.
- With `USE_LLM=true`, a model draft that fails validation is retried once and then replaced by the baseline. The outreach trace records `fallback: true`.
- A `placeholder=true` hit is still drafted when its score is at least 60, and the subject starts with `[sample]`.
- Cards under 60 still appear with no draft.

## What the writer receives

`build_draft` takes the scored `LeadCard`, the evidence snippet, the retrieved chunks, and `placeholder: bool`. It returns an `OutreachDraft` at `pending_approval`.

The email may use:

- Company name, signal, evidence URL, fit reasoning, and `matched_service`.
- The one-sentence service blurbs in the writer module, one per allowed line. Those blurbs are the D11 list, written for this node, and they contain no numbers.
- A non-sample chunk’s text when `usable_case_study` returns that chunk’s source.

The email may not use the Parcel North story, any other `sample=true` chunk, a person’s name, a job title, a price, or a result figure that is not in the snippet or a non-sample chunk.

## Baseline outline

The baseline is a fixed outline filled from those fields. Word count is the number of whitespace-separated tokens in the body the writer returns, before guardrails run.

1. Opening to the company team, naming the signal and the evidence URL.
2. One sentence that ties `matched_service` to that signal, using that line’s blurb.
3. Either one sentence pointing at `case_study_used`, or one sentence saying no client case study is attached.
4. The single ask: a `20-minute call`.
5. Last line: `Webknot Technologies`.

The outline is padded with the blurb and the signal sentence until it reaches 120 words, and it stops before 161. The ask sentence appears once, so padding must not repeat it.

Subject shape: `{Signal} at {company}` truncated to 80 characters, or `{company} {signal}` when that is shorter and still names one of the two. When `placeholder` is true, prefix `[sample] ` and keep the 80-character cap after the prefix.

Hooks:

- `Public signal: {signal} ({evidence_url})`
- `Case study on file: {source}` only when `case_study_used` is set

## Model path

When `USE_LLM=true`, outreach calls `invoke_or_baseline` with a `DraftCopy` model: `subject`, `body`, `personalization_hooks`, `case_study_used`. The prompt includes the allowed fields, the seven service names, the word range, the single ask, the sign-off, and the instruction to leave `case_study_used` null when no non-sample case study was retrieved.

After a schema-valid model reply, run `accept_draft`. Failure raises, which is how the helper treats a bad payload: one retry, then the baseline, then `fallback: true` on the outreach trace.

`accept_draft` requires all of the following:

| Check | Rule |
| --- | --- |
| Length | 120–160 words in `body` |
| Ask | `20-minute call` exactly once |
| Sign-off | The last non-empty line is `Webknot Technologies` |
| Subject | 1–80 characters, contains the company or the signal, and does not contain `Webknot` |
| Money and invented metrics | `$`, `₹`, `€`, `%`, `pricing`, and `per hour` are absent unless that same token appears in the snippet or a non-sample chunk |
| Case study | `case_study_used` equals `usable_case_study(chunks)` or is null. A sample filename fails the check |
| Sample label | When `placeholder` is true, the subject starts with `[sample]` |

The status written to state is always `pending_approval`, including when the model returned another status.

## Tests

Use the offline search fixture from phase 3, plus direct calls to `build_draft` and `accept_draft`.

| Case | Expectation |
| --- | --- |
| Rubric lead, `placeholder=false`, sample-only chunks | Word count 120–160, one `20-minute call`, sign-off present, `case_study_used` is null, body does not contain `Parcel North` |
| Same lead with `placeholder=true` | Subject starts with `[sample]` |
| Fit 50 and fit 80 in one outreach call | One draft, two lead cards |
| `usable_case_study` returns `case_study_logistics.md` with `sample=false` on that chunk | `case_study_used` is that filename and the second hook is present |
| Model reply with a price and a 40-word body, `structured_invoke` returning that twice | Baseline draft is kept, outreach trace has `fallback: true`, and `structured_invoke` was called twice |
| Guardrails on the new body | The D18 sentence is appended once. The writer’s word count is unchanged by that assertion (count before guardrails) |

## Files

| File | Change |
| --- | --- |
| `graph/nodes/outreach.py` | Baseline outline, blurbs, `accept_draft`, `invoke_or_baseline` for the model path |
| `schemas/outreach.py` | `DraftCopy` if it should live beside `OutreachDraft`. Status is still applied by the node |
| `tests/test_drafts.py` | Voice, sample citation, fallback |

`graph/llm.py` stays the phase 2 helper. This phase only calls it.

## Out of this phase

| Left for | Work |
| --- | --- |
| Phase 5 | Relevance and unsupported-claim notes. The body above is the body the judge reads |
| Phase 6 | Persisting the operator’s edited subject and body |

Approve and reject still update status only, until phase 6.
