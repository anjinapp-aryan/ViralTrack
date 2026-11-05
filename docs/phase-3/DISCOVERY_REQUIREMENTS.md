# Discovery product requirements, metric and ranking policy, filter design (Tasks D, E, F)

Date: 2026-11-05. Proposals, not approved requirements. Evidence is in
[YOUTUBE_DISCOVERY_AUDIT.md](YOUTUBE_DISCOVERY_AUDIT.md). Labels: VERIFIED FACT, INFERENCE, PROPOSAL, UNKNOWN, BLOCKED.

## 1. Metric policy (verified in the repository)

VERIFIED FACT, `viraltrack/providers/youtube/metric_policy.py` (`RULES`), checked on 2026-11-05:

| Class | Metrics |
|---|---|
| ALLOWED (4) | `engagement_rate`, `views_per_hour_lifetime`, `views_per_hour_24h`, `views_gained_24h` |
| RESTRICTED (10) | `acceleration`, `views_per_follower`, `outlier_score`, `outlier_score_age_adjusted`, `outlier_score_nexlev`, `outlier_band`, `viral_score`, `projected_30d_views`, `estimated_rpm`, `short_form_label` |
| INTERNAL_ONLY (2) | `baseline_median_views`, `semantic_score` |

Raw values that may be shown, sorted by and filtered on: `views`, `likes`, `comments`, channel `subscribers` and video
count, `published_at`, duration, category id returned by the API, language.

Caveats of the four approved metrics (VERIFIED, `domain/metrics.py`):

| Metric | Caveat |
|---|---|
| `engagement_rate` | `(likes + comments) / views`. Omitted by ViralTrack when likes are hidden (the foundation would count hidden likes as 0). Unstable for small view counts |
| `views_per_hour_lifetime` | `views / max(age_hours, 1)` using the **stored** view count; stale if not refreshed; biased to very new videos |
| `views_per_hour_24h` | From snapshots; needs 2+ snapshots; the window is "newest snapshot vs the latest one at least 24 h older, else the oldest", so it can span far more or less than 24 h |
| `views_gained_24h` | `vph24h x 24`, an extrapolation and not a measured delta |

**Is the approved set enough for useful discovery? INFERENCE: yes for a first useful version, with limits.** Recent
videos from small channels sorted by lifetime velocity, plus an engagement filter, answers "what is moving now". It
cannot normalise against a channel's own history (that needs the restricted outlier metrics), so it cannot say
"outperforming its channel". Without the worker it has no growth information at all.

## 2. Hard rules for filtering, sorting, ranking, export

1. A restricted or internal-only metric must not influence discovery, filtering, ranking, sorting, exports or any API.
   This includes **upstream defaults**: the adapter must keep sending `min_views_per_subscriber=0` and must never rely on
   an upstream default sort (`viral`, `outlier`).
2. A missing value stays missing (`None`), never imputed, never zero. Hidden likes give no engagement rate.
3. A velocity metric from fewer than two snapshots is "no data", not a trend. Present `views_per_hour_24h` with its
   actual window length.
4. Every shown ranking factor carries provenance (existing `Provenance`: raw/derived, source, `collected_at` unknown,
   `foundation_first_seen_at`, `Content.retrieved_at`).
