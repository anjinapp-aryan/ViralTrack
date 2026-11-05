# YouTube discovery audit (Task A and B)

Date: 2026-11-05. Repository head `5ed12ec`, upstream `d872014` (unchanged). Audit only: no code run against YouTube, no
quota spent, no application code changed.

Labels: **VERIFIED FACT** (read in source or recorded in evidence), **INFERENCE**, **PROPOSAL**, **UNKNOWN**, **BLOCKED**.
Upstream paths are relative to `upstream/youtube-niche-finder/backend/`.

## 1. Root cause of the zero-result discovery

**VERIFIED FACT: the zero came from two upstream default thresholds that ViralTrack silently re-activated, applied to a
sample that was almost entirely outside the requested window and on large channels.**

Evidence chain:

1. ViralTrack sent `GET /api/viral?period=30d&sort_by=vph...` with `max_subscribers` and `min_views` **omitted**:
   `DiscoveryQuery.max_creator_followers` and `min_views` default to `None` (`viraltrack/providers/base.py:26-37`), and
   `FoundationClient.get` drops every `None` parameter (`viraltrack/providers/youtube/client.py:60`).
2. An omitted parameter is not "no filter". The HTTP route declares `max_subscribers: int = 10000, min_views: int = 10000,
   min_views_per_subscriber: float = 1.0` (`interfaces/http/api.py:658-663`). So the foundation applied **subscribers <=
   10,000 and views >= 10,000**. (ViralTrack separately sends `min_views_per_subscriber=0`, `viraltrack/providers/youtube/provider.py:160-172`,
   which does disable that third default because `0` is falsy at `application/discovery.py:321`.)
3. The foundation's own funnel for that call, recorded during Batch 5, was:
   `videos in window: 3` -> `channel subs <= 10,000: 0` -> `video views >= 10,000: 0`, hint
   "channel subs <= 10,000 removed all 3 videos".
4. Only 3 of the 70 stored videos were published in the last 30 days (`period_by` defaults to `published`,
   `application/discovery.py:97-134`). The keyword half of the sample (50 videos) was collected with
   `order="viewCount"` and **no `publishedAfter`** because ViralTrack's `collect_query` sends only
   `query, pages, region, language` (`viraltrack/providers/youtube/provider.py:215-226`) and the foundation's
   `collect_niche` defaults to `order="viewCount"`, `period=None` (`application/collecting.py:170-174`;
   `search_videos` default at `infrastructure/youtube/client.py:279-296`). That returns the **all-time most viewed**
   videos for the keyword, which are old and from large channels. The 2016-2026 `published_at` range in the evidence
   (`docs/phase-2/evidence/batch5_evidence.json`) matches.

Classification of the possible causes you listed:

| | Cause | Verdict |
|---|---|---|
| A | Insufficient collected data | **Contributing.** 70 videos, 3 in window. Data volume was a deliberate quota-limited sample |
| B | Subscriber threshold | **Primary.** Default 10,000 re-activated by omitted parameter; zero survivors |
| C | Minimum video threshold | Not applicable. `max_channel_video_count` is not exposed by the HTTP route and was not sent |
| D | Video-age threshold | **Contributing.** 30-day window on publish date; sample was mostly older (keyword order and no `publishedAfter`) |
| E | Metric availability | **Not the cause.** `vph24h` was `None` (one snapshot per video) but no approved metric is used as a filter |
| F | Ranking/filter interaction | Not the cause. Filtering runs before sorting (`application/discovery.py:306-332`) |
| G | Incorrect adapter mapping | **Not the cause for mapping**, but the **parameter semantics** are wrong: None is treated as "no filter" by ViralTrack and as "use default" upstream. This is the adapter defect |
| H | Pagination | Not the cause. There is no pagination; only `limit` (`results[:limit]`, `application/discovery.py:350`) |
| I | Upstream limitation | **Contributing.** `max_subscribers=0` does **not** disable the filter (see 3.1); the hint text says "0 / None" |
| J | Other | `collected_at` unknown is unrelated to filtering |

**UNKNOWN (not preserved):** the funnel for the `period=all` call (it also returned 0 results); the subscriber counts of
all 19 channels (two were observed at 154,000 and 207,000 in transient output that was deleted with the database).
Do not treat the 3 -> 0 -> 0 funnel as the full picture of the 70-video corpus.

