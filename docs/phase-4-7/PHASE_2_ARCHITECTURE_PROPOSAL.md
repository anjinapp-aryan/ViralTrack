# Phase 2 (creator intelligence): architecture proposal

Date: 2026-11-07. A proposal; nothing is authorized or started. Evidence: [PHASE_2_CREATOR_INTELLIGENCE_AUDIT.md](PHASE_2_CREATOR_INTELLIGENCE_AUDIT.md). Reuse decisions: [PHASE_2_OPEN_SOURCE_REUSE_AUDIT.md](PHASE_2_OPEN_SOURCE_REUSE_AUDIT.md). Sequencing and gates: [PHASE_2_IMPLEMENTATION_ROADMAP.md](PHASE_2_IMPLEMENTATION_ROADMAP.md).

## 1. Principle

Compose what the foundation already does. ViralTrack adds a policy boundary and a UI. The layering is the one from D5:

```text
web (React) -> ViralTrack API (FastAPI) -> PlatformProvider -> MetricPolicy + Provenance -> foundation HTTP API -> PostgreSQL
```

No new table, scheduler, queue, ingestion path or score is introduced.

## 2. Features split by availability

| Feature | Available upstream | Missing in ViralTrack | Gate |
|---|---|---|---|
| Creator list | derived from discovery (D5 `GET /creators`) | UI page, size and period filters, pagination | none (**2A**) |
| Creator detail (profile) | `GET /channels/{id}` | map three more raw fields; UI page | none (**2A**) |
| Creator's videos | `GET /channels/{id}/velocity` (mixed fields) | provider method, raw-only mapping, API endpoint, UI list | none (**2A**) |
| Creator history chart | `GET /channels/{id}/history` | API endpoint, chart, freshness and gap display | **D6** authorization and a D7 timestamp check |
| Growth over a window | derived from history | arithmetic on two raw snapshots, with both times shown | **D6** and the owner's classification of "growth" |
| Watchlist (read) | `GET /channels/tracked` | API endpoint, UI list, link to the creator page | **D6** |
| Watchlist (add and remove) | `POST /channels/track`, `DELETE` | authenticated write path, quota guard | **D6** and an authentication boundary |
| Alerts | scan, events, digest, delivery | allow-listed kinds and payload fields; UI inbox | **D6**, plus counsel on wording (D4) |
| Score explanations, momentum, grade, projections, revenue | present, internal | nothing: stay internal | blocked by policy (D4) |

## 3. Phase 2A: creators, offline, no persistence

### 3.1 Provider (ViralTrack package)

- Extend `mapping.map_channel` to keep three more raw values when present: `country` (text), `created_at` (UTC), `total_views` (raw metric, the name already used for history). Each is `null` when absent. `subscribersHidden` stays "followers is null".
- New method `get_creator_videos(creator_id, period, limit)` on the YouTube provider, calling `/api/channels/{id}/velocity`. It maps only `videoId`, `title`, `publishedAt` and `views` into the existing `Content` model (RAW provenance, origin from the settings) and **discards** everything else, including `vphLifetime`, `vph24h`, `viewsGained24h`, `acceleration`, `trend`, `isShort`. Likes, comments, duration and thumbnail are absent, so they are `null`. The capability is declared in `CAPABILITIES` with a note that it is limited. A creator with no collected videos returns an empty list, not an error.
- **Order.** The foundation selects the newest `limit` videos of the period by publication date and then re-orders them by `vph24h`, the withheld 24-hour rate (`channel_velocity` in `application/channel_tracking.py`). ViralTrack therefore discards the upstream order and sorts by `published_at`, newest first, itself; the page says it shows "the newest N videos in the period", and `limit` (the foundation's, bounded by ViralTrack) is the window. There is no offset upstream, so paging is a slice of that window, as in D5.
- The foundation `note` and any text that names a restricted metric is not passed on (the existing hint filter).

### 3.2 API (`/api/v1`, still read-only, localhost only)

| Endpoint | Change |
|---|---|
| `GET /creators/{id}` | adds `country`, `created_at`, `total_views` (provenance-carrying, nullable) |
| `GET /creators/{id}/videos` | new; `period` (`all` or `Nd`), `page`, `page_size`; envelope and notes as the other lists; `meta.sort` is `published_at`, applied by ViralTrack because the upstream order is by a withheld rate |
| `GET /creators` | unchanged contract; the UI adds filters it already supports |

The response guard and the schema `extra=forbid` apply unchanged; the OpenAPI snapshot and the frontend types are regenerated.

### 3.3 Frontend

- **Creators** (`/creators`): grid of creator cards (name, handle, followers or "hidden", videos in result), filters period, creator size and region, pagination, DEMO label, states as on Discover. Header text states that the list comes from the discovered videos, not from a creator index.
- **Creator detail** (`/creators/$id`): identity block (name, handle, country, created, followers, uploads, total views, each a `MetricValue` with RAW tag and source), a videos grid (the existing card, with "likes and duration not reported" shown as missing), link to the platform channel, and a "history, tracking and alerts arrive in a later phase" note instead of fake empty tabs.
- Navigation: add **Creators** to the sidebar; nothing else.
- No chart, no growth figure, no ranking, no score.

### 3.4 Freshness and provenance

Each value shows the retrieval time and, where the source reports none, the line already used on Discover ("the time each value was read from the platform is not reported by the source"). A creator whose video list is empty says so and why it may be empty (not collected yet).

## 4. Later parts (blocked by D6 and decisions)

### 4.1 History (2B, needs D6)

`GET /creators/{id}/history` over the existing `get_creator_history`. Points keep their own time `t` as `collected_at`; irregular spacing is shown as irregular (no interpolation, no gap fill, no zero fill). A chart (Recharts, lazy-loaded) of followers, uploads or total views over at most 30 days (stats retention without the amendment), with each point's time in the tooltip. Fewer than two points shows an explanation (the foundation's own hint says the worker writes snapshots). Hidden followers produce gaps, not zeros. A zero count on a channel that has other data is annotated (finding 3 in the audit).