5. **BLOCKED:** a *composite* numeric ranking score. The policy source (`docs/phase-1/DERIVED_METRIC_POLICY.md`, quoting
   Google's compliance guide) lists "calculate and assign custom scores ... based on ratios" and "gamify channel
   performance by ranking ... between different channels" as prohibited without the Analytics & Reporting amendment,
   which is not filed. A weighted blend of the four metrics is a custom score.
6. Open compliance questions for the owner or counsel (not decided here): does a *single-metric ordering of videos*
   (for example by `views_per_hour_lifetime`) count as ranking? Does ordering text-search results by semantic
   similarity? Does the Shorts duration filter count as inferring a content type? Does an embedding-based "similar
   videos" list merge YouTube data with other data?

## 3. Proposed explainable ranking (PROPOSAL)

Separate five things; do not collapse them into one number:

| Layer | Meaning | Proposal |
|---|---|---|
| Eligibility | May the video be a candidate at all | Pass/fail rules on raw values: published within the window, valid id, views >= floor, channel subscribers within the chosen band (or unknown), not excluded by language/duration choice. Each failure is counted by reason |
| Order | How candidates are ordered | **One approved metric chosen by the caller** (`views_per_hour_lifetime`, `views_per_hour_24h`, `views_gained_24h`, `engagement_rate`, `views`, `published_at`), with fixed documented tie-breaks (`views` descending, then `video_id`). No blended score |
| Confidence | How far to trust the order | A label from facts, not a probability: `ok`, `no_history` (fewer than 2 snapshots), `stale` (last refresh older than N hours, when known), `low_sample` (views below a floor for engagement), `hidden_likes` |
| Freshness | How old the numbers are | Show `foundation_first_seen_at` and the newest snapshot time (needs the history endpoint). `collected_at` stays unknown unless the foundation exposes it |
| Evidence | Why it is listed | The list of filters it passed and the metric values with provenance and the formula text already in `MetricRule.basis` |

Assumptions to validate before any threshold is fixed (UNKNOWN until measured on real data): the stale threshold;
the minimum views for a meaningful engagement rate; how often `views_per_hour_lifetime` favours very new low-view
videos. No numeric formula is proposed here.

## 4. Discovery dimensions

Status key: SN supported now, SA supported with adaptation, NS not currently supported, BP blocked by policy or data
source. "Upstream" names the verified capability. Quota: search.list is 1 call from its own 100/day bucket; the other
calls are 1 unit from the 10,000/day pool (Google quota page, read 2026-11-04 through a fetch agent; the foundation's
own counters agree). The estimates are for the smallest sensible sample.

| # | Dimension | Status | User objective | Candidate source | Required data | Missing capability | Quota | Eligibility | Ordering | Compliance | Acceptance criteria |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Keyword | **SA** | Find videos for a topic | `collect_niche` (search.list) | views, published_at, channel subs | Adapter does not send `period`; upstream order is all-time `viewCount`; no `order`/`category` over HTTP | 1 search call + ~2 units per 50 results | Window, views floor, subs band | `views`, `views_per_hour_lifetime` | Official API only | With `period` set, >= 90% of collected videos fall inside the window; funnel shows counts per filter |
| 2 | Niche | **SA** | Browse a labelled collection | `video_niches` from keyword collections | niche label | Niche **score** (`/api/niches/ranking`) is a custom composite: not exposable | as keyword | Niche membership | as chosen | Niche score BP | Niche filter returns only that collection's videos |
| 3 | Category | **SA** read / **NS** collect | Browse by YouTube category | `category_id` returned by the API | `category_id` | HTTP collect route does not pass `category_id`; only API-returned category may be used (no inference) | read: 0 | Category id equality | as chosen | No inferred categories | Filter by API category id returns only those |
| 4 | Channel | **SN** | Study a known channel | `collect_channel` (uploads playlist) | uploads, subs | none | ~3 units per 20 videos (Batch 5: 3) | Subs band | as chosen | none | 20-video collection costs <= 5 units |
| 5 | Recently published | **SA** | What came out lately | keyword with `period`, or `WORKER_QUERIES` daily (`WORKER_QUERY_PERIOD=24h`) | published_at | adapter `period` | as keyword | Window | `published_at`, velocity | none | Items all newer than the window |
| 6 | Fast-growing | **SA** | What is gaining views now | snapshots from `refresh_stats` / worker hot refresh | 2+ snapshots | Needs a refresh schedule (quota) and window disclosure | refresh: ~1 unit per 50 videos per pass | >= 2 snapshots | `views_per_hour_24h`, `views_gained_24h` | `acceleration` BP | Only videos with 2+ snapshots get a velocity; others labelled `no_history` |
| 7 | High engagement | **SN** | Audience interacts a lot | any collected video | likes, comments, views | Low-sample handling | 0 | Likes visible, views floor | `engagement_rate` | Hidden likes excluded | No item with hidden likes carries a rate |
| 8 | Emerging creators | **SA** | Small channels with traction | collected channels | subs, channel age (`channels.published_at`), video count | Channel age not in the `Creator` model; foundation's outlier-channel list uses restricted multipliers (BP) | 0 | Subs band, channel age | video metrics above | "Emerging" **label** is a classification: avoid; show filter facts instead | Result states the filter, not an "emerging" score |
| 9 | Similar content | **NS** in ViralTrack | More like this | upstream `similar_videos` (pgvector) | embeddings | Not exposed by adapter; policy review (section 2.6) | 0 | n/a | similarity (internal-only) | BP pending review | Not scheduled |
| 10 | Breakout candidates | **SA** as a *filter*, **BP** as a score | Surface outliers | rule: window + small channel + velocity above a user threshold | approved metrics | Outlier/viral/acceleration are restricted; any "breakout" tag is a classification | 0 beyond refresh | User thresholds | velocity | No composite | Output says "meets: ..." and lists the rules |

## 5. Filter design (Task F)

Rules: filters are explicit and visible; every filter has a default that is *stated in the response*; an unset filter is
sent upstream as an explicit non-restrictive value, never omitted (this is the audit's root cause); no restricted metric
is ever a filter; upstream defaults are not silently relaxed, they are overridden openly and recorded.

| Filter | YouTube supplies it | Collected by foundation | Approved | Extra quota | Can wrongly exclude emerging videos | Optional or mandatory |
|---|---|---|---|---|---|---|
| Niche or keyword | Yes (search query) | Yes | Raw | Collection only | Yes: search ranks by relevance/views, not novelty | Optional |
| Publication period | Yes | Yes | Raw | Selects `publishedAfter` at collection | Yes if too narrow | **Mandatory** (explicit) |
| Minimum views | Yes | Yes | Raw | No | **Yes**: a 10,000 default hid every candidate | Optional, default 0 |
| Maximum views | Yes | Yes | Raw | No | Possible | Optional |
| Minimum engagement rate | Likes and comments | Yes | Approved metric | No | Yes for hidden likes (excluded, counted separately) | Optional |
| Minimum views per hour (lifetime) | Derived | Yes | Approved | No | Biased to new videos | Optional |
| Minimum views per hour (24 h) | Needs snapshots | Needs worker | Approved | Refresh quota | Excludes videos without history | Optional |
| Language | `defaultLanguage` (often missing) | Yes | Raw | No | Unknown language is kept upstream | Optional; HTTP route does not expose it for `/api/viral` |
| Category | API `categoryId` | Yes | Raw | No | Mis-set creator categories | Optional |
| Video duration | API duration | Yes | Raw | No | Shorts rule is a restricted label (F-6) | Optional; upstream exposes it on `/api/search` only |
| Channel size (subscribers) | Yes, may be hidden | Yes | Raw | No | **Yes**: the 10,000 default hid every candidate; hidden subs are kept upstream | Optional; default none |
| Maximum candidates | n/a | n/a | n/a | Collection cap controls quota | Yes if too small | Mandatory (cap) |

## 6. Not supported now (state plainly)

Instagram and TikTok discovery; trending audio; transcripts; thumbnail analysis; any restricted metric or score; a
composite ranking; channel ranking; forecasting or projections; "similar content" until the policy question is
answered; category-targeted collection over HTTP.
