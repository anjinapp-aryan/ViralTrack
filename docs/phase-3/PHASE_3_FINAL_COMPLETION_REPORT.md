# Phase 3 final completion report

Date: 2026-11-06. Baseline: `main` = `origin/main` = `b51498d`, submodule `d872014`. **Nothing is committed or pushed; the hosted CI has not run these changes.**
Verdict: **PHASE_3_COMPLETE_WITH_DOCUMENTED_LIMITATIONS**, for the approved, offline scope (D0 to D3). The roadmap stages D4 to D8 are not started and need approvals the
owner has not given; they are listed in section 9 as one consolidated decision report.

## 1. Executive summary

Phase 3 set out to make ViralTrack discovery return trustworthy, explainable candidates. D0 (audit), D1 (offline tests), D2 (keyword-collection `period` and the dedicated CI job) were done and merged earlier.
This delivery finished D3: every defect recorded as a strict xfail was fixed, the policy decisions the owner gave were implemented, and the remaining gaps found in a fresh audit were closed. **No xfail remains**, all
offline suites pass, and no upstream file, schema, Compose file, dependency or secret was touched. No YouTube request or quota was used.

## 2. Original Phase 3 scope (roadmap)

D0 audit, D1 offline correctness tests, D2 candidate generation, D3 configurable eligibility filters (fix the zero-result defect, make filters explicit, visible and safe), D4 explainable ranking, D5 dashboard/API (optional),
D6 history and tracking (optional), D7 controlled real-data validation (needs separate approval and budget), D8 release gate.

## 3. Acceptance matrix (audit areas A to R)

| Area | Status | Evidence |
|---|---|---|
| A. Funnel and result integrity | COMPLETE | `ContentPage.funnel` (`None` = unknown, `()` = reported empty); invalid, restricted or malformed funnels are withheld with a note; `test_d3_discovery_fixes.py` |
| B. Malformed entries and response validation | COMPLETE | one bad entry refuses the whole page (`results[i] is invalid`, field and type only, never the value); wrong-typed fields are malformed; absent or null stay missing |
| C. Deduplication | COMPLETE | canonical `content_id`, first occurrence wins, never merged, counted in a note, idempotent |
| D. Numeric validation | COMPLETE | `count()`, `_number()`, `duration_seconds()`: booleans, negatives, floats-as-counts, strings rejected or unknown, never coerced |
| E. Subscriber and minimum-view defaults | COMPLETE | unset = `max_subscribers=1000000`, `min_views=0`; proven on the real route (no 10,000 funnel step); Batch 5 replay returns candidates; invalid values refused before any request |
| F. 24-hour and lifetime velocity | COMPLETE | 24-hour values never mapped (no snapshot time exists); lifetime rate needs an aware date not in the future and views |
| G. Undated videos | COMPLETE | no lifetime rate, no invented date; real-route evidence that upstream would rank an undated video first |
| H. Safe sorting, restricted metrics | COMPLETE | allowlist of two (`views`, `published_at`); restricted names need approval; everything else refused before any request; nothing can reach the foundation's `viral` fallback |
| I. Engagement rate and hidden likes | COMPLETE (sort removed) | section 6 |
| J. Short-form filter (F-6) | COMPLETE | duration filter applied by ViralTrack, inclusive 180 s, zero/unknown/invalid not short, upstream `is_short` ignored, no Shorts funnel stage; real-route tests |
| K. Subscriber maximum 1,000,000 | COMPLETE | `MAX_CREATOR_FOLLOWERS`, enforced, documented, document-lint test; no unlimited sentinel |
| L. Period and query semantics | COMPLETE | discovery `period` now strict (`all` or 1 to 9999 `h`/`d`, `fullmatch`); the old pattern accepted `"7d\n"`, zero and leading zeros; collection `period` strict since D2; region validated |
| M. Pagination, limits, upstream defaults | COMPLETE | no offset exists upstream, so there is one page; `limit` 1 to 1000, no booleans; every threshold explicit; foundation's Shorts and subscriber defaults neutralised |
| N. RAW vs DERIVED provenance | COMPLETE (unchanged) | raw/derived split and `Provenance` untouched; funnel and notes are not metrics |
| O. Missing values and timestamps | COMPLETE | unknown stays `None`; publication and first-seen times are aware UTC or unknown; `collected_at` stays `None` |
| P. API serialization, platform-neutral contracts | NOT_APPLICABLE | the repository has no API or serialisation layer yet (D5); `ContentPage`/`FunnelStage` are platform-neutral and contain no YouTube names |
| Q. Remaining roadmap requirements | D0 to D3 COMPLETE; D4 to D8 BLOCKED / not started | section 9 |
| R. Tests, CI, documentation | COMPLETE locally; hosted gate IMPLEMENTED_BUT_UNVERIFIED | section 7 |

