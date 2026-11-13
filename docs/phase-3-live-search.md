# Phase 3 — Live public search

**Status:** Built. Phase 2 is in the tree.  
**Decisions:** the live-search half of D13, and D17.  
**Depends on:** [phase-2-lead-policy.md](phase-2-lead-policy.md). Count, location, the draft gate, and `LeadRequest.signal` already exist.  
**Spec:** [PRD.md](../PRD.md) sections 7.2 and 7.3, [architecture.md](../architecture.md) sections 6 and 14.

Phase 3 replaces the fictional `example.com` hits with public web results. DuckDuckGo is the only provider. The scorer, the 60-point draft gate, and the 90-day window stay as phase 2 left them. A live hit still becomes a draft only when its fit score is at least 60.

`pytest` stays offline. The default suite monkeypatches the network functions. Parsing, host rules, and signal order are tested with saved fixtures.

## Done when

- `web_search` and `search_jobs_or_news` call DuckDuckGo and set `placeholder=false` on a live result.
- `search_provider()` returns `tavily` when `TAVILY_API_KEY` is set, and `duckduckgo` when it is empty. Hiring queries on Tavily include Greenhouse, Lever, and Ashby.
- `fetch_company_page` fetches one public http(s) URL and returns a text excerpt.
- A named signal is the only signal searched. An unnamed signal fills hiring, then funding, then launch, up to `LeadRequest.count`.
- Every kept hit has an http(s) evidence URL. LinkedIn, people-data hosts, and other blocked hosts are dropped.
- A search or fetch failure returns no invented companies. The trace says the call failed.
- The Streamlit warning that cards are fictional appears only when a result still has `placeholder=true`.
- Routing tests still pass without the network and without Ollama.

## Provider

Add the `ddgs` package to `requirements.txt` and call `DDGS` from `web_search` and `search_jobs_or_news`. `httpx` and Beautiful Soup are already dependencies and are the fetch stack.

`search_provider()` returns `tavily` when `tavily_api_key` is set, and `duckduckgo` otherwise. Default pytest clears the key, so the suite stays on the offline fixture.

One research run performs one web search and at most one page fetch of an allowed URL. Use a 15-second timeout. On exception, timeout, or an empty body, return an empty result list, `placeholder=false`, and a trace message naming the tool and the failure. Do not substitute the phase 1 fictional companies.

## What a query searches

`search_jobs_or_news` searches the phrase built from the `LeadRequest` slots in [phase-7-search-brief.md](phase-7-search-brief.md): sector, signal word, role, remote, location, then `jobs`, `funding`, or `product launch`. The operator's raw sentence is not sent to DuckDuckGo.

| `signal` | Searches, in order, stopping at `count` unique companies |
| --- | --- |
| `hiring` | that hiring phrase only, then the startup list below if nothing is kept |
| `funding` | that funding phrase only |
| `launch` | that launch phrase only |
| null | hiring, then funding, then launch, then the startup list if nothing is kept |

Hits taken from the hiring search are `signal=hiring`, and the same for funding and launch. Drop a later hit whose normalized company name was already kept.

When the hiring phrase keeps no company, read numbered `h2` and `h3` headings from one public list article. Try `top {sector} startups` in the place, then `funded {sector} startups`. Repeat a list search once when DuckDuckGo returns no rows. Those cards use signal `funding`, the article URL as evidence, and a snippet that says the company was named on that list. A title that is itself a job listing (`jobs`, `vacancies`, `openings`, `careers`, `hiring`) is not a company name.

`web_search` is the research path. It sends the operator query, `max_results` from the input (still 1–10), and does not apply the signal order.

## Which URLs are kept

A hit is kept only when all of these hold:

- The URL starts with `http://` or `https://`.
- The host is not on the blocklist below, and is not a subdomain of a blocklist host.
- A company name can be read from the title or snippet.

Blocklist:

- `linkedin.com`, `lnkd.in`
- `facebook.com`, `instagram.com`, `twitter.com`, `x.com`
- `zoominfo.com`, `apollo.io`, `lusha.com`, `hunter.io`, `rocketreach.co`, `signalhire.com`, `contactout.com`
- `naukri.com`, `instahyre.com`, `indeed.com`, `wellfound.com`, `angel.co`

Those last hosts are login-gated job boards for this demo. A company homepage, a public news article, and a public careers page on the company domain stay allowed.

Company name, first match:

1. Text after ` at ` in the title (`React Developer at Northwind` → `Northwind`).
2. Otherwise the title segment before ` - `, ` | `, or ` — `.
3. Otherwise drop the hit.

Strip a trailing legal suffix (`Inc`, `Ltd`, `Pvt`, `Private Limited`) for the display name. Dedupe and the CRM key use the slug from `normalize_domain(company)`, so `Northwind Pay` stays `northwind-pay.local`.

