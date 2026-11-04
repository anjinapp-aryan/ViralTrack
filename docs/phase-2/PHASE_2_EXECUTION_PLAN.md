# Phase 2 Execution Plan: YouTube raw-data discovery and ingestion

Date: 2026-11-04. Each batch needs the owner's approval before work starts, and its commit needs separate
approval.

**Status (2026-11-04):**

| Batch | Status |
|---|---|
| 1 | Approved; implemented in the working tree; at its acceptance gate; not committed |
| 2 | Approved with conditions; starts only after Batch 1 passes |
| 3 | Needs a separate approval after Batch 2. It includes the owner's retention verification requirements |
| 4 | **Deferred**: no FastAPI, uvicorn or new API service in this phase |
| 5 | Not started |

Thumbnails: `WORKER_THUMBS=0` for ViralTrack deployments (approved).

Base: `4b0bb9b` (GitHub CI green: 66 passed, 1 skipped). Upstream: `pandich93/youtube-niche-finder` @ `d872014`,
unmodified.

## 0. Owner decisions received (2026-11-04)

| | Decision | Effect on Phase 2 |
|---|---|---|
| A | Prefers proprietary + private. Do not change visibility or add a license until a final confirmation | Nothing applied. Public distribution stays blocked |
| B | acceleration and views_per_follower are conditionally approved. Verify them; keep restricted if compliance is uncertain | Verified in section 1. **Both are proposed as RESTRICTED** |
| C | Shorts label stays restricted | Unchanged. The duration filter stays |
| D | No transcript collection, persistence or transcript-based processing | Unchanged: purge every run; no adapter mapping |
| E | Foundation dashboard and API stay internal-only | Unchanged; no foundation port is published to users |
| — | Google audit not filed; YouTube key not configured | Restricted metrics stay disabled. No claim of live-data validation; demo/test fixtures only |

## 1. Reconciliation of the six ALLOWED metrics (verified against code)

Sources:

- ViralTrack: `viraltrack/providers/youtube/metric_policy.py`, `mapping.py`, `provider.py`.
- Upstream @ `d872014`: `backend/domain/metrics.py` and `backend/application/discovery.py` `_enrich`, which
  serves both `/api/viral` and `/api/search`.

| Metric | Exact upstream computation | Source fields | Findings | Proposed |
|---|---|---|---|---|
| engagement_rate | `round(((likes or 0) + (comments or 0)) / views × 100, 3)`; None if views is 0 or **both** likes and comments are None | `like_count`, `comment_count`, `view_count` | Simple arithmetic. **Defect:** with likes hidden and comments present it returns comments/views and treats likes as 0, which understates the rate | **ALLOWED**, plus an adapter guard: drop the value when raw `likes` is missing |
| views_per_hour_lifetime | `views / max(hours_since(published_at), 1.0)` | `view_count`, `published_at` | Simple division. Matches the policy | **ALLOWED** |
| views_per_hour_24h | `vph_from_history(snapshots, 24)`: (latest views − views at the latest snapshot ≤ 24 h before it) / hours between, floored at 0. Falls back to the **oldest** snapshot when none is 24 h old, so the window can be shorter or longer than 24 h. Drops snapshots before **2026-08-24** (view-count rule change) | `video_stats_history` (≤ 30 days by retention) | Simple arithmetic over stored YouTube numbers. The current policy text ("between two stored snapshots") is right; the docs must say the window varies | **ALLOWED**; correct the docs |
| views_gained_24h | `int(vph24h × 24)` | same as above | **Not a measured delta.** It is the rate times 24, so it is a 24-hour extrapolation whenever the window is not exactly 24 h. The policy text "view delta between two stored snapshots" is wrong | **ALLOWED** (multiplication of an allowed value); correct the basis text and the label to "views per hour × 24" |
| acceleration | discovery: `vph24 / max(2·vph48 − vph24, 0.01)`, None if either is 0/None. `inspection.py` uses `vph24 / vph7d` (a different definition). Upstream also derives "heating up" (> 1.5) and "cooling" (< 0.7) labels and alerts | snapshots | (1) The prior-window rate `2·vph48 − vph24` is an **estimate**, not an observation. (2) With under 24 h of history both rates use the same oldest snapshot, so the value is exactly **1.0**, a manufactured neutral. (3) A prior rate ≤ 0 is floored to 0.01, which produces arbitrarily large values. (4) The definition differs between upstream endpoints. (5) It is close to the guide's "custom score" category | **RESTRICTED** (requires the amendment). Compliance status is uncertain |
| views_per_follower | `views / max(subscribers or 0, 1)` | `view_count`, channel `subscriber_count` (rounded by YouTube; **None when hidden**) | (1) **Defect:** a hidden subscriber count gives `views / 1`, so such videos look extremely "viral". The `max_subscribers` filter also keeps hidden-count channels (`subs is None`). (2) Ordering or filtering a list of many channels' videos by this ratio is close to the guide's Don't "Gamify channel performance by ranking or tracking views between different channels". (3) **Hidden filter today:** `/api/viral` applies `min_views_per_subscriber=1.0` by default and the adapter does not send it | **RESTRICTED** (requires the amendment). Compliance status is uncertain |

