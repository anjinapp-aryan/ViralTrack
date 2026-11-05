# D1 closure report: restricted-sort audit, subscriber-filter semantics, known defects

Date: 2026-11-05. Audit only. No production code, CI workflow, schema, Compose file or upstream file changed; no package
installed; no YouTube request; no quota spent. Nothing committed.

Labels: **VERIFIED** (read in source or observed by running the real upstream offline), **INFERRED**, **PROPOSED**,
**UNKNOWN**, **BLOCKED**. Upstream paths are relative to `upstream/youtube-niche-finder/backend/`. Earlier documents
are referenced, not repeated: [YOUTUBE_DISCOVERY_AUDIT.md](YOUTUBE_DISCOVERY_AUDIT.md),
[D1_OFFLINE_DISCOVERY_TEST_REPORT.md](D1_OFFLINE_DISCOVERY_TEST_REPORT.md).

## 0. Repository state

Initial state (recorded before any work in this assignment), `main` equal to `origin/main` at `5ed12ec`:

```text
 M docs/phase-2/DISCOVERY_TEST_PLAN.md
A  docs/phase-2/PHASE_2_COMMIT_MAP.md
M  docs/phase-2/PHASE_2_EXECUTION_PLAN.md
A  docs/phase-2/PHASE_2_RELEASE_READINESS.md
A  docs/phase-3/DISCOVERY_ARCHITECTURE_PROPOSAL.md
AM docs/phase-3/DISCOVERY_EXECUTION_ROADMAP.md
A  docs/phase-3/DISCOVERY_REQUIREMENTS.md
A  docs/phase-3/DISCOVERY_VALIDATION_STRATEGY.md
A  docs/phase-3/OPEN_SOURCE_REUSE_AUDIT.md
A  docs/phase-3/YOUTUBE_DISCOVERY_AUDIT.md
?? docs/phase-3/D1_OFFLINE_DISCOVERY_TEST_REPORT.md
?? tests/support/
?? tests/test_discovery_d1_adapter.py
?? tests/test_discovery_d1_policy.py
?? tests/test_discovery_d1_upstream.py
```

The staged files belong to the owner and were left staged. The upstream submodule is at `d872014`. This assignment adds only
the three documents listed in the final report.

## 1. Task A: restricted sort audit

### 1.1 Verified behaviour

| Question | Answer | Evidence |
|---|---|---|
| Can any ViralTrack request inherit `sort_by=viral`? | **No today.** Both call sites always put a mapped `sort_by` in the request | `viraltrack/providers/youtube/provider.py` `_sort` (line 140), `discover_content` (160), `search_content` (175); tests `test_default_sort_is_by_raw_views`, `test_only_approved_metrics_and_raw_values_can_be_requested_as_the_order` (D1 policy), `test_every_restricted_or_internal_metric_is_refused_as_a_sort_before_any_request` |
| Upstream default order | `/api/viral`: `sort_by="viral"` (restricted `viralScore`); `/api/search`: `sort_by="outlier"` (restricted) | `interfaces/http/api.py:658` and `:724`; test `test_upstream_viral_route_defaults_are_the_ones_the_audit_names`, `test_the_default_upstream_order_is_a_restricted_score_so_it_must_never_be_relied_on` |
| Are restricted metrics computed before filtering? | **Yes.** `load_window` calls `_enrich` for every row in the window, then the Python filters run | `application/discovery.py:97-134`, `_enrich` at `:195-251`, filters at `:306-332` |
| Do they influence eligibility? | Only through two filters: `min_views_per_subscriber` (default 1.0) and `min_outlier_score` (default None). ViralTrack sends `min_views_per_subscriber=0` and never sends `min_outlier_score` | `discovery.py:321,325`; `provider.py:160-172`; test `test_adapter_never_filters_or_ranks_by_restricted_scores` |
| Do they influence ordering? | Yes when the key is a restricted one. `rows.sort(key=...)` uses `SORTS.get(sort_by, "viralScore")`: **an unknown `sort_by` silently falls back to the restricted `viralScore`** | `discovery.py:255-267, 331` |
| Text search ordering | With a `query`, results are ordered by `semanticScore` (INTERNAL_ONLY) and `sort_by` is ignored | `application/search.py:76-93`; policy rule `semantic_score` |
| Ties | `BASE_SQL` has no `ORDER BY`, so equal sort values come back in database order, which is not guaranteed stable | `discovery.py:30-41` |