Do not use the evidence URL host as the CRM domain. A TechCrunch or YourStory article would collapse every company on that site into one row. Pass the company name into `crm_upsert` as phase 2 does. `fetch_company_page` may also return `company_domain` when the fetched host is the company site (the host is not a publisher and not on the blocklist). Outreach may pass that host as `domain` only in that case.

Publisher hosts, which never become `company_domain`: `techcrunch.com`, `yourstory.com`, `economictimes.com`, `inc42.com`, `entrackr.com`, `moneycontrol.com`, `livemint.com`, `bloomberg.com`, `reuters.com`, `forbes.com`, and any blocklist host.

## Page fetch

`fetch_company_page` issues one `httpx` GET. Redirects are allowed up to three hops, and the final URL has to pass the same host rules. Read at most 1 MB. Decode HTML with Beautiful Soup, drop `script`, `style`, and `nav`, and keep the title plus the first 1,500 characters of visible text.

Before the excerpt is stored, strip any substring that matches the personal-email or phone patterns in `guardrails.py`. The excerpt describes the company, the role, or the news item.

On `find_leads`, fetch a hit only when its snippet is shorter than 80 characters. Cap those fetches at `count`. On `research_company`, fetch the first allowed result. If that fetch fails, try the next allowed result, once.

A fetch that fails leaves the search hit in place. The evidence URL stays the search URL. The trace records the failed URL.

`placeholder` is `false` for a live search or a live fetch. It is `true` only for the offline fixture the tests install.

## UI

In `ui/app.py`, show the fictional-card warning only when some tool output on the run has `placeholder=true`. A live run shows the evidence link, the signal, and the fit score with no placeholder banner. The answer text from `respond` follows the same flag: a live run says the cards came from public search, and a fixture run still says they are placeholders.

## Offline tests

`tests/conftest.py` monkeypatches `web_search`, `fetch_company_page`, and `search_jobs_or_news` with an in-memory fixture that returns the current fictional hits and `placeholder=true`. The phase 2 routing assertions (five React cards, example.com URLs, `PLACEHOLDER` reasoning, draft gate, 90-day skip) keep running on that fixture. Default `pytest` does not open a socket.

`tests/test_search.py` calls the real parser and filter functions with saved DuckDuckGo-shaped dicts and a saved HTML string. No network.

| Case | Expectation |
| --- | --- |
| Hiring query, mixed fixture rows | Only `hiring` rows are kept, in result order, up to `count` |
| No signal in the query | Hiring rows are taken first, then funding, then launch, stopping at `count` |
| LinkedIn and ZoomInfo URLs | Dropped |
| Title `React Developer at Northwind Pay - LinkedIn` | Dropped on the host rule before the name is used |
| Title `Northwind Pay raises Series A - TechCrunch` | Company `Northwind Pay`, evidence URL kept, `company_domain` empty |
| HTML excerpt containing `jane@acme.com` and a phone number | Those substrings are absent from `text_excerpt` |
| Raised exception from the DuckDuckGo client | Empty results, `placeholder=false`, no `example.com` row |

Add one test marked `network` that calls DuckDuckGo for the Bengaluru rubric query and asserts each kept URL is http(s) and off the blocklist. Default `pytest` excludes that mark (`addopts` stays unchanged; document `pytest -m network` in this file only). A failure of the live service fails that marked test and does not fail the suite.

## Files

| File | Change |
| --- | --- |
| `requirements.txt` | Add `ddgs` |
| `tools/web_search.py` | DuckDuckGo text search. Provider is always `duckduckgo` |
| `tools/job_news_search.py` | Signal order, company parse, host filter, startup-list fallback |
| `tools/page_fetch.py` | One public GET, excerpt, contact stripping, optional `company_domain` |
| `schemas/tool_io.py` | `company_domain` on the page-fetch output |
| `graph/nodes/tool_node.py` | Pass signal into job/news search. Fetch short snippets and the research URL |
| `graph/nodes/outreach.py` | Use `company_domain` as the CRM domain only when the fetch returned one |
| `graph/nodes/respond.py` | Wording follows `placeholder` |
| `ui/app.py` | Warning follows `placeholder` |
| `tests/conftest.py` | Offline fixture backend |
| `tests/test_search.py` | Parser, blocklist, excerpt, failure fixtures |

## Out of this phase

| Left for | Work |
| --- | --- |
| Phase 4 | The 120–160 word draft. Live hits still go through the phase 1 placeholder body until then |
| Phase 5 | Judge notes |
| Phase 6 | Storing the edited subject and body, and the answer-level eval |

The draft gate from phase 2 still applies to every live card.
