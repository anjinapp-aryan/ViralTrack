# Discovery architecture proposal (Task H)

Date: 2026-11-05. PROPOSAL. Nothing here is implemented or approved. The upstream submodule stays unmodified.

## 1. Principle

The smallest change that fits: **keep the existing chain** and fix its boundary.

```text
ViralTrack domain  ->  PlatformProvider  ->  YouTube adapter  ->  foundation HTTP API  ->  YouTube Data API
```

The audit shows the discovery engine, quota system, scheduler, snapshots and storage already exist upstream. The
failure was at the adapter boundary (omitted parameters re-activating hidden defaults). No new service, scheduler,
collection client, quota system or database abstraction is proposed.

## 2. Responsibility split

| Concern | Belongs to | Exists today | Change proposed |
|---|---|---|---|
| Calling YouTube, quota reservation and counters | Foundation | Yes (`yt._get`, `/api/health`) | None |
| Collection (channel, keyword, refresh) | Foundation | Yes | None |
| Scheduling (hot/full refresh, daily queries, RSS, freshness) | Foundation worker | Yes | None; configure via compose environment |
| Storage of videos, channels, snapshots, niches | Foundation PostgreSQL | Yes | None |
| Metric computation | Foundation (`domain/metrics.py`) | Yes | None |
| Candidate eligibility filters (subs, views, window, shorts, niche) | Foundation (`/api/viral`) | Yes | **None upstream**; ViralTrack sends explicit values |
| Parameter normalisation: "unset" means "unbounded", never "default" | **ViralTrack adapter** | **No (the defect)** | **ADAPT** |
| Passing `period` (publishedAfter) to keyword collection | **ViralTrack adapter** | No | **ADAPT** (one field) |
| Metric policy (4 / 10 / 2), restricted-sort refusal | ViralTrack | Yes | None |
| Provenance (`collected_at` unknown, `foundation_first_seen_at`, `retrieved_at`) | ViralTrack | Yes | None |
| Funnel (counts removed by each filter) | Foundation computes it; ViralTrack drops it | Partly (`notes` carries the hint only) | **ADAPT**: surface the funnel as structured data |
| Ranking explanation (which filters passed, metric values, formulas, confidence labels) | ViralTrack | No | **BUILD** (small, pure functions over `Content`) |
| Confidence labels (`no_history`, `stale`, `low_sample`, `hidden_likes`) | ViralTrack | No | **BUILD** (same module) |
| Candidate tracking / watchlist | Foundation (`tracked_channels`, `/api/channels/track`) | Yes | **COMPOSE** via HTTP (later) |
| Alerts / topic watch | Foundation | Yes (use restricted metrics internally) | Out of scope for ViralTrack output |
| Discovery history | Foundation snapshots and `saved_items` | Partly | **Do not add ViralTrack storage** (see 4) |
| External API / UI | ViralTrack (Batch 4, deferred) | No | Decision D5 |

## 3. Components to add (all inside existing modules)

1. **`viraltrack/providers/youtube/provider.py`, `discover_content`:** build the parameter set so every filter is
   explicit: `max_subscribers` = caller value or a documented "unbounded" sentinel; `min_views` = caller value or 0;
   `min_views_per_subscriber` stays 0. The sentinel must be a very large integer, because `0` does not disable
   `max_subscribers` upstream (audit F-2). Add a test that fails if any filter parameter is omitted.
2. **`collect_query`:** accept and send `period`; document that the foundation orders by all-time views.
3. **`ContentPage`:** add an optional structured `funnel` (list of stage name and remaining count) and the effective
   filters actually sent. The domain type is platform-neutral; the YouTube adapter fills it from the foundation's
   `funnel` field.
4. **A small `viraltrack/discovery/` module (pure functions, no I/O):** `explain(content, query) -> Explanation` with
   the filters passed, the metric values and their provenance, formula text from `MetricRule.basis`, and confidence
   labels. No composite score.
5. **No persistence layer.** ViralTrack owns no tables today and nothing in this proposal adds one.

## 4. Discovery history and tracking

- Persisting discovery results in ViralTrack would create new provider-data storage that needs its own 30-day retention
  rule, schema and migration. **Not proposed.**
- History already exists upstream: `video_stats_history` snapshots (written by collection and refresh) and the worker
  schedule. Historical comparison therefore means *reading snapshots through the foundation's API*, which is already
  covered by retention.
- Tracking a candidate means adding its channel to the foundation watchlist (`POST /api/channels/track`, 1 unit to
  resolve a handle) and letting the worker refresh it. Compose, do not rebuild.
- **UNKNOWN:** whether the foundation exposes per-video snapshot series over HTTP in a form ViralTrack can map
  (`/api/videos/trajectory` and `/api/channels/{id}/velocity` exist; they were not read in detail). To be verified in D1.

## 5. Can the current architecture support the required functions?

| Function | Supported by | Gap |
|---|---|---|
| Candidate discovery | Foundation collection + worker | Adapter `period`; category not passable |
| Candidate normalisation | `mapping.map_video` | None |
| Eligibility filtering | `/api/viral`, `/api/search` | Explicit-parameter defect; `max_channel_video_count`, language not exposed on `/api/viral` |
| Explainable ranking | Single-metric ordering already allowed by policy | Explanation module (BUILD, small) |
| Discovery history | Upstream snapshots | Mapping of series (verify) |
| Candidate tracking, watchlists | Upstream | Adapter methods (COMPOSE) |
| Historical comparison | Upstream snapshots | Same |

## 6. What this does not do

No microservice, queue, second scheduler, cache, vector store, new dependency, ViralTrack database table, forecasting,
composite score, LLM, transcript or thumbnail processing. No change to the upstream submodule: where the upstream behaves
badly (F-2, hint text, no `order` over HTTP), ViralTrack works around it and documents it.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Upstream default thresholds change when the submodule pin moves | Adapter sends every filter explicitly; a contract test asserts the full parameter set |
| "Unbounded" sentinel hits an upstream integer limit | Use a value well inside a signed 32-bit integer; test against the real upstream function using the demo corpus |
| Ordering by semantic similarity in text search | Policy decision (audit F-5) before exposing text-search ordering |
| Stale numbers presented as current | Confidence label and freshness fields; never rank-claim a trend without history |