### 1.2 Exact request-parameter matrix (current adapter)

`/api/viral` (discovery):

| Parameter | Value ViralTrack supplies | Upstream default if omitted | Policy status | Risk if omitted |
|---|---|---|---|---|
| `period` | caller's, validated by `^(all\|\d{1,4}[hd])$` | `7d` | raw/neutral | wrong window |
| `period_by` | not sent | `published` | neutral | none |
| `sort_by` | mapped: `views`, `published`, `vph`, `vph_lifetime`, `velocity`, `engagement` (restricted keys only with the amendment) | **`viral` (restricted)** | allowed set only | **restricted ordering** |
| `limit` | caller's (default 24) | 24 | neutral | none |
| `region`, `niche` | caller's, omitted when None | none | raw | none |
| `max_subscribers` | caller's, **omitted when None** | **10000** | raw | silent restriction (D1 root cause) |
| `min_views` | caller's, **omitted when None** | **10000** | raw | silent restriction |
| `min_views_per_subscriber` | always `0` | **1.0** | **restricted metric as a filter** | restricted metric decides eligibility |
| `min_outlier_score` | not sent | None (off) | restricted | none today |
| `exclude_shorts`, `only_shorts` | both always sent | `exclude_shorts=True` | Shorts label restricted; filter is a duration test (<= 180 s) | silent removal of short videos |
| `category_id`, `preset` | not sent | None | raw / n.a. | none |

`/api/search` (corpus search):

| Parameter | Value ViralTrack supplies | Upstream default if omitted | Policy status | Risk if omitted |
|---|---|---|---|---|
| `query` | caller's | None | neutral, but **ordering by internal `semanticScore`** | order disclosed |
| `period` | caller's (default `all`) | `all` | raw | none |
| `sort_by` | mapped, always sent | **`outlier` (restricted)** | allowed set only | restricted ordering (when no query) |
| `limit` | caller's (default 30) | 30 | neutral | none |
| `niche` | caller's | None | raw | none |
| `exclude_shorts`, `only_shorts` | both always sent | False / False | as above | none |
| `max_subscribers` | not sent | **None = unbounded** | raw | none |
| `min_outlier_score` | not sent | 0.0 (falsy, off) | restricted | none |
| `min_video_length`, `max_video_length`, `min_rpm`, `max_rpm`, `min_ypp_status`, `languages` | not sent | None | rpm and YPP are restricted | none today |

(Request shape verified by `tests/test_discovery_d1_adapter.py` and the SENT_PARAMS check in `tests/test_youtube_provider.py`.)

### 1.3 Findings

1. **VERIFIED: response sanitising is not what protects ordering; the explicit `sort_by` is.** Removing restricted
   fields from the response would not prevent a restricted order, and the adapter currently relies on a single
   convention (always name the sort) with no structural guard.
2. **VERIFIED latent hazard:** an upstream-side typo or a future mapping value that is not a key of upstream `SORTS`
   silently orders by restricted `viralScore`. No test checks that every mapped value exists upstream.
3. **VERIFIED latent hazard:** `FoundationClient.get` is a generic method; a new call to `/api/viral` or `/api/search`
   that omits `sort_by` would inherit the restricted default without any failure.
4. **VERIFIED:** text search is ordered by an INTERNAL_ONLY score by upstream design (audit F-5). Separate decision.
5. **VERIFIED:** equal sort values have no guaranteed order (no `ORDER BY`). Affects reproducibility, not policy.

### 1.4 Smallest safe prevention (PROPOSED, not implemented; belongs to D3)

1. One function builds the ranked-route parameters and refuses to return without `sort_by` in a fixed set
   `{views, published, vph, vph_lifetime, velocity, engagement}` (plus the restricted keys only when the amendment is
   held). About ten lines in `provider.py`.
