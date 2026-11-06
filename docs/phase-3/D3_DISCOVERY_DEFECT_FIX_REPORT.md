# D3 discovery defect fixes: implementation report

Date: 2026-11-06. Status: **implemented and tested offline, awaiting owner review. Not committed, not pushed.** The seven defect fixes
and, after the owner's policy decisions, the F-1/F-2 threshold fix (section 10) are done; **no strict xfail remains**. Open: the lifetime-sort
finding was resolved by the owner's decision to remove the sort (section 11). Open: F-6 (`short_form`), investigated only: [F6_SHORT_FORM_INVESTIGATION.md](F6_SHORT_FORM_INVESTIGATION.md).

Baseline: `main` = `origin/main` = `b51498d`, clean tree, submodule `d872014`. No YouTube call, no quota, no network use, no upstream change.

## 1. Executive summary

| ID | Defect | Outcome |
|---|---|---|
| D3-01 | Foundation funnel lost | `ContentPage.funnel` (tuple of `FunnelStage`) carries it; `None` = not reported, `()` = reported empty |
| D3-02 | Malformed entries dropped silently | The whole response is refused with `ProviderError` naming `results[i]`; wrong-typed fields are malformed |
| D3-03 | Duplicate video ids | Collapsed by canonical id, first occurrence wins, a note counts them |
| D3-04 | Boolean accepted as a total | One `count()` helper for totals and funnel counts; booleans, negatives, floats, strings are unknown |
| D3-05 | 24-hour velocity with unknown snapshot recency | `views_per_hour_24h` and `views_gained_24h` are not mapped and cannot be a sort |
| D3-06 | Lifetime velocity for undated videos | Withheld without an aware publication date, with a future date, or without views |
| D3-07A | Sort fallback | One allowlist of three (`views`, `published_at`, `engagement_rate`); everything else, including both 24-hour and the lifetime rate, refused before any request |
| D3-07B | Subscriber bound | 1,000,000 enforced in the adapter; contradictory documents corrected |

## 2. Root causes

- **D3-01:** `YouTubeProvider._page` copied only `results`, `matched` and `hint`; the response's `funnel` list was never read.
  Upstream builds it in `application/discovery.py` as `[{"step": name, "remaining": n}]`, one entry per filter that ran, in order.
- **D3-02:** `_page` mapped `r for r in results if isinstance(r, dict)`, so non-objects vanished. Inside an object, `title`,
  `thumbnail`, `language` and similar were copied without a type check, and `_num` turned a wrongly typed number into "missing".
- **D3-03:** nothing compared ids. Upstream de-duplicates by primary key, so a repeat means a faulty or replayed response.
- **D3-04:** `isinstance(total, int)` is true for `True`/`False` (`bool` subclasses `int`).
- **D3-05:** upstream computes `vph24h` from "the latest snapshot at least 24 h older, else the oldest one" and sends **no snapshot
  time**. A 2-hour rate was therefore shown under a 24-hour label. This was a characterised known limit in D1.
- **D3-06:** upstream computes the lifetime rate from an age of 0 h (floored to 1 h) when `publishedAt` is missing; the adapter passed the
  number through. `parse_time` also accepted offset-less text, assuming nothing about the zone but returning a naive time.
- **D3-07A:** `_SORTS` mixed approved and restricted names and relied on `metric_policy.require` per key; a non-hashable `sort` raised
  `TypeError` and the two 24-hour sorts ordered by a value that should be hidden. Upstream itself falls back to restricted `viral` for any
  unknown name, so the adapter must never forward one.
- **D3-07B:** the documents called the practical upper bound `2147483647` "unbounded" in places, and no code enforced the approved bound.

## 3. Reuse audit

Fresh, focused audit. Licences are from memory and were **not re-verified** (no network in this task); none was adopted.