**Side effect found:** my own Phase 2 `DISCOVERY_TEST_PLAN.md` case D1 uses `max_creator_followers=0`. That would
**remove** every channel with at least one subscriber, not disable the filter. The plan needs correcting before any run
(see the roadmap, D1).

## 2. The actual discovery pipeline

```text
ViralTrack  DiscoveryQuery  (period, limit, short_form, region, niche, max_creator_followers, min_views, sort)
   -> YouTubeProvider.discover_content      provider.py:160   builds params, MetricPolicy check on sort (provider.py:140)
   -> FoundationClient.get                  client.py:60      DROPS None values   <== defect
   -> GET /api/viral                        api.py:658        route defaults: max_subscribers=10000, min_views=10000,
   |                                                          min_views_per_subscriber=1.0, exclude_shorts=True, limit=24
   -> trends.viral_videos_small_channels    discovery.py:270
        load_window(period, period_by, niche, languages, region, category_id, exclude/only_shorts)   discovery.py:97
           SQL: videos JOIN channels [JOIN video_niches] + window on published_at; language filter in Python
           _enrich: computes every metric (restricted ones too)                                      discovery.py:195
        then in Python, with a funnel counter:
           max_subscribers -> max_channel_video_count -> min_views -> min_views_per_subscriber -> min_outlier_score
        sort by SORTS[sort_by] (default "viral" = restricted)                                        discovery.py:255,331
        results[:limit]
   <- ViralTrack mapping.map_video: allow-list of fields, raw vs derived, MetricPolicy drops restricted
```

VERIFIED FACT: discovery reads only the local database; it spends no quota (`application/discovery.py` module
docstring). Everything it ranks must first be collected by a spending call.

Keyword search (`GET /api/search`, `application/search.py:27`) is a different path: `max_subscribers` default `None`,
`period` default `all`, `min_outlier_score` default 0. With a `query` it ranks by **semantic similarity** to the query
text (`semanticScore`, `search.py:76-93`), ignoring `sort_by`. It worked in Batch 5 (30 items) because it has no
default thresholds.

## 3. Filter-by-filter analysis

"Layer": U = upstream, V = ViralTrack. "Can empty the list" is for discovery (`/api/viral`) unless noted.

| # | Filter | Source | Default | Configurable | Layer | Excludes | Documented | Can cause zero? |
|---|---|---|---|---|---|---|---|---|
| 1 | Window by publish date | `discovery.py:97-134`, `periods.window` (`periods.py:56`) | `7d` route; ViralTrack passes caller's `period` | `period`, `period_by` (`published`/`discovered`/`updated`) | U; V passes `period` only | Videos published before the window | Yes (module docstring) | **Yes** (3 of 70 in 30d) |
| 2 | `max_subscribers` | `discovery.py:311`, route `api.py:661` | **10,000** | Yes, but **0 does not disable** (`is not None` test); HTTP cannot send None | U | Channels above the limit; NULL subs are kept | Partly: hint says "0 / None" (`discovery.py:367`), which is wrong for 0 | **Yes (primary)** |
| 3 | `min_views` | `discovery.py:318`, route | **10,000** | Yes; `0` disables (falsy) | U | Videos under the limit | Yes | **Yes** |
| 4 | `min_views_per_subscriber` | `discovery.py:321`, route | 1.0 | Yes; `0` disables | U; **V sends 0** | Videos with VSR below limit | Yes | Yes upstream; neutralised by ViralTrack |
| 5 | `min_outlier_score` | `discovery.py:325` | `None` | Yes | U; not sent by V | Rows below score | Yes | No (off) |
| 6 | `max_channel_video_count` | `discovery.py:314` | `None` | Python arg only; **not an HTTP route parameter** | U | Channels with many videos | n/a | No |
| 7 | Shorts exclusion | `discovery.py:123-128`, route `exclude_shorts=True` | exclude | Yes | U; V sends both flags explicitly (`provider.py:107`) | Videos with `is_short` (duration <= 180 s, `domain/metrics.py:23`) | Yes | Only if all videos are Shorts |
| 8 | Language | `discovery.py:76` | none | Python arg; **not an HTTP route parameter** | U | Unknown language is kept | n/a | No |
| 9 | Region | `discovery.py:51` | none | Yes | U | `v.region` or channel country mismatch | Yes | Yes if set and data lacks region |
| 10 | Category | `discovery.py:55` | none | Yes (`category_id`) | U; V does not expose | Other categories | Yes | Yes if set |
| 11 | Niche | `discovery.py:48` | none | Yes | U; V passes `niche` | Videos not collected under that niche | Yes | Yes if set and niche empty |
| 12 | Limit | `discovery.py:350` | route 24; V passes caller's | Yes | U | Beyond N | Yes | No |
| 13 | Data freshness | none | none | n/a | none | **Nothing**: stale view counts are used as stored | **No** | No, but misleading |
| 14 | Metric availability | `_enrich` | n/a | n/a | U | `vph24h`, `viewsGained24h` are `None` without 2+ snapshots (`domain/metrics.py:314-334`); none of them filters | Yes (module docstring) | No |
| 15 | Duration filters | `search.py:60-63` only (`min_video_length`) | none | `/api/search` only | U | | Yes | No |