## 4. Findings resolved

| Finding | Resolution |
|---|---|
| F-1 / F-2 unset thresholds fall back to 10,000 | explicit `1000000` / `0` (the 3 last strict xfails) |
| Funnel lost | surfaced |
| Silent entry drops, duplicates, boolean totals | fail closed, collapsed with a note, rejected |
| 24-hour velocity with unknown recency; lifetime velocity for undated videos | withheld; sorts removed |
| Sort fallback to the restricted default | single allowlist, refused before any request |
| Hidden likes as zero in the engagement ordering | sort removed, value shown only with visible likes |
| F-6 Shorts filter | owner decision implemented |
| Subscriber documentation that presented the 32-bit maximum as a setting | corrected: 1,000,000, a bounded limit |
| Period pattern accepted `"7d\n"`, `0h`, `07d` | strict |
| `limit`, `region`, `short_form`, `sort`, thresholds unchecked or loosely checked | validated before any request |

Original nine strict xfails: all nine are fixed; the gate now expects none.

## 5. Findings deferred, with reasons

| Item | Reason |
|---|---|
| F-3 (keyword collection default) | fixed in D2 (`period`); live effect is D7 |
| F-5 text-search ordering | already decided: relevance only, no score exposed (the semantic score stays internal) |
| F-7 freshness (`collected_at` unknown) | unchanged by design; unknown stays `None`; no replacement exists in the foundation |
| F-8 composite scores | blocked by the derived-metric policy; not built |
| D4 explainable ranking | the roadmap requires the owner **and counsel** to answer the ranking question first |
| D5 dashboard/API, D6 history | optional, never approved; D5 must not start before D8 |
| D7 live validation, D8 release gate | D7 needs a separate authorisation with a written budget (at most 15 units and 1 search call); D8 depends on D7 |

## 6. Engagement-rate audit

Upstream `engagement_rate = ((likes or 0) + (comments or 0)) / views * 100`; it is `None` only when views are missing or **both** likes and comments are hidden. With hidden likes and any comment figure,
hidden likes count as zero (understated). Real-route evidence (`test_upstream_orders_by_an_engagement_rate_that_counts_hidden_likes_as_zero`): a hidden-likes video with 300 comments scores 3.0 and ties a visible 3.0 %; hidden likes with no comments score 0.0.
That value **orders** the results (a hidden-likes video outranks a both-hidden one), so a missing value was silently converted to zero for ranking, against the baseline. ViralTrack never displayed a different number (the rate is omitted whenever likes are hidden),
and restricted metrics never entered this sort or any eligibility rule. A trustworthy calculation is impossible from upstream's output without refetching likes, so none was invented. **Correction applied:** the engagement-rate sort is refused with its reason (same
precedent as the lifetime sort); the value is still shown when likes are visible. Alternative if the owner wants the sort back: have the foundation expose `likeRate` / hidden flags (an upstream change, not allowed) or order locally over a full page (not recommended).

## 7. Tests and CI

All runs exited 0 (local PostgreSQL 16.2 with pgvector; the upstream interpreter for the upstream-backed tests).

| Run | Passed | Failed | Skipped | Xfailed |
|---|---|---|---|---|
| Five CI files with `--junitxml`, then the real gate (281 collected, gate exit 0) | 281 | 0 | 0 | 0 |
| `tests/test_d3_discovery_fixes.py` alone | 309 | 0 | 0 | 0 |
| Full suite, database + upstream Python (`VT_TEST_REQUIRE_UPSTREAM=1`) | 913 | 0 | 5 | 0 |
| Full suite, database only | 805 | 0 | 113 | 0 |
| Plain `pytest` | 781 | 0 | 137 | 0 |
| `ruff check .` | clean | | | |

Skips are all expected: the full run skips 2 live-foundation tests (no foundation URL) and 3 POSIX-only tests (Windows); the database-only run additionally skips the 108 upstream-backed tests (no upstream interpreter); the plain run also skips the database tests.
Before Phase 3 D3 the full run was 591 passed with 9 xfailed. CI gate (`tests/support/ci_checks.py`): `EXPECTED_XFAILS` is empty; the minimum for the policy file moved from 35 to 32 because three 24-hour or lifetime/engagement sort
parameters were removed on purpose; the workflow file changed in one comment only. **Hosted CI:** the previous commit's hosted run was green; these changes have not run on GitHub (not pushed), so the hosted result is IMPLEMENTED_BUT_UNVERIFIED.
No network-dependent test ran: the upstream-backed tests use the in-process runner with a `requests` guard, and the others use mock transports.