| Candidate | Licence | Capability | Decision |
|---|---|---|---|
| This repository: `mapping._num`, `ingestion._int`, `provider._cap` (already refuses `bool`), `MetricPolicy`, `Provenance`, `REQUIRES_RAW` | project | bool-safe numbers, policy gate, "needs raw input" rule | **REUSE / ADAPT**: `_num` idea became `_number`/`count`; `REQUIRES_RAW` now also guards lifetime velocity |
| Python `dict` insertion order, `dataclass` equality | stdlib | stable de-duplication, "same data" comparison | **REUSE** |
| `pydantic` | MIT | schema validation | **REJECT**: new dependency for four field checks |
| `jsonschema` | MIT | JSON validation | **REJECT**: same reason; error text would also echo values |
| `more-itertools` (`unique_everseen`) | MIT | order-preserving unique | **REJECT**: a dict does the same |
| Upstream (`discovery.py`) | MIT | builds the funnel | **COMPOSE**: read its documented shape; unchanged |

## 4. Implementation

| File | Change |
|---|---|
| `viraltrack/domain/models.py`, `domain/__init__.py` | `FunnelStage` (validated: non-empty step, non-negative non-bool integer) and `ContentPage.funnel` |
| `viraltrack/providers/youtube/mapping.py` | strict readers `_number`, `_text`, `count`; `published_time`; `map_funnel`; `mentions_restricted_metric`; velocity gates |
| `viraltrack/providers/youtube/provider.py` | `_page` (index-tagged errors, de-duplication, funnel, hint filter), one sort allowlist, `MAX_CREATOR_FOLLOWERS` |
| `tests/support/ci_checks.py`, `tests/test_ci_checks.py`, `.github/workflows/ci.yml` (one comment) | the gate expects no xfail (`EXPECTED_XFAILS` is empty); policy-file minimum 35 to 33 |
| Tests | `tests/test_d3_discovery_fixes.py` (new); six D1 xfails turned into normal tests; characterisation tests rewritten |
| Docs | this report; roadmap; `DERIVED_METRIC_POLICY.md`; subscriber-bound wording in three earlier documents |

No production file outside `viraltrack/domain` and `viraltrack/providers/youtube` changed. `base.py`, `ingestion.py`, the retention package,
Compose, schema, dependencies and the upstream submodule are untouched.

## 5. Policy details and exact semantics

**Funnel (D3-01).** Stages are `(step, remaining)` in upstream order; `remaining` is the number of candidates left after that step.
Limits: the first stage counts videos in the foundation's window, **not** the whole corpus; counts are not checked for monotonicity or
against `matched`; the step text is upstream's English label (a hint may be in another language). If the funnel is not a list, any stage is
invalid (including a boolean, negative, float, string or missing count), or any step names a restricted metric (`per subscriber`,
`outlier`, `viral`, `acceleration`), the **whole funnel is unavailable** (`None`) and a note says why: a funnel missing a stage would mislead.
A `hint` naming a restricted metric is dropped for the same reason. The adapter never sends the restricted thresholds, so this is defence in depth.

**Malformed entries (D3-02).** Contract: the response is refused as a whole (`ProviderError`, message `results[i] is invalid: <reason>`),
the same contract as an item without ids. Reasons name the field and the type, never the value. Absent or `null` optional fields stay
missing; a present field of the wrong type (text where a number is expected, a boolean, a non-finite number, a number where text is
expected) is malformed. The previous partial-page behaviour is gone; a caller who wants partial results must ask for that explicitly.

**Duplicates (D3-03).** Key: `content_id` only (never title, channel or URL). The first occurrence wins because the foundation's order is
its ranking; later ones are dropped whole and **never merged**. The page note states how many were dropped and how many differed from the first.
`total` is the foundation's `matched` and is not recomputed.

**Totals (D3-04).** `count()` accepts a non-negative `int` that is not a `bool`. Anything else is **unknown** (`None`), not an error and not
zero, matching the existing contract for a malformed total.

**24-hour velocity (D3-05).** Not mapped: neither the rate nor the "views gained" value. Neither the response time, the collection time nor
`firstSeenAt` stands in for a snapshot time; no lifetime or other value is substituted; the two sorts are refused. The policy table still
classifies both ALLOWED (4 / 10 / 2 unchanged); they return when a verified snapshot time exists.

**Lifetime velocity (D3-06).** Shown only when `publishedAt` is an ISO text **with an offset or `Z`** (stored as aware UTC), is not later than the
provider's clock, and the video has a numeric `views`. Missing, null, malformed, offset-less and future dates give "unknown" and no rate;
zero views on a dated video is a real `0`. The future check uses the provider clock and is a sanity guard, not a snapshot time.

