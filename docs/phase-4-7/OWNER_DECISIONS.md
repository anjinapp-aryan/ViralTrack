# Owner decisions for phases 4 to 7

## Recorded owner decisions (after review of Stage A, 2026-11-07)

| # | Decision | Outcome |
|---|---|---|
| 1 | `engagement_rate` sort | Stays refused. The foundation computes `(likes or 0) + (comments or 0)` and so understates videos with hidden likes; the displayed value is still shown when likes are visible. No behavior change. |
| 2 | D4 ranking and claims policy | Questions to be prepared for counsel ([LEGAL_POLICY_DEPENDENCIES.md](LEGAL_POLICY_DEPENDENCIES.md), section 2). Not sent. D4 policy-dependent behavior stays blocked. |
| 3 | D5 API and dashboard | Deferred. |
| 4 | D6 history and watchlists | Deferred. |
| 5 | D7 | Offline harness preparation authorized, after a fresh reuse audit ([D7_OFFLINE_HARNESS.md](D7_OFFLINE_HARNESS.md)). No live call authorized. |
| 6 | `discovery-offline` as required check | Approved in principle; steps in [CI_REQUIRED_CHECK.md](CI_REQUIRED_CHECK.md); not yet applied. |
| 7 | Test environment documentation | Done in the README. |

## Original decision table (kept for the record)

Date: 2026-11-07. Nothing below is assumed approved. Until a decision is recorded, the committed behavior stays.

| # | Decision | Options | Recommendation | Blocks |
|---|---|---|---|---|
| 1 | `engagement_rate` sort | (a) keep it refused (committed D3 behavior); (b) allow it only for rows whose likes are visible, computed by ViralTrack from raw views, likes and comments; (c) restore the foundation's ordering | (a) now; (b) later if engagement ordering is wanted. Not (c): the foundation computes `(likes or 0) + (comments or 0)` and so understates videos with hidden likes | Nothing urgent |
| 2 | D4 ranking and claims policy | Counsel and owner answer the nine questions in [LEGAL_POLICY_DEPENDENCIES.md](LEGAL_POLICY_DEPENDENCIES.md); in particular whether ordering by one raw metric is "ranking", and which words (popular, trending, viral, breakout, emerging) may appear | Ask counsel first; approve only the explanation record (no scores, no confidence value) in the meantime | D4, all D5 display wording |
| 3 | D5 API and dashboard | Authorize now / defer. If authorized: users and authentication needs; API only or API plus a read-only page; approve `schemathesis` as a dev dependency | Defer until decision 2; then API only | D5 |
| 4 | D6 history and watchlists | Authorize now / defer. If authorized: start with the read-only timestamp audit of the foundation history endpoints | Defer; authorize only the timestamp audit when D5 is decided | D6 |
| 5 | D7 live validation | Authorize one run, or not. The authorization request must state endpoint, exact query, call count, unit ceiling (at most 15 units, one search call), database target, retention and cleanup, secret handling, expected evidence and stop conditions, and must confirm the quota accounting described in the roadmap (search has its own 100-per-day bucket in the foundation) | Not yet; prepare the harness first, then ask with the full request | D7 |
| 6 | Make the `discovery-offline` CI job a required check | Yes / no | Yes, after one more green run on a normal change | CI trust |
| 7 | Local test environment | Document `pip install -e ".[dev]"` in a venv in the README, or leave as is | Document it (one line) | Nothing |

Items 1 to 5 were already open in the Phase 3 report; 6 and 7 are new.

What can proceed without any decision: documents and read-only audits. What cannot: any code that ranks, scores, exposes a new metric, adds a dependency, adds a table, or touches the live API.