Proposed result after Batch 1: **4 ALLOWED** (engagement_rate, views_per_hour_lifetime, views_per_hour_24h,
views_gained_24h), **10 RESTRICTED**, **2 INTERNAL_ONLY**. No other derived value is approved, and unknown names
remain denied by default.

Consequences:

- The sort keys `acceleration` and `vsr` are refused.
- Discovery sends `min_views_per_subscriber=0`, so the result set is no longer filtered by a restricted value.
- "Small channel, big views" remains possible with **raw** filters only: `max_subscribers` and `min_views`.

Hidden-count channels pass `max_subscribers` upstream. Batch 1 documents this, and ViralTrack leaves
`followers` as None for them (it already does).

These are engineering classifications, not legal conclusions. Either metric can return to ALLOWED by changing
one line, after written confirmation in the Google audit or by counsel.

## 2. Scope

**In scope**

1. Metric-policy reconciliation and the defect guards from section 1.
2. **Ingestion control** through the foundation's existing collection:
   - its worker: hot, full, channel, trending, queries and freshness jobs;
   - its documented collection routes.
   Includes a quota-aware ViralTrack interface and an ingestion profile for the deployment.
3. Raw-data discovery through the provider layer: corpus discovery, search, creators and creator history, with
   provenance and origin enforced.
4. An internal ViralTrack read API that serves `Content` only (optional batch, separate approval).
5. Tests on recorded synthetic fixtures and the demo corpus, plus a real-data validation runbook that is
   executed only when a key exists.

**Excluded**

- Instagram or TikTok in any form.
- Trending audio.
- Hashtag discovery.
- Scraping, undocumented endpoints, or bypassing limits or authentication.
- Transcripts: no collection, storage, hook scores or content gaps.
- Restricted metrics in any surface: fields, sort, filter, export, API, UI or MCP.
- The Shorts label.
- Exposing the foundation dashboard, API, MCP, extension or alerts.
- LLM features: AI labels, insights and briefs (`LLM_PROVIDER` stays unset).
- Upstream modifications.
- A public UI.
- Changes to license or visibility.

## 3. Reuse audit (REUSE → ADAPT → COMPOSE → BUILD)

| Need | Existing implementation | Decision |
|---|---|---|
| Collecting from YouTube (videos.list, channels.list, playlistItems.list, search.list, mostPopular chart) | Upstream `backend/application/collecting.py`, `infrastructure/youtube/client.py` | **REUSE** unchanged |
| Scheduled ingestion and snapshots (needed for every views-per-hour value) | Upstream worker (`worker_cycle.py`): hot every 3 h (last 7 d), full daily (30 d), channels daily, trending daily per region, `WORKER_QUERIES` daily, freshness daily | **REUSE** via configuration. ViralTrack adds a documented profile (env), no code |
| Quota guardrails | Upstream client enforces `YOUTUBE_DAILY_UNIT_LIMIT` (default 10,000) and a separate search-call bucket (100/day) before every call; multi-user per-user caps; `GET /api/health` reports what remains | **REUSE**. ViralTrack reads `/api/health` and adds only a pre-flight cap on on-demand calls |
| On-demand collection | `POST /api/collect/channel`, `POST /api/collect/niche`, `POST /api/refresh`, `GET /api/manual-runs` (need `X-NF-Client` and, in multi-user mode, a Bearer token) | **ADAPT**: new provider methods over these routes |
| Data coverage and freshness | `GET /api/coverage`, `GET /api/freshness` | **ADAPT** into a read-only status method |
| Discovery, search, creators, history | Existing ViralTrack adapter over `/api/viral`, `/api/search`, `/api/channels/{id}`, `/api/channels/{id}/history` | **REUSE** (already built). Batch 1 only changes the parameters it sends |
| Retention | ViralTrack retention job (all tables classified; contract test) | **REUSE**. Re-check classifications when the pin moves |
| HTTP framework for an internal ViralTrack API | FastAPI (MIT) and uvicorn (BSD-3) are already upstream dependencies; ViralTrack has none | **COMPOSE** (Batch 4 only). Adding them to ViralTrack is a dependency change that needs approval |
| Per-item fetch time (`collected_at`) | Not exposed by list routes. Snapshot times exist in history routes | **BUILD nothing.** Leave None. An upstream contribution is a separate decision |

Nothing in scope requires writing a YouTube client, a scheduler, a quota system or a metric engine.