**Sorting (D3-07A).** `_SORTS` (three approved: `views`, `published_at`, `engagement_rate`; the lifetime rate was removed, section 11) plus
`_SORTS_NEEDING_APPROVAL` (the five restricted names, still refused with `RestrictedMetric` until the policy carries their approval)
are the only names that can reach the foundation. Everything else, including `viral`, `viralScore`, `outlier`, `views_per_subscriber`,
`outlier_score` (refused as restricted), non-text input, empty and mis-cased names, is refused before any request. Text search: the
foundation orders by relevance and ignores `sort_by`; ViralTrack still sends and validates a sort, and that order is **query relevance
only**, never popularity or viral ranking.

**Subscriber bound (D3-07B).** Owner-approved maximum: **1,000,000 subscribers**, a bounded discovery limit and not "unlimited". The adapter
refuses larger values, negatives, booleans and non-integers before any request. `2147483647` appears in documents only as an upstream
observation, labelled as not a ViralTrack setting.

## 6. Tests

New: `tests/test_d3_discovery_fixes.py` (all offline, mock transport). Converted from strict xfail to normal tests: boolean total, invalid
entries (now asserts refusal), duplicates, funnel, stale snapshots, undated lifetime velocity. Rewritten because the behaviour changed on
purpose: two-snapshot and two-hour 24-hour characterisations (now assert the value is withheld), the approved-sort matrix (24-hour rows
removed), `test_raw_and_allowed_derived_by_default`, `test_allowed_derived_sort_and_unknown_sort`. One fixture fix: the upstream replay now uses
the real current time as the provider clock, because its corpus dates are relative to it.

## 7. Results

Local PostgreSQL 16.2 with pgvector; every run exited 0 after the last change.

| Run | Passed | Failed | Skipped | Xfailed |
|---|---|---|---|---|
| Five CI files with `--junitxml`, then the real `gate` (exit 0; 277 collected) | 277 | 0 | 0 | 0 |
| Full suite, database + upstream Python (`VT_TEST_REQUIRE_UPSTREAM=1`) | 814 | 0 | 5 (2 live-foundation, 3 POSIX-only) | 0 |
| Full suite, database only | 710 | 0 | 109 | 0 |
| Plain `pytest` | 686 | 0 | 133 | 0 |
| `ruff check .` | clean | | | |

(Figures after the final policy corrections, section 11; the D3-only run before it was 784 / 683 / 659 with 3 xfailed.) Before D3 the same configurations gave 591 / 492 / 468 passed and 9 / 7 / 7 xfailed. `tests/test_d3_discovery_fixes.py` now has 212 tests. The hosted CI has not
run these changes.

## 8. Remaining limitations

1. ~~Three strict xfails remain~~ Resolved by the F-1/F-2 fix (section 10); none remains.
2. ~~Ordering by `views_per_hour_lifetime`~~ Resolved: the sort is removed (section 11). The lifetime rate is still **shown** for dated videos
   (D3-06), but cannot order a result.
3. The funnel is not cross-checked against `matched` or for monotonicity; its first stage is not the corpus size.
4. A malformed entry now fails the whole page: one bad row hides the good ones. This is the stricter reading of the existing contract.
5. The future-date guard depends on the provider clock; a badly skewed clock withholds valid rates (the safe direction).
6. The hosted CI has not run these changes.

## 9. Confirmations

No YouTube API call, no quota, no real-data collection, no live-foundation test, no network use by the tests (mock transports and the
in-process upstream runner only). The upstream submodule (`d872014`), schema, Compose and dependency files are unchanged. No commit, push or
history change. Restricted metrics remain unmapped and unsortable.

## 10. Owner decisions and the F-1/F-2 fix (same day)

Owner decisions applied: (1) both 24-hour velocity sorts removed (done in D3-05/D3-07A); (2) a malformed result entry rejects the whole page
(done in D3-02); (3) subscriber discovery stays bounded at 1,000,000, no unlimited sentinel; (4) an unset minimum views is sent as `min_views=0`.

**Root cause.** `discover_content` put `query.max_creator_followers` and `query.min_views` straight into the request parameters. Both default to
`None`, and `FoundationClient` drops `None` parameters, so the foundation's route applied its own `max_subscribers=10000` and
`min_views=10000`. A Batch 5 corpus of small-to-mid channels with few views then lost almost every video at the first two funnel steps.

