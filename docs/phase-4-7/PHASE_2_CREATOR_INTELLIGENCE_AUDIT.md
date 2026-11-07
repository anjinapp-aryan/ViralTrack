# Phase 2 (creator intelligence): audit of what exists

Date: 2026-11-07. Read-only. Evidence: the pinned foundation source at `d872014`, its documented API (`upstream/youtube-niche-finder/docs/http-api.md`), live reads against the local demo foundation (no API key, 0 quota units used), and the ViralTrack code at `c3adf7e`. Nothing was changed, and nothing here spends quota. Related, not repeated: [MASTER_ROADMAP.md](MASTER_ROADMAP.md) (D6), [D5_DASHBOARD_RECONNAISSANCE.md](D5_DASHBOARD_RECONNAISSANCE.md), [../phase-1/DERIVED_METRIC_POLICY.md](../phase-1/DERIVED_METRIC_POLICY.md), [../phase-1/DATA_RETENTION_POLICY.md](../phase-1/DATA_RETENTION_POLICY.md).

## 1. Capability inventory

| Capability | In the foundation | In ViralTrack today | Policy status |
|---|---|---|---|
| Creator discovery | No creator index. `/api/outlier-channels` ranks by outlier multiplier (RESTRICTED). `/api/niches/{slug}/videos` and `/api/search` return videos with their channel | `GET /api/v1/creators`: distinct creators among the first 1000 discovered videos (D5) | allowed (raw counts only) |
| Creator profile | `GET /api/channels/{id}`: profile, cadence, performance, growth, momentum, grade, projections, revenue, YPP eligibility, milestones, top outliers | `GET /api/v1/creators/{id}`: identity, followers, upload count (raw, null when hidden). `map_channel` reads only `title`, `handle`, `subscribers`, `subscribersHidden`, `videoCount` | profile fields below are mostly RESTRICTED |
| Creator's videos | `GET /api/channels/{id}/velocity` is the only per-creator video list. `/api/viral` has **no channel filter** (verified from the route signature) | none; the D5 detail says `videos: null` | the list mixes raw fields with restricted ones |
| Historical snapshots | `GET /api/channels/{id}/history`: points `{t, subscribers, videos, views}` from `channel_stats_history` (primary key channel + `captured_at`) | `YouTubeProvider.get_creator_history` maps the points (followers, content_count, total_views); no API endpoint | raw values; retention 30 days |
| Watchlist | `tracked_channels` (single-user or per-user): `GET /api/channels/tracked`, `POST /api/channels/track`, `DELETE /api/channels/tracked/{id}`, plus `POST /api/refresh` and the worker | none | read is free; write may spend quota |
| Alerts | `events` table and scan: kinds outlier, acceleration, title_change, silence_break, channel_gone, video_gone, topic_match; digest; Telegram and webhook delivery | none | most kinds depend on restricted values |
| Creator analytics | growth windows, cadence, medians, momentum, grade, projections, revenue, YPP, milestones, collab candidates, sponsors, template risk | none | restricted or unclassified |
| Score explanations | `GET /api/scores` documents every number (formula, inputs, minimum sample) | none; D4 blocked | contains restricted scores |

## 2. Evidence from the live demo foundation

`GET /api/channels/{id}` returns these groups (keys only; values are synthetic demo data):

- `profile`: title, handle, country, subscribers, subscribersHidden, totalViews, videoCount, createdAt, ageDays, topics, keywords, mainCategory, aiLabels.
- `cadence`: uploadsPerWeekLifetime, uploadsInPeriod, avgVideoLengthSeconds, daysSinceLastUpload, longformCount, shortsCount, shortsSharePercent.
- `performance`: medianViewsPerVideo, avgViewsPerVideo, viralSkew, medianEngagementRate, medianViewsPerSubscriber, bestVideo, shortsMedianViews, longformMedianViews.
- `growth`: windows 24h, 7d, 30d, 90d.
- Also `momentum`, `grade` (A+), `projections` (subscribers 1y/3y, views 1y), `revenue` (including a Social Blade range), `yppEligibility`, `milestones.forecasts`, `topOutliers`, `gone`, `snapshots`, `caveats`.

`GET /api/channels/{id}/history` points carry `t`, `subscribers`, `videos`, `views`. `GET /api/channels/{id}/velocity` videos carry `videoId`, `title`, `publishedAt`, `ageHours`, `views`, `isShort` **and** `vphLifetime`, `vph24h`, `viewsGained24h`, `acceleration`, `trend`. `GET /api/events` events carry `kind`, `refId`, `payload`, `createdAt`, `seenAt`.

## 3. Classification against the existing metric policy

