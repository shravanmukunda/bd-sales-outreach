# Docs

The product contract is [Decisions.md](../Decisions.md) and [PRD.md](../PRD.md). How the pieces fit is [architecture.md](../architecture.md). This folder is the build sequence.

There are **seven phases**. Each one leaves the app runnable with `USE_LLM=false` and the routing tests green. Live company search waits until the draft rule, the service list, and the 90-day window are already true on placeholder data. That keeps a real company from receiving a draft just because a stub scored it 70.

| Phase | Doc | Status | Outcome |
| --- | --- | --- | --- |
| 1 | [phase-1-scaffolding.md](phase-1-scaffolding.md) | Built | Compiling graph, schemas, both chunkers, tool stubs, Streamlit trace, SQLite, routing tests |
| 2 | [phase-2-lead-policy.md](phase-2-lead-policy.md) | Built | Honest case-study answer, allowed service lines, score after retrieval, draft only at fit ≥ 60, 90-day dedupe, verbatim opt-out, one retry then a traced baseline |
| 3 | [phase-3-live-search.md](phase-3-live-search.md) | Built | DuckDuckGo for web and job/news search, one public page fetch, requested count, signal order. An empty hiring search reads a public startup list |
| 4 | [phase-4-grounded-drafts.md](phase-4-grounded-drafts.md) | Built | 120–160 words, one 20-minute-call ask, generic sign-off, sample case studies left uncited |
| 5 | [phase-5-judge.md](phase-5-judge.md) | Built | Relevance and unsupported-claim notes on the trace. Drafts stay `pending_approval` |
| 6 | [phase-6-approval-and-eval.md](phase-6-approval-and-eval.md) | Built | Edited subject and body stored on approve. The three rubric answers checked end to end |
| 7 | [phase-7-search-brief.md](phase-7-search-brief.md) | Built | A find-leads sentence is read into slots. The search phrase is built from those slots |

Build them in that order. Phases 1–7 are in the tree. The order used to land phase 2 is [implementation-plan-phase-2.md](implementation-plan-phase-2.md). Each later phase assumes the one before it is in the tree.