**Behaviour now (every `/api/viral` request from `discover_content`).**

| Query value | Sent | Check |
|---|---|---|
| `max_creator_followers` unset | `max_subscribers=1000000` | |
| supplied | the value | whole number, not a boolean, 0 to 1,000,000, else `ValueError` before any request |
| `min_views` unset | `min_views=0` | upstream tests `if min_views:`, so 0 means no views filter (proved against the real route) |
| supplied | the value | whole number, not a boolean, 0 or more, else `ValueError` before any request |
| restricted threshold | `min_views_per_subscriber=0` (unchanged) | never `min_outlier_score` or a preset |

Exact request for `DiscoveryQuery()`: `period=7d&sort_by=views&limit=24&max_subscribers=1000000&min_views=0&min_views_per_subscriber=0&only_shorts=false&exclude_shorts=false`
(`region` and `niche` omitted when unset, as they have no upstream default). Replayed against the real upstream route the funnel is
`videos in window`, `channel subs <= 1,000,000` only; no `10,000` step appears and the result equals the one from a 32-bit probe on the same corpus.
On the Batch 5-shaped corpus the same `period=30d` query now returns 2 of the 3 videos in the window (it returned 0): the third is on a channel above 1,000,000 subscribers and is excluded by the approved bound; a 32-bit probe would return all 3 (kept as a test). Note that 1,000,000 is a **bounded** discovery limit: a channel above it is excluded, and a hidden-subscriber channel still passes (upstream rule).

**Tests.** The three strict xfails became ordinary tests in `tests/test_discovery_d1_adapter.py`; new tests in `tests/test_d3_discovery_fixes.py`
(exact payload, verbatim supplied values, refusals before any request, no sentinel) and two in `tests/test_discovery_d1_upstream.py` (real route).

**Lifetime-velocity sorting (owner decision: removed, section 11).** Evidence (real upstream, synthetic corpus, `sort_by=vph_lifetime`): the undated video is
returned **first** with `vphLifetime` 40,000.0, above the best dated video (4,687.5), because upstream treats its age as 0 h (floored to 1 h). Hiding the value was not
enough: the rank and one slot of `limit` are upstream's. The owner approved removing the sort; no local reordering was added.

**Consistency of the owner decisions in the documents.** 24-hour removal: report sections 4 and 5, `DERIVED_METRIC_POLICY.md`, roadmap, tests. Whole-page rejection:
report sections 4 and 5, `test_d3_discovery_fixes.py`, roadmap. Bound: report, roadmap, `DISCOVERY_TEST_PLAN.md`, two Phase 3 reports and a document-lint test.

## 11. Final policy corrections (owner-approved)

**Decision 1: lifetime-velocity sort removed.** `views_per_hour_lifetime` (upstream `vph_lifetime`) is no longer in `_SORTS`; it is in `_REFUSED_SORTS` with
the reason, next to the two 24-hour values. Allowed sorts are now exactly `views`, `published_at` and `engagement_rate`.