2. `FoundationClient.get` raises for `/api/viral` and `/api/search` when `sort_by` is missing (fail closed). About five lines.
3. Two tests: every `_SORTS` upstream value is a key of upstream `SORTS` (read the dict with `ast`, like the route
   defaults), and every request to a ranked route has `sort_by` in the safe set.
4. Text-search ordering: owner decision (section 7).

## 2. Task B: subscriber-filter semantics

D1 established (test file `tests/test_discovery_d1_upstream.py`): omitted = 10,000; `0` keeps only 0 or hidden subscribers;
negative keeps only hidden; empty and null spellings return HTTP 422; large integers pass the synthetic corpus.
There is **no unbounded value**, and none is documented upstream (`docs/http-api.md` lists `max_subscribers=10000`).

| Alt | Implementation | Data needed | Accuracy | Quota | Limits | Policy | Maintenance |
|---|---|---|---|---|---|---|---|
| A. `/api/viral` | `if max_subscribers is not None:` filter in Python (`discovery.py:311`); HTTP cannot send None | none extra | exact for any bound it is given | 0 | no "no limit"; hidden-subscriber channels always pass | raw values only; default sort is restricted so ViralTrack must name it | low (already used) |
| B. `/api/search` | `max_subscribers` default **None = unbounded**, applied in SQL only when given (`discovery._filters`, `search.py:27`) | none | exact; **truly unbounded when omitted** | 0 | **no `min_views`**, no `max_channel_video_count`/language over HTTP; **no funnel, no `matched`**; default sort restricted; text query orders by internal score | same | low |
| C. Local filtering | ViralTrack reads candidates from B with a `limit` at least the corpus size, then filters on `Creator.followers` and `views` itself | `channelSubscribers`, `views` are in each result | exact **only if the page holds the whole candidate set**; there is no offset (D1 test `test_there_is_no_offset_parameter...`), so truncation by `limit` silently loses candidates | 0 | needs the corpus size (from `/api/stats` or `/api/health` database counts) to set `limit`; reimplements two comparisons and its own funnel | raw comparisons only | medium: duplicates upstream logic (REUSE says avoid) but small |
| D. Other endpoints | `/api/niches/{slug}/videos` returns restricted outlier fields and no subscribers; `/api/outlier-channels` has `max_subscribers=None` but filters by the restricted multiplier | n.a. | n.a. | 0 | unsuitable | restricted metrics decide eligibility | n.a. |
| E. Practical upper bound on A | send a large integer as `max_subscribers` | none | exact below the bound; excludes any channel above it | 0 | **a bounded operational compromise, not "unlimited"**; the value must be chosen and justified | raw | very low |

**Recommendation (PROPOSED):** for the discovery route use **E as an explicitly labelled bounded compromise**, set to a
named constant with a documented rationale and a test that pins it, *and* report in the response metadata that the
subscriber filter was "bounded at N", never "off". Prefer a bound grounded in data over a round number: the Batch 5
approach of recording the largest subscriber count seen in the collected channels is not exposed by the API (UNKNOWN), so
the bound stays a constant. Do not use `2147483647` and call it unlimited. If the owner wants a true no-limit list, the
only exact route is **B** (no subscriber filter at all), accepting no views filter, no funnel and an unvalidated order;
**C** can add the views filter locally for lists small enough to fit one page.

Whether any real channel exceeds a chosen bound is an INFERENCE about YouTube data; it is not proven by any test.

## 3. Nine strict xfail tests and the six non-filter defects

The nine are `tests/test_discovery_d1_adapter.py` (7) and `tests/test_discovery_d1_policy.py` (2). Three concern the root
cause (unset filters); six are the defects below. All remain `xfail(strict=True)`: none was weakened or removed, and the
full suite still reports them as xfailed.

