# Discovery test plan (Phase 2, not executed)

Status: plan only. **No YouTube API request was made to prepare it**, and none may be made until the owner approves a
run. Every case below is a local read of data already in a foundation database, so discovery itself costs no quota;
only the data-preparation step in section 2 does.

## 1. Why

Batch 5 collected one channel and one keyword, but `discover_content(period=30d)` returned 0 items, because the
foundation's defaults (`max_subscribers` 10,000, `min_views` 10,000) removed everything. Discovery was therefore never
shown to return real items. This plan makes that observable.

## 2. Data (needs owner approval, spends quota)

- A fresh, empty test database and the foundation API only (no worker). Same safeguards as Batch 5: ingestion enabled in
  the test process only, thumbnails and LLM off, key never printed.
- Budget: at most 15 units and 1 search call. Collect **one** channel with a cap of 20 videos (about 3 units) and
  **one** keyword with one page (about 3 units).
- Choose a channel whose recent videos fall inside the test window, and record its subscriber count from the
  foundation's own response. Do not pick a second channel to fix a bad sample.
- Use the 120-second collection timeout, and read `/api/health` before and after each step.

## 3. Cases (all read-only)

| # | Query | Expect |
|---|---|---|
| D1 | `DiscoveryQuery(period="all", min_views=0, max_creator_followers=2_147_483_647)` (see 3.1: **never 0**) | Non-empty; every item `real_provider_data`; no restricted metric; ordered by views descending |
| D2 | Same with `sort="published_at"` | Ordered newest first; `published_at` aware and not in the future |
| D3 | `min_views` above the largest sample view count | Empty page with the foundation's hint in `notes`; not an error |
| D4 | `max_creator_followers` below the channel's subscribers | Items from that channel excluded; funnel/hint present |
| D5 | `short_form=True` and `False` | Result sets differ only by the filter; no Short label unless approved (classification stays restricted) |
| D6 | `sort="outlier_score"`, `acceleration`, `views_per_follower` | `RestrictedMetric`, no request sent |
| D7 | `niche="<label>"` for the keyword niche | Only items collected under that niche |
| D8 | `limit` 1 and 100 | Honoured |
| D9 | Request check (recorded transport) | Every discovery call sends `min_views_per_subscriber=0` |
| D10 | Provenance of all items | `collected_at` None; `foundation_first_seen_at` aware UTC inside the collection window; raw and derived separated |
| D11 | Quota check | `/api/health` units and search calls identical before and after D1 to D10 (discovery spends nothing) |

### 3.1 Correction (D1 audit, 2026-11-05): what "no subscriber limit" means

The first version of this plan used `max_creator_followers=0` for D1. **That was wrong.** Verified against the pinned
upstream (`application/discovery.py:311`, exercised offline by `tests/test_discovery_d1_upstream.py`):

| Value sent as `max_subscribers` | Upstream behaviour |
|---|---|
| omitted | Default **10,000** is applied (route `api.py:661`) |
| `0` | Filter is **active**: keeps only channels with 0 or hidden subscribers |
| negative | Filter active: keeps only hidden-subscriber channels |
| empty string, `null`, `None` | HTTP 422 (not an integer) |
| `2147483647` or `1000000000000` | Passes every channel in the test corpus (including hidden ones) |

There is no literal "unbounded" over HTTP. A very large integer behaves as unbounded for any real channel, but that is
an inference about YouTube data, not a guarantee. `min_views=0` does disable the views filter (the check is
`if min_views:`). The current adapter cannot yet send an explicit subscriber bound when the caller leaves it unset
(audit F-1), so this live case must wait for the D3 adapter fix or use the raw HTTP route.

## 4. Offline groundwork (no quota, can run now)

The fixtures in `tests/fixtures/niche_finder/` already cover D3, D6, D7, D9 and D10 with synthetic data. The approved
run would add D1, D2, D4 and D5 on real data. Before it, add a recorded-transport test for D9 on `/api/viral` with
an explicit large subscriber bound (not 0; see 3.1). D1 delivered it in `tests/test_discovery_d1_upstream.py`.

## 5. Acceptance

All cases pass, D11 shows zero quota, no restricted metric appears, and nothing persists outside the test database,
which is dropped afterwards (verified by name first) with only aggregate evidence kept.