- **Error semantics:** `DiscoveryQuery(sort="views_per_hour_lifetime")` raises `ValueError` ("sort 'views_per_hour_lifetime' is not available: the foundation ranks an
  undated video by a fabricated rate (age 0 h) and places it first; hiding the value does not remove it from the ordering"). Other spellings (`vph_lifetime`, upper case)
  raise "unknown sort". Both happen before any request; the same applies to `search_content`.
- **No fallback:** the adapter only forwards names found in `_SORTS` or `_SORTS_NEEDING_APPROVAL`; a refused or unknown name never reaches the foundation, so its fallback to
  `viral` cannot be triggered and `vph_lifetime` cannot come back through an unknown value. A test pins the set of values the adapter can send:
  `{views, published, engagement}`.
- **Evidence kept:** `test_upstream_ranks_an_undated_video_first_by_lifetime_velocity_so_viraltrack_refuses_that_sort` (real upstream: 40,000.0 first) and
  `test_lifetime_velocity_is_not_a_sort_and_nothing_restores_it`. No local reordering exists.
- **Unchanged:** the lifetime rate is still displayed for dated videos with views (D3-06); it just cannot order results. The other approved sorts are untouched.

Not examined: `engagement_rate` ordering has its own upstream quirk (a hidden like count counts as 0 there, while ViralTrack omits the value); it is an approved sort and was not
changed. F-6 is investigated, not implemented: see [F6_SHORT_FORM_INVESTIGATION.md](F6_SHORT_FORM_INVESTIGATION.md).

## 12. F-6 implementation and the engagement-rate audit

**F-6** (owner-approved, section 8 of [F6_SHORT_FORM_INVESTIGATION.md](F6_SHORT_FORM_INVESTIGATION.md)): `short_form` is a duration filter on raw metadata applied by ViralTrack: short = more than 0 and at most 180 s, inclusive;
zero, missing, null and invalid durations are not short; the foundation's `is_short` never decides; the name is unchanged. The foundation's `only_shorts`/`exclude_shorts` are always sent `false`; with a filter set, 1000 candidates are
requested and the caller gets at most `limit`; a filtered page has no `total` and carries a note; no Shorts funnel stage exists. Documents updated: capability text, `DiscoveryQuery`/`SearchQuery` comments, metric inventory, provider boundary, Phase 2
test plan (case D5 now automated), roadmap, D1 closure.

**Engagement-rate audit (read only; the sort is unchanged).** Evidence from the real upstream route on a synthetic corpus (`sort_by=engagement`, all videos 10,000 views):

| Video | likes | comments | upstream `engagementRate` | Displayed by ViralTrack |
|---|---|---|---|---|
| a | 500 | 100 | 6.0 | 6.0 |
| b | 200 | 100 | 3.0 | 3.0 |
| likes hidden, 300 comments | hidden | 300 | **3.0** (likes counted as 0) | **omitted** |
| likes hidden, 0 comments | hidden | 0 | **0.0** | **omitted** |
| likes 0, comments 0 (visible) | 0 | 0 | 0.0 | 0.0 |
| both hidden | hidden | hidden | None (last) | omitted |
| no view count | 5 | 5 | None (last) | omitted |

Findings: (1) upstream returns `None` only when views are missing or **both** likes and comments are hidden; with hidden likes and any comment count it treats likes as zero, which understates the rate (`metrics.engagement_rate`, `(likes or 0) + (comments or 0)`).
(2) That understated value **orders** the results: the hidden-likes video with 300 comments ties with the visible 3.0 one, and the hidden-likes video with 0 comments ties with a visible zero. (3) ViralTrack omits the value for any hidden like count
(`REQUIRES_RAW`), so it never shows a different number, but the video is still **placed** by the understated one: a visible rank without a visible reason. Exports: none exist. (4) Eligibility is not affected (no engagement filter exists; the adapter
never sends one). Restricted metrics do not enter this sort; the unavailable value (hidden likes) does influence ranking, as in the lifetime-rate case but milder (understated, not inflated, and not able to top the list).

Smallest safe options, none applied: (a) keep the sort and document the limit; (b) remove `engagement_rate` from the allowlist, as was done for the lifetime rate (no misleading order; loses the sort; simplest and consistent); (c) none involving local reordering is recommended.
Recommendation: (b) if the same standard as the lifetime sort is wanted, otherwise (a). Owner decision needed.

## 13. Engagement-rate sort removed and request validation (final delivery)

The consolidated delivery applied the lifetime-sort precedent to the engagement rate: the foundation counts a hidden like count as zero when it orders by this rate (evidence in section 12 and the real-route test
`test_upstream_orders_by_an_engagement_rate_that_counts_hidden_likes_as_zero`), which breaks the baseline "never silently convert missing values to zero". `engagement_rate` is now refused as a sort with the reason; the value is still displayed when likes
are visible. Approved sorts: `views` and `published_at`. Also validated before any request: `period` (strict `all` or 1 to 9999 `h`/`d`, via `fullmatch`; the old pattern accepted a trailing newline, zero and leading zeros), `limit` (1 to 1000, no booleans)
and `region` (two capital letters). See [PHASE_3_FINAL_COMPLETION_REPORT.md](PHASE_3_FINAL_COMPLETION_REPORT.md) for the consolidated matrix and the decisions that remain for the owner.