| # | Defect | Reproduction test | Actual | Expected | Source | Minimal correction | Compat impact | Stage |
|---|---|---|---|---|---|---|---|---|
| 1 | Foundation funnel dropped | `test_the_foundations_funnel_reaches_the_caller` | `ContentPage` has `items`, `total`, `notes` only | the funnel and effective filters reach the caller | `provider.py:149-158` (`_page`), `domain/models.py` `ContentPage` | add optional `funnel` and `filters` fields (default None); map and validate `body["funnel"]` | additive; existing callers unaffected | **D3** |
| 2 | Malformed entries dropped silently | `test_invalid_entries_are_not_silently_dropped` | `if isinstance(r, dict)` at `provider.py:154` drops others | counted and reported, or the call fails | same line | count the dropped, add a note; or raise `ProviderError` | a page that used to be quietly smaller now carries a note | **D3** |
| 3 | Duplicate video ids returned | `test_duplicate_video_ids_in_one_response_are_collapsed_or_flagged` | both copies returned | collapsed (first wins) with a note | `provider.py:154` | dedupe by `content_id` | low; the foundation's primary key makes duplicates impossible from a healthy server | **D3** |
| 4 | JSON boolean accepted as total | `test_a_boolean_total_is_not_a_count` | `isinstance(total, int)` accepts `True` | unknown (`None`) | `provider.py:157` (the ingestion parser `_int` at `ingestion.py:17` already excludes bool) | reuse the same guard | none in practice | **D3** (trivial) |
| 5 | Stale velocity shown as current | `test_velocity_from_stale_snapshots_is_withheld_or_flagged` | `vph24h` from two snapshots 20 days old is mapped | withheld or flagged | upstream `domain/metrics.py:314-334` computes it; `mapping.py` maps it | **BLOCKED on data**: no snapshot time reaches ViralTrack. Options: withhold the 24-hour metrics until the history endpoints are mapped (D6), or label them "window unknown" (already partly done) | withholding removes an approved metric from output | **D6** (cannot be fully fixed in D3); owner decision |
| 6 | Undated video gets lifetime velocity | `test_an_undated_video_has_no_lifetime_velocity` | upstream `hours_since("")` returns 0, so velocity = views / 1 h | no `views_per_hour_lifetime` | upstream `domain/periods.py:83-91`, `metrics.py:292` | in `mapping._derived`, skip `views_per_hour_lifetime` when `published_at` is None | removes a meaningless value for undated items | **D3** (trivial) |

None of the six belongs in D2: D2 is limited to collection, not discovery filtering or mapping.

## 4. D1 closure

| Item | State |
|---|---|
| Offline tests | 123 new (35 adapter, 53 upstream-backed, 35 policy); latest full run 399 passed, 0 failed, 2 skipped, 9 xfailed (database plus upstream Python); 335 / 68 skipped / 7 xfailed with only a database (what CI has); 311 / 92 / 7 plain |
| Network | zero attempts in every upstream-backed test; no key set |
| Strict xfails | 9, all preserved |
| CI coverage | the 53 + 35 upstream-backed tests mostly skip in GitHub CI; proposal in [D1_CI_INTEGRATION_PROPOSAL.md](D1_CI_INTEGRATION_PROPOSAL.md) |
| Production change | none |
| Open question | the unbounded-subscriber design (section 2) and the ordering questions (section 7) |

## 5. Policy statement

Unchanged: four approved metrics; restricted and internal-only metrics stay out of filtering, sorting, ranking, APIs and
exports; no composite score, breakout score, cross-channel ranking, forecasting, Shorts classification, similar-video
discovery, transcripts, thumbnails, LLM, Instagram or TikTok. Technical feasibility is not treated as policy approval.

## 6. Documents of this assignment

[D1_CLOSURE_REPORT.md](D1_CLOSURE_REPORT.md) (this file), [D1_CI_INTEGRATION_PROPOSAL.md](D1_CI_INTEGRATION_PROPOSAL.md),
[D2_IMPLEMENTATION_SPEC.md](D2_IMPLEMENTATION_SPEC.md).

## 7. Owner decisions that source inspection cannot settle

1. Which subscriber approach for discovery: bounded constant (E), no filter via search (B), or local filter (C); and the value of the bound if E.
2. Whether text-search results may be ordered by the internal semantic score (audit F-5), or text search must be refused until an allowed order exists.
3. Whether the 24-hour velocity metrics may be shown while their snapshot recency is unknown (defect 5).
4. Whether the Shorts duration filter may stay in the discovery request (audit F-6).