### 4.2 Growth (2B)

"Change in followers between two stored snapshots" only, shown with both snapshot times and the elapsed time, and never labelled "growth rate", "momentum" or "trend". It is simple subtraction of two raw values, and it needs the owner's classification of "growth" (the metric policy has no entry for it).

### 4.3 Watchlist (2C)

Read-only mirror first: `GET /watchlist` over the foundation's tracked channels (free read). Add and remove go through the foundation's own routes only after an authentication boundary exists (reverse proxy with OpenID Connect) and a quota guard modelled on the D7 guard: `POST /channels/track` may spend 1 unit. No ViralTrack-owned watchlist table.

### 4.4 Alerts (2D)

An allow-list of event kinds (candidates: `title_change`, `silence_break`, `channel_gone`, `video_gone`) and of payload fields; `outlier`, `acceleration` and `topic_match` stay out. Delivery by Telegram or webhook sends content to third parties and is out of scope until the owner decides. UI: an inbox of allowed events, read-only, with "seen" state kept by the foundation.

## 5. Metric restrictions (unchanged)

No outlier, viral, views-per-subscriber, RPM, projection, momentum, grade, YPP, milestone or revenue value appears anywhere. Sorting stays `views` and `published_at` on lists; relevance only for topic search. 24-hour velocity stays withheld. Instagram and TikTok stay unavailable.

## 6. Retention and storage

2A persists nothing. 2B reads rows the foundation already stores and the retention job already purges (`channel_stats_history`: 30 days; `video_stats_history`: 30 days). 2C reads `tracked_channels` (KEEP, the user's own choice; contains channel ids). 2D reads `events` (30 days; payloads hold titles and counts). ViralTrack adds no table, so `viraltrack/retention/policy.py` needs no change; if a future step adds one, the `data-retention` checklist comes first. Report-only retention remains the default.

## 7. Tests and acceptance criteria

### 2A

- Provider: raw-only mapping of the velocity payload (restricted keys never survive, checked by a field-by-field enumeration of the upstream fixture); the result is ordered by `published_at` whatever order the foundation returned (a fixture ordered by `vph24h` proves it); `null` for missing values; empty list; malformed items fail the whole response (the D3 rule); a creator id that is unsafe is refused before any request.
- API: contract tests for the new fields and endpoint; guard tests with restricted keys in nested objects; 404 and 502 mapping; pagination; the OpenAPI snapshot and generated types match.
- Real foundation on PostgreSQL (the existing runner): the endpoint on a seeded corpus, zero network attempts.
- Frontend: the Creators and Creator detail pages in every state, hidden followers, missing values, no derived value displayed, keyboard and axe checks, light and dark.
- Regression: the full Python and web suites, hosted CI green, submodule unchanged, quota zero.

### Acceptance

Only allowed raw fields reach any response or screen; nothing is shown as 0 that was not reported; provenance and DEMO labels present; no new dependency; no persistence; no ranking or performance wording; hosted CI green.
