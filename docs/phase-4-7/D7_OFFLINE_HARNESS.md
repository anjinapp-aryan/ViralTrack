# D7 offline harness: reuse audit, design, tests and the future authorization request

Date: 2026-11-07. Authorized scope: offline preparation only. No live API call was made, no quota was spent, and live execution is disabled by default and unauthorized.

## 1. Fresh reuse audit (what already exists, checked first)

| Need | Existing capability (inspected in source) | Decision |
|---|---|---|
| Count and cap search calls and units | Foundation ledger: `backend/infrastructure/youtube/client.py` `_charges` / `_reserve` reserve cost before the request, all counters in one transaction; `COST` is 1 per call; a search is charged as 1 search call (limit 100/day) **and** 1 pool unit (limit 10,000/day). `GET /api/health` reports `searchQuota.callsToday` and `unitQuota.unitsToday` | REUSE as the source of truth; the harness only reads it |
| One collection, no retry | `FoundationClient.post` makes one attempt and turns a timeout into `ProviderTimeout(outcome_unknown=True)` | REUSE |
| Preflight (credentials, quota floor, cooldown, caps) | `YouTubeProvider._preflight`, `_cap`, `IngestionSettings` (`max_search_pages` default 1, quota floors) | REUSE |
| Collection call and result mapping | `YouTubeProvider.collect_query`, `ingestion.collect_result` | REUSE |
| Scheduler | Foundation worker; not needed (one manual run) | not used |
| Test doubles | `httpx.MockTransport`, same pattern as `tests/test_ingestion.py` | REUSE the pattern |
| HTTP mocking or recording libraries (`respx`, `vcrpy`, `responses`) | Verified in [OPEN_SOURCE_REUSE_AUDIT.md](OPEN_SOURCE_REUSE_AUDIT.md): duplicate, or store raw responses | REJECT |
| Quota-limiting libraries | None needed: the foundation already enforces its daily ceilings | REJECT |

Remaining BUILD (justified, small, ViralTrack-specific): an approval guard that the foundation cannot provide because the budget is ViralTrack's own owner policy: a hard 1 search call and 15 other units ceiling, an arming switch bound to the exact approved request, an independent before and after ledger check, and a single-use run. About 150 lines in `viraltrack/providers/youtube/live_validation.py`. No dependency added.

## 2. Design

* `LivePlan(query, region, language, period)`: the exact approved request; always one search page. `fingerprint()` is a hash of the whole request.
* `LiveBudget(max_search_calls=1, max_other_units=15)`: can be lowered, never raised (values above the ceilings, negatives, booleans, floats and strings raise `ValueError`).
* `LiveValidation(provider, plan, budget, env, clock).run()`:
  1. Refuses unless the environment variable `VT_LIVE_VALIDATION_ARM` equals the plan fingerprint (default: disabled; nothing is sent, not even a health read).
  2. Refuses if the estimated follow-up reads (2 units for one page of at most 50 results, from the foundation's documented 1 unit per 50 videos and channels) exceed the budget, or the budget allows no search.
  3. Reads the ledger (`/api/health`, free). Refuses if no search call is left.
  4. Marks itself used, then makes **one** `collect_query(pages=1)`. Any error is recorded and never retried.
  5. Reads the ledger again. Search calls used = difference of calls; other units used = difference of pool units minus search calls. Both are compared with the budget; the foundation's own reported figures are also compared. A breach, or an unreadable ledger after the call, raises `LiveBudgetExceeded` carrying a sanitized report.
  6. A second `run()` on the same object is refused.
* Independence of the two limits: the search limit is enforced by the single page, the single POST and the single-use object before the call, and by the ledger difference after it; the unit limit by the estimate before and the ledger difference after. Neither check relies on the number the foundation echoes in its own response.
* Honest limit: the ledger check after the call detects an overrun, it cannot undo it. Prevention before the call rests on one page (at most 50 results) and the foundation's own daily ceilings.
* The report holds counts and ledger differences only. No response body, no query result content, no credentials.

## 3. Tests

`tests/test_live_validation_harness.py`, 29 tests against a fake foundation whose `/api/health` counters are moved by `/api/collect/niche`, like the real ledger. They prove: disabled by default and for any other plan (zero requests); the ceilings cannot be raised; one POST with `pages=1`; ledger-measured search and other-unit counts; a second search call, 16 other units, a lowered budget, and a lying foundation response each raise `LiveBudgetExceeded`; exactly 15 other units is allowed; a budget below the estimate or with no search call sends nothing; no search call left prevents the POST; a second run is refused; HTTP 500, HTTP 502 and a read timeout are never retried (one POST each); an unreadable ledger after the call is reported as unverified; the report contains no token.

Results on 2026-11-07: 29 passed in 0.1 s; full suite 810 passed, 137 skipped (database, foundation and POSIX-only tests, see the README), 0 failed, 0 xfailed; `ruff check .` clean. The harness tests need no environment variable and cannot reach a network (mock transport only).

## 4. Draft of the future authorization request (not sent; not an authorization)

1. Operation: one `POST /api/collect/niche` through `YouTubeProvider.collect_query`, one page.
2. Search query: *to be chosen by the owner* (and optional region, language, period); the arming value is its fingerprint.
3. Request count: one POST; the ledger is read before and after (free).
4. Maximum quota: 1 `search.list` call and at most 15 other units (expected 2).
5. Maximum results: one page, at most 50 videos.
6. Database target: *to be named by the owner* (a disposable foundation database, not a production one).
7. Retention and cleanup: the 30-day policy applies; run the retention report afterwards, then `--apply` only on the disposable database if the owner approves.
8. Secrets: the YouTube key stays in the foundation environment; the harness never reads it; the report is sanitized.
9. Expected evidence: sanitized report (`LiveReport.as_dict()`), ledger before and after, retention report.
10. Stop conditions: any difference from this plan; ledger unreadable; any breach; any error (no retry).
11. Rollback or cleanup: cannot refund quota; delete the disposable database or the rows collected.
12. Prerequisites the owner must set: `VT_YOUTUBE_INGESTION_ENABLED=true`, `VT_LIVE_VALIDATION_ARM=<fingerprint>`, a foundation with `YOUTUBE_API_KEY`.

Not yet built: a command-line entry point to run the guard. It is deliberately left out until the owner approves the request above, so there is no executable path to a live call in the repository.