Hidden behaviours worth knowing:

- **VERIFIED FACT: `views_per_subscriber` divides by `max(subs,1)`** (`domain/metrics.py:259`), so a channel with hidden or
  missing subscribers gets an enormous value. Restricted metric, so unused by ViralTrack, but any upstream filter on it
  would be dominated by hidden-subscriber channels.
- **VERIFIED FACT: `engagement_rate` treats hidden likes as 0 when comments exist** (`domain/metrics.py:265-271`).
  ViralTrack's `REQUIRES_RAW` guard omits it when likes are hidden (`mapping.py`).
- **VERIFIED FACT: `vph_lifetime = views / max(age_hours, 1)`** (`domain/metrics.py:292`): a video under an hour old is
  treated as one hour old; and it uses the *stored* view count, however old that snapshot is.
- **VERIFIED FACT: the 24-hour velocity uses "the latest snapshot at least 24 h before the newest, else the oldest
  one"** (`domain/metrics.py:314-334`), so `views_per_hour_24h` can span far more or less than 24 hours. ViralTrack's
  policy already records this caveat.
- **VERIFIED FACT: snapshots are appended only by `refresh_stats`, the worker's hot/full refresh, and collection**
  (`infrastructure/postgres/repositories.py:85-110`, `application/collecting.py:470`). Without the worker or a refresh
  there is one snapshot per video, so no velocity metric exists.
- **VERIFIED FACT: no pagination.** `results[:limit]`; `matched` is the pre-limit count.

## 4. Discovery funnel (actual evidence only)

Batch 5 corpus, `period=30d` call (recorded in the Batch 5 session output; the database is dropped):

| Stage | Count | Status |
|---|---|---|
| Collected videos (channel 20 + keyword 50) | 70 | VERIFIED (`batch5_evidence.json`) |
| Collected channels | 19 | VERIFIED |
| Valid YouTube records (id format check) | 70 | VERIFIED (ViralTrack maps only valid ids; no error raised) |
| Fresh records (re-read within 25 days) | 70 | INFERENCE: all collected minutes earlier; no freshness filter exists |
| Videos in the 30-day window | **3** | VERIFIED |
| Channel subscribers <= 10,000 | **0** | VERIFIED |
| Views >= 10,000 | 0 | VERIFIED (nothing left) |
| Views per subscriber >= 0 (disabled by ViralTrack) | 0 | VERIFIED |
| Metric eligibility (approved metrics present) | not reached | UNKNOWN |
| Ranking | not reached | n/a |
| Final results | **0** | VERIFIED |

`period=all` call: final results 0; intermediate counts **UNKNOWN**.
`/api/search` call with `period=all`: 30 items returned (limit 30); total matched **UNKNOWN**.

## 5. Upstream capability audit (Task B)

Classification uses the project rule: REUSE (as is), ADAPT (thin ViralTrack change), COMPOSE (combine existing parts),
BUILD (missing), REJECT. "Policy" is the ViralTrack metric policy (4 allowed / 10 restricted / 2 internal-only).
All entries were verified in source, not only in documentation.