## 4. Architecture and data flow

```text
                       (internal network only)
YouTube Data API v3 <-- niche-finder worker ----------------> Postgres (niche-finder schema)
        ^               (scheduled: hot/full/channels/          ^          ^
        |                trending/queries/freshness)            |          |
        |                                                       |   ViralTrack retention job (daily)
        +-- niche-finder web: POST /api/collect/*, /api/refresh |
                        GET /api/viral, /api/search, /api/channels/*, /api/health, /api/coverage
                                     ^
                                     | HTTP, X-NF-Locale: en, X-NF-Client on POST, optional Bearer token
                ViralTrack YouTube adapter (policy-gated mapping, explicit sort and filter params)
                                     ^
                PlatformProvider interface (+ new ingestion capabilities)
                                     ^
                ViralTrack domain: Content / Creator / Metric / Provenance (ALLOWED only)
                                     ^
                [Batch 4, optional] internal ViralTrack read API -> serves Content only
```

Domain additions (Batch 2), all platform-neutral:

- Capabilities: `COLLECT_CREATOR` (ingest one creator's uploads), `COLLECT_QUERY` (keyword search ingestion),
  `REFRESH_STATS`, `INGESTION_STATUS` (quota, coverage, freshness).
- Value types: `IngestionRequest`, `IngestionResult` (items collected, quota units spent as **reported by the
  foundation**, never estimated by ViralTrack) and `QuotaStatus`.
- Base-class defaults raise `UnsupportedCapability`, as today.

The adapter stops being GET-only. This is an **architecture change**: it adds writes to the foundation, and
spending YouTube quota needs the owner's approval of Batch 2. The writes go only to the documented collection
routes, each guarded by a ViralTrack config switch `VT_YOUTUBE_INGESTION_ENABLED` (default `false`).

## 5. API quota considerations

- Every YouTube call is made by the foundation, and its client refuses to exceed the daily pool. ViralTrack
  never calls YouTube directly.
- Read routes (`/api/viral`, `/api/search`, `/api/channels/*`, `/api/health`, `/api/coverage`) cost **zero**
  YouTube quota. They read Postgres only.
- Costs as documented upstream (to re-verify against Google's current quota table during real-data
  validation):
  - **Collect a channel:** about 1 unit per 50 videos, plus 1 unit to resolve a new handle.
  - **Collect a niche:** 1 `search.list` call per page, from its own bucket of 100 calls a day, plus about
    1 unit per 50 videos.
  - **Refresh:** about 1 unit per 50 videos or channels.
  - **Worker trending:** about 3 units per region per day.
- Planned ViralTrack controls:
  - `VT_YOUTUBE_MAX_SEARCH_PAGES` (default 1);
  - `VT_YOUTUBE_MAX_VIDEOS_PER_COLLECT` (default 200);
  - a pre-flight check of `/api/health`, which refuses an on-demand call when the remaining search calls or
    units are below a configured floor;
  - a typed `QuotaExhausted` error mapped from upstream 429 / quota responses.
- Recommended ingestion profile for a single 10,000-unit project:
  - worker defaults;
  - `WORKER_REGIONS` limited to the target markets;
  - `WORKER_QUERIES` of at most about 20 terms, which leaves room for on-demand searches;
  - `WORKER_THUMBS=0`;
  - `LLM_PROVIDER` unset.

  Thumbnail image downloads from `i.ytimg.com` are not needed for raw discovery, and they add stored image
  bytes. This is an owner question.
- With no key configured, ingestion returns the foundation's "key not set" error. Tests assert that error;
  they don't simulate success as if it were real.

## 6. Data-retention implications

- Ingestion fills the same upstream tables that are already classified. No new table is planned. If a pin
  move adds one, the contract test fails until it is classified.
- 30-day rule: the foundation's freshness job re-reads rows older than 25 days, and the ViralTrack job deletes
  anything not refreshed within 30 days. Both must run in every deployment; the compose file already includes
  `retention`.
- Snapshots behind views-per-hour are kept at most 30 days without the amendment, so views-per-hour values are
  limited to recent videos, which suits viral discovery.
- `chart_snapshots` and `chart_entries` (mostPopular) are purged on the statistics window.
- `thumbnail_archive` stays on the text window. With `WORKER_THUMBS=0` it stays empty.
- Transcripts are still purged every run.
- ViralTrack's own data:
  - Ingestion requests and results are not persisted in Phase 2 (logs record counts only).
  - If Batch 4 adds a cache, it must be in-memory or have its own retention rule, which goes into
    DATA_RETENTION_POLICY.md and `policy.py` first.
- Ingestion with origin `real` is possible only with a key. Demo seeds remain origin `demo` and are rejected as
  real.

## 7. Test strategy

| Layer | Tests |
|---|---|
| Policy (Batch 1) | Updated counts (4/10/2). `acceleration` and `views_per_follower` are never mapped and their sorts are refused. Discovery sends `min_views_per_subscriber=0`. `engagement_rate` is dropped when likes are hidden. Basis texts match the formulas (table-driven) |
| Contract | Existing: every upstream numeric field is classified; every allow-listed parameter is checked. New: the adapter's POST body contains only allow-listed keys; no write route outside the collection allow-list can be called |
| Ingestion (Batch 2) | `httpx.MockTransport` with recorded synthetic responses covering: success, key not set, quota exhausted (429), manual-run cooldown (429 + Retry-After), 403 without `X-NF-Client`, ingestion disabled by config (no request made), pre-flight floor refusal (no POST made). Ids are percent-encoded |
| Provenance | Collected items keep origin and provider. `collected_at` stays None for list items. Quota units are copied from the foundation response, never computed |
| Live foundation (demo corpus, no key) | Status and coverage read correctly. A collect call returns the typed "key not configured" error and the corpus is unchanged |
| Retention | The existing suite on the real DDL. A test that rows created by a demo ingestion path are deleted at 30 days |
| Real data | Only with a key: the REAL_DATA_VALIDATION.md runbook, with a quota budget of at most 50 units. Its results are recorded verbatim, or `REAL_DATA_VALIDATION_BLOCKED` |
| Regression | Full ViralTrack suite plus ruff in CI. The upstream suite (Docker) runs only if the pin moves |

## 8. Acceptance criteria

1. The metric inventory in code, DERIVED_METRIC_POLICY.md and METRIC_INVENTORY_AND_APPROVAL.md agree exactly:
   the same names, counts and formulas. A test enforces the counts.
2. No restricted or internal value is reachable through fields, sort, filter or request parameters. Each path
   is covered by a test.
3. Ingestion is off by default, makes no request when disabled, uses only documented collection routes, and
   reports the quota spent as the foundation reports it.
4. Every `Content` carries provenance and an origin. Demo data can't pass as real.
5. Retention covers every table that ingestion writes. The contract test is green.
6. Upstream submodule unchanged at `d872014`.
7. CI is green. Local full run (Postgres plus demo foundation) has 0 failures. Results are recorded in
   TEST_RESULTS.md.
8. Without a key, real-data validation reads `REAL_DATA_VALIDATION_BLOCKED — YOUTUBE_API_KEY_NOT_CONFIGURED`.

## 9. Batches and phase gates

| Batch | Content | Files (expected) | Gate to start | Gate to finish |
|---|---|---|---|---|
| **1. Metric reconciliation** | Section 1: acceleration and views_per_follower made RESTRICTED; basis text fixed; engagement guard; `min_views_per_subscriber=0`; docs and tests | `metric_policy.py`, `mapping.py`, `provider.py`, tests, 3 policy docs | **Owner approves section 1** | Tests and CI green; inventory reconciled |
| **2. Ingestion interface** | Platform-neutral ingestion capabilities and value types; adapter methods over the collect, refresh, health and coverage routes; config switches and quota floor; typed errors | `domain/capabilities.py`, `domain/models.py`, `providers/base.py`, `providers/youtube/{client,provider}.py`, `config.py`, `.env.example`, tests, PROVIDER_BOUNDARY.md | Batch 1 done. **Owner approves writes to the foundation** (architecture change) | Mock and demo tests green; ingestion disabled by default |
| **3. Ingestion profile and retention check** | Documented worker profile; compose comments only; retention verification of ingested rows | `docs/phase-2/INGESTION_PROFILE.md`, `.env.example`, retention tests | Batch 2 done. Owner answers the thumbnail question | Docker run: worker plus retention, nothing skipped |
| **4. Internal read API (optional)** | Small service serving `Content` JSON (discover, search, creator, status) and a CSV export from `Content`; localhost only; no MCP | new `viraltrack/api/`, `pyproject.toml` (FastAPI, uvicorn), compose service, tests | **Owner approves the dependency and the surface** | Leak tests on every route and export |
| **5. Real-data validation and Phase 2 gate** | Run the runbook when a key exists; update docs; Phase 2 release gate | docs | Key configured (else recorded as blocked) | Gate report; stop for approval |

Phase 2 ends with a release-gate document like Phase 1.2's. No commit or push happens without the owner's
separate approval for each batch.

## 10. Questions for the owner

1. Approve section 1, which makes acceleration and views_per_follower **RESTRICTED** and leaves 4 ALLOWED?
2. Approve Batch 2's change from a GET-only adapter to one that may trigger collection (off by default)?
3. Thumbnail downloads (`WORKER_THUMBS`): turn them off for ViralTrack deployments? Recommended: yes.
4. Batch 4 (internal read API with FastAPI): include it in Phase 2 or defer it?
