# Discovery validation strategy (Task G)

Date: 2026-11-05. PROPOSAL. Offline first. No real discovery is executed by this document.

## 1. Measurements

Every discovery call should be able to report these (the foundation already returns the funnel; the rest are
computed by ViralTrack from the response):

| Measure | Definition | Source today |
|---|---|---|
| Raw candidates | Videos in the collected corpus before any filter | Funnel first step ("videos in window") plus `/api/stats` |
| Eligible candidates | Videos passing all filters | `matched` |
| Excluded per filter | Count removed at each funnel step | Foundation `funnel` (dropped by the adapter today) |
| Final results | Items returned (<= limit) | `results` |
| Duplicate rate | Share of returned items with a repeated `video_id` | Computed; expected 0 (primary key upstream) |
| Data freshness | Age of the newest snapshot per item; `foundation_first_seen_at` | Snapshot series (to verify), provenance |
| Missing-metric rate | Share of items lacking each approved metric (`vph24h`, `engagement_rate`) | Computed |
| Explanation coverage | Share of results with a complete explanation | D4 |
| Quota used | Units and search calls from `/api/health` before and after | Existing |
| Latency | Wall time of the call | Measured by the test |
| Source coverage | Share of candidates from each source (keyword, channel, worker) | Niche link and tracked flag |

## 2. Datasets and fixtures (all synthetic, no YouTube data)

1. **Recorded contract fixtures** in `tests/fixtures/niche_finder/` (already present: viral, search, shorts, channel,
   history). Keep them; label them synthetic.
2. **A deterministic synthetic corpus generator** (seeded) used by tests: videos with controlled publish dates, view
   counts, likes (visible or hidden), snapshots (0, 1 or many), channels (hidden or visible subscribers, small or large),
   duplicates and invalid ids. One generator feeds both mock responses and, optionally, the demo foundation.
3. **The demo-seeded foundation** (`NICHE_DB_SCHEMA=demo`, no API key, zero quota) to run the **real upstream filter
   code** against known data. This is how upstream semantics (for example `max_subscribers=0`) are confirmed without
   YouTube. It is local and already used in Phase 1.
4. **Replay of the Batch 5 shape:** 70 videos, 3 in the window, channels above 10,000 subscribers, one snapshot each.
   Expect the old adapter to return 0 and the corrected adapter to return the stored candidates.

## 3. Test matrix (offline)

| # | Case | Setup | Expected |
|---|---|---|---|
| 1 | Zero results | Filters exclude everything | `[]`, funnel names the filter that emptied the list, hint present, not an error |
| 2 | One result | Exactly one eligible video | One item, `total` 1 |
| 3 | Many results | More than `limit` eligible | `limit` items, `total` is the full count, order follows the chosen metric |
| 4 | Duplicates | Same `video_id` twice in a response | Rejected or collapsed with a counted warning; duplicate rate reported |
| 5 | Missing metrics | No snapshots | `views_per_hour_24h` absent, label `no_history`, item still listed under non-velocity ordering |
| 6 | Hidden likes | Likes absent | `engagement_rate` omitted, label `hidden_likes`, never 0 |
| 7 | Stale data | Old snapshot | Label `stale` when freshness is known; `unknown` when not |
| 8 | Invalid channel | Channel id not matching `UC...` | Rejected (existing id check), whole call does not silently drop it |
| 9 | Restricted metrics | Upstream payload contains all restricted fields; sort requested by each | Never in `Content`, `derived`, explanation, sort or export; `RestrictedMetric` raised for sort |
| 10 | Pagination | `limit` 1, 24, 100; `matched` larger | Only `limit` returned; no offset parameter exists; this is documented |
| 11 | Filter combinations | Cross product of window, subscribers, views, shorts, niche | Funnel counts are consistent (non-increasing), every request carries every parameter |
| 12 | Quota exhaustion | `/api/health` below floor, or 429 `QuotaExceeded` | `QuotaExhausted`, zero POSTs, no retry |
| 13 | Partial upstream failure | 500 on funnel-bearing call, timeout on collection | Typed error; collection timeout is `ProviderTimeout` with `outcome_unknown`; no retry |
| 14 | Unset filter | `DiscoveryQuery()` with all defaults | Request contains explicit, non-restrictive values (the regression test for the root cause) |
| 15 | Sentinel | `max_subscribers` sentinel against the demo foundation | All channels pass; `0` is shown to remove them (documents upstream F-2) |
| 16 | Window semantics | `period` and `period_by` variants | Counts match the fixture's publish dates |

Cases 1, 14 and 15 reproduce the audit's root cause; 14 must fail on the current code.

## 4. Quality gates for D8

- All 16 cases pass offline in CI (no key, no quota).
- Zero restricted fields in any returned object, serialized form or log (searched by name in the tests).
- Every request records its complete filter set; none omitted.
- Explanation coverage 100% of returned items (once D4 exists).
- No composite score anywhere.

## 5. Real-data validation (D7, separate approval)

- Fresh empty database; ingestion enabled only for the run; key never printed.
- Budget stated up front: at most 15 units and 1 search call. Estimate before each spending call; stop if the
  foundation's counters and the estimate disagree.
- Distinguish buckets: `search.list` counts against its own 100/day bucket; other calls against 10,000 units.
- Steps: one keyword with `period`; one channel capped at 20; discovery reads (free); one refresh pass later for a
  second snapshot; compare quota counters before and after the read-only discovery calls (must be unchanged).
- Record: raw, eligible and final counts; funnel; missing-metric rate; freshness; latency; quota; confidence labels.
- Never retry a spending call. Drop the database afterwards, verified by name, and keep aggregates only.
- Independent check of quota: if the owner can supply the Google Cloud console quota view, compare it with the
  foundation's counters (Phase 2 left this unchecked).

## 6. What would count as failure

- A non-empty corpus returning zero results with no explanation of which filter removed the items.
- Any request that relies on an upstream default threshold.
- Any restricted or internal-only value reaching a result, a sort key or an export.
- Quota above budget, or counters that disagree with the estimate.
