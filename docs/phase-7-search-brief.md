# Phase 7 — Search brief

**Status:** Built. Phase 6 is in the tree.  
**Depends on:** [phase-3-live-search.md](phase-3-live-search.md) for DuckDuckGo, and [phase-1-scaffolding.md](phase-1-scaffolding.md) for `invoke_or_baseline`.  
**Spec:** The capstone asks the agent to turn a natural-language target into a structured tool call. Scoring and approval stay as they are.

A find-leads sentence is read into a `LeadRequest`: count, location, remote, role, sector, and signal. Code builds the DuckDuckGo phrase from those slots. The model does not write the phrase.

## Done when

- `USE_LLM=false` uses the baseline reader and makes no chat call. Default pytest stays offline.
- `USE_LLM=true` asks `llama3` for a `LeadRequest`. A reply that fails the check is tried once, then the baseline is stored and the tool trace sets `fallback: true`.
- The rubric sentence still produces `fintech hiring React developers Bengaluru jobs`.
- "Search me companies hiring Java Spring Boot devs in India" is hiring, role `Java Spring Boot`, location India, and the phrase has no "search me".
- "Search me startups looking for remote devs in Australia" is hiring, remote, and location Australia.
- "What makes a good cold email subject line?" stays a direct answer with no leads.
- The lead screen shows the count, role, sector, place, remote, and signal that were searched. A fallback adds the baseline note.

## Slots

| Slot | Rule |
| --- | --- |
| count | First integer, clamped to 1–10. Default 5 |
| location | Any place. `bangalore` is stored as Bengaluru |
| remote | True only for remote, WFH, or work from home |
| role | Short skill phrase. Trailing "devs" is dropped. "React developers" stays |
| sector | The word before startups, companies, or firms, when it is not filler |
| signal | hiring, funding, or launch. "Looking for", "devs", "developers", "engineers", and "open roles" count as hiring unless the sentence is about funding or a launch |

Phrase order: sector, signal word, role, "remote" when set, location, then `jobs`, `funding`, or `product launch`.

## Route intent

The offline classifier checks a draft-an-email request before a lead request, so "Draft an outreach email…" stays `draft_outreach`. Lead cues now include search, developers, devs, engineers, openings, roles, and "looking for", along with find, hiring, startup, and leads. The classify prompt used when the model is on includes the three rubric sentences and a few BD phrasings. The label set is still the four intents.

## Check

A model reply is rejected when location or role is the whole sentence or still contains "search me" or "find N", when remote is true but the sentence never says remote, or when the sentence is a hiring request and the signal is not hiring. Count and signal still have to satisfy the schema.

The screen line is built from the tool trace. `USE_LLM` stays false for pytest. Start the BD demo with `USE_LLM=true` when the open phrasing should go through `llama3`.

## When the phrase keeps no company

The phrase is still sent once. LinkedIn, Indeed, Naukri, and the other blocked hosts are dropped, and a title such as "Java Developer Jobs in Bengaluru" is not read as a company. If nothing remains, [phase-3-live-search.md](phase-3-live-search.md) reads a public startup list: `top {sector} startups` in the place, then `funded {sector} startups`, with one retry when a list search returns no rows. Those cards are signal `funding`. The brief line on the page still shows the hiring slots the operator asked for.