| Foundation value | Class | Reason |
|---|---|---|
| profile: title, handle, country, subscribers, totalViews, videoCount, createdAt | **ALLOWED, raw** | platform-reported counts and metadata (`subscribers` is `null` when hidden) |
| profile: topics, keywords, mainCategory | raw metadata, not mapped yet | platform text; needs a retention note (text window, 30 days) |
| profile: aiLabels | **excluded** | produced by an LLM; LLM is off by default |
| history points (subscribers, videos, views) | **ALLOWED, raw** | simple stored counters; observation time question below |
| velocity: videoId, title, publishedAt, views | **ALLOWED, raw** | |
| velocity: vphLifetime | allowed, display only (never a sort) | existing D3 rule |
| velocity: vph24h, viewsGained24h | **withheld** | no reliable snapshot recency (D3-05) |
| velocity: acceleration, trend | **RESTRICTED** | |
| velocity: isShort | **RESTRICTED** | the platform returns no Shorts flag (the duration filter is ViralTrack's own rule) |
| cadence (uploads per week, days since last upload, averages) | **unclassified** | simple arithmetic on raw data, but not in the policy table; needs an owner decision |
| growth windows (24h to 90d) | **unclassified, depends on timestamps** | subtraction of two raw snapshots; correct only if snapshot times are reliable |
| medianEngagementRate, medianViewsPerSubscriber, viralSkew, bestVideo | **RESTRICTED or unclassified** | views per subscriber is RESTRICTED; skew is a custom statistic |
| momentum, grade, projections, revenue, yppEligibility, milestones | **RESTRICTED** | custom scores, projections and financial estimates (third-party data for revenue) |
| topOutliers | **RESTRICTED** | outlier scores |
| events: outlier, acceleration | **RESTRICTED** | built from restricted scores; payloads contain the scores |
| events: topic_match | **INTERNAL_ONLY** | embedding similarity |
| events: title_change, silence_break, channel_gone, video_gone | plausibly raw-based | need an allow-list review of their payloads |

## 4. Findings that shape the design

1. **There is no way to list a creator's videos through the existing discovery route.** The only source is `/api/channels/{id}/velocity`, which mixes raw and restricted fields; ViralTrack would map the four raw fields and discard the rest. It returns no likes, comments, duration or thumbnail. **Its order is by a withheld value:** the query takes the newest `limit` videos by `published_at`, then the code re-sorts them by `vph24h` (the 24-hour rate withheld by D3-05), so the upstream order must not be used. ViralTrack would order by `published_at` itself.
2. **History timestamps are plausibly observation times.** `record_channel_stats` stores `captured_at = now_iso()` at the moment it records the counters read from the API, so a point's time is when the foundation read the value. ViralTrack already maps it as `collected_at`. It must still be confirmed on real data (D7), because the demo corpus is seeded. Points are irregular (they exist only when a refresh ran), and `/history` returns the newest 400 points.
3. **Hidden subscribers are `null`, but upstream can turn a missing video or view count into 0.** In `collecting.py`, `video_count` and `view_count` use `int(stt.get("videoCount", 0) or 0)`. A channel whose response omits them is stored as 0, which would be shown as a real zero. This needs a D7 check against real responses and a UI rule (a zero count on a channel with other data is displayed with a "may be unreported" note), not a code change in the submodule.
4. **Retention bounds history.** `channel_stats_history` is PURGE at the 30-day stats window (`viraltrack/retention/policy.py`), so a chart cannot exceed 30 days until the Analytics and Reporting amendment is accepted (then 36 months for statistics). Alert `events` are 30 days. `tracked_channels` are KEEP (the user's own choice).
5. **Watchlist writes can cost quota.** `POST /api/channels/track` spends 1 unit to resolve an unseen handle or URL; `POST /api/refresh` spends units per 50 items. The D5 API is read-only and unauthenticated, localhost only. Exposing watchlist writes needs an authentication boundary and the existing quota guard.
6. **Alerts depend on restricted values.** Of the seven kinds, two are built from restricted scores, one from an internal-only similarity, and four are plausibly raw-based. Delivery (Telegram, webhook) sends content to outside services.
7. **The foundation dashboard already offers all of this internally** (tracker, channel pages, alerts), so ViralTrack should not rebuild any of it. The gap is the policy boundary and a UI over it.

## 5. What already works and must not be rebuilt

Collection and refresh (worker), quota ledger, snapshots, watchlist storage, history series, alert scan and digest, notification delivery, similar creators, profit and revenue models. ViralTrack reuses them through the foundation HTTP API (the same composition as D5) and exposes only the allowed subset.