## 8. Architecture, reuse, data and metric policy

- **Layers:** `viraltrack/domain` gained `FunnelStage` and `ContentPage.funnel` (no YouTube names). Everything else is in `viraltrack/providers/youtube` (`mapping.py`, `provider.py`) and comments in `providers/base.py`. No new module, dependency, schema, Compose or upstream change.
- **Reuse:** REUSE the existing bool-safe pattern (`_cap`, `_int`), `MetricPolicy`, `REQUIRES_RAW`, `Provenance`, dict ordering and dataclass equality; COMPOSE the foundation's documented funnel shape. `pydantic`, `jsonschema` and `more-itertools` were rejected (a few field checks do not justify a dependency).
- **Data and metric policy:** 4 allowed, 10 restricted, 2 internal-only metrics are unchanged. The two 24-hour values are classified allowed but not mapped (no snapshot time). Restricted metrics are never mapped, sorted, filtered or exposed; the adapter sends
  `min_views_per_subscriber=0` and no outlier threshold. `short_form` is a duration filter and the `SHORT` label stays restricted. Retention is untouched: no new persistence.

## 9. Consolidated owner-decision report (the only open items)

| # | Decision | Recommendation |
|---|---|---|
| 1 | Confirm the **engagement-rate sort removal** (made here on the lifetime-sort precedent and the "never convert missing to zero" baseline) | confirm; reversible by adding one line to the allowlist |
| 2 | **D4** explainable ranking needs the owner **and counsel** to say whether single-metric ordering is "ranking" under the Google policy | ask counsel before any work |
| 3 | Whether **D5** (API/dashboard) and **D6** (history, watchlist, quota ceiling) belong in Phase 3 | defer until D8 |
| 4 | **D7**: authorise one controlled live validation with a written budget (at most 15 units and 1 search call) | do after the owner pushes and the hosted CI is green |
| 5 | **Push authorisation** for this delivery, then a hosted CI run | needed before the phase can be called verified |

## 10. Known limitations

- A filtered `short_form` page is chosen from the first 1000 candidates of the requested order (a note says when that bound is reached); `total` is `None`; the funnel counts videos of every duration.
- One malformed result entry hides the valid ones (owner decision).
- The foundation's funnel is not cross-checked against `matched`; its first stage is not the corpus size.
- The future-date guard on the lifetime rate uses the provider clock (a skewed clock withholds a valid rate, the safe direction).
- Discovery quality on real data is unproven until D7; everything here is offline and synthetic.
- `short_form` is not YouTube's Shorts classification.

## 11. Security and quota confirmation

No YouTube API call, no quota spent, no live validation, no undocumented API, no scraping, no cookie use, no CAPTCHA or rate-limit bypass. No secret was read, printed or written; a scan of every changed file found none. The upstream submodule is
at `d872014` and unchanged; no schema, Compose or dependency file changed; nothing is staged; no commit or push occurred.

## 12. Changed files (working tree against `b51498d`)

Production (5): `viraltrack/domain/__init__.py`, `viraltrack/domain/models.py`, `viraltrack/providers/base.py` (comments), `viraltrack/providers/youtube/mapping.py`, `viraltrack/providers/youtube/provider.py`.
Tests (7): `tests/support/ci_checks.py`, `tests/test_ci_checks.py`, `tests/test_discovery_d1_adapter.py`, `tests/test_discovery_d1_policy.py`, `tests/test_discovery_d1_upstream.py`, `tests/test_youtube_provider.py`, and new `tests/test_d3_discovery_fixes.py`.
CI: `.github/workflows/ci.yml` (one comment).
Docs (10): `docs/phase-1/DERIVED_METRIC_POLICY.md`, `METRIC_INVENTORY_AND_APPROVAL.md`, `PROVIDER_BOUNDARY.md`; `docs/phase-2/DISCOVERY_TEST_PLAN.md`; `docs/phase-3/D1_CLOSURE_REPORT.md`, `D1_OFFLINE_DISCOVERY_TEST_REPORT.md`, `DISCOVERY_EXECUTION_ROADMAP.md`;
new `D3_DISCOVERY_DEFECT_FIX_REPORT.md`, `F6_SHORT_FORM_INVESTIGATION.md`, `PHASE_3_FINAL_COMPLETION_REPORT.md`.
Total against HEAD (tracked files): 19 changed, 580 insertions, 171 deletions, plus 4 new files.

## 13. Release-readiness verdict

**PHASE_3_COMPLETE_WITH_DOCUMENTED_LIMITATIONS.** The approved offline scope is complete and verified locally; hosted CI verification and everything in section 9 remain.