| Capability | Where (verified) | Verdict | Notes |
|---|---|---|---|
| Keyword candidate collection | `collecting.collect_niche` (`:170`), `search_videos` | **ADAPT** | Works. ViralTrack must pass `period` (publishedAfter) and should not rely on `order=viewCount` default; HTTP route does not accept `order`, `category_id`, `video_duration` |
| Channel candidate collection | `collecting.collect_channel` (`:361`) | **REUSE** | 1 unit per 50 videos, uploads playlist |
| Channel discovery by RSS (no quota) | `collecting.discover_new_videos_via_rss` (`:402`) | **REUSE** (worker) | Novelty detection for known channels; no view counts |
| Most-popular chart | `collecting.collect_trending` (`:292`) | **REJECT for general discovery** | Since 2025-07-21 it is the Music/Movies/Gaming chart only (upstream comment `client.py:331-336`) |
| Daily keyword queries | `worker_cycle.py` `WORKER_QUERIES`, `WORKER_QUERY_PERIOD=24h` | **REUSE** | 1 search call each; the right shape for recent-video discovery |
| Eligibility filters (subs, views, window, shorts, niche, region, category) | `discovery._filters`, `viral_videos_small_channels` | **ADAPT** | Correct but defaults are hidden; adapter must send explicit values |
| Search with outlier/semantic filters | `search.search_outliers` | **ADAPT** | Text query ranks by internal semantic score (policy question, section 7) |
| Snapshots and refresh | `refresh_stats` (`:470`, uses `videos:batchGetStats`), worker hot/full refresh | **REUSE** | Needed for any velocity metric; spends quota |
| View velocity (24 h) | `domain/metrics.vph_from_history` | **REUSE** | Approved metric; needs 2+ snapshots; window is variable |
| Lifetime velocity, engagement | `domain/metrics.vph_lifetime`, `engagement_rate` | **REUSE** | Approved; stale-count caveat |
| Outlier score, VSR, viral score, acceleration, projection | `discovery._enrich` | **REJECT for ViralTrack use** | Restricted by policy |
| Niche identification | `video_niches`, `list_niches`, `niches/ranking`, `niches/saturation` | **COMPOSE** (review) | Niche score is a custom composite: check against the "custom scores" rule before exposing |
| Similarity search | `search.similar_videos` (`:423`), `similar_channels` (`:517`), pgvector `embedding_v` | **COMPOSE** (review) | Embeddings are computed locally from YouTube text (fastembed). Is a similarity ranking a "custom score" or a merge with other data? Counsel/owner question |
| Embeddings | `infrastructure/embeddings/fastembed_provider.py` | **REUSE** internally | Model downloaded from Hugging Face on first use; vectors follow the 30-day row |
| Dashboard | upstream frontend | **REJECT for external use** | Internal-only; shows restricted metrics |
| Watchlist, alerts, topics | `tracked_channels`, `alerts`, `topic_watch` | **REUSE** | Tracking foundation for D6; alerts use restricted metrics internally |
| Background worker | `worker_cycle.py` | **REUSE** | The scheduler; do not build another |
| Quota system | `yt._get` reservation, `search_calls_today`, `unit_quota` in `/api/health` | **REUSE** | ViralTrack already reads it (pre-flight) |

## 6. Findings for the owner

| ID | Finding | Severity |
|---|---|---|
| F-1 | Adapter treats None as "no filter" but upstream treats absent as "default threshold". Discovery silently applies 10,000 subscribers and 10,000 views | High (this is the zero-result bug) |
| F-2 | `max_subscribers=0` does not disable the filter; only an explicit large value does over HTTP. Upstream hint says otherwise | Medium (upstream; document, work around in adapter) |
| F-3 | `collect_query` sends no `period`, so the foundation collects all-time most-viewed videos | High for discovery quality |
| F-4 | Phase 2 discovery test plan case D1 is wrong (`max_creator_followers=0`) | Medium (doc fix) |
| F-5 | Text search orders by `semanticScore`, an INTERNAL_ONLY metric, ignoring `sort` | Policy question |
| F-6 | `short_form` filter uses the Shorts duration inference, which is a restricted *label* | Policy question |
| F-7 | No freshness information reaches ViralTrack (`collected_at` unknown), yet stale view counts feed `views_per_hour_lifetime` | Medium |
| F-8 | The metric policy's own source document lists "custom scores" and "ranking views between different channels" as prohibited without the amendment; a composite ranking score would hit this | Blocker for composite scoring (see Task E) |

## 7. Commands used (read-only)

Source reading of the files cited above; `gh api repos/...` for licence and activity; no requests to YouTube, no code
run against the foundation.
