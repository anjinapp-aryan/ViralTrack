# Derived Metric Policy

Status: **enforced in code** (`viraltrack/domain/metric_policy.py`, `viraltrack/providers/youtube/metric_policy.py`).
These are engineering classifications, not legal conclusions. Rows marked **review** need a human or legal
decision.

## Why

Without Google's acceptance of the "Analytics & Reporting" amendment (not filed), the YouTube compliance guide
allows only metrics that "use only YouTube API data and combine them via simple mathematical calculations
(addition, subtraction, averages, multiplication, division)" and "must not incorporate any other external data
sources".

Its *Don't* list includes:

- "Infer or project financial performance of a YouTube channel"
- "Calculate and assign custom 'scores' to channels based on independently calculated averages or ratios"
- "Gamify channel performance by ranking or tracking views between different channels"
- "Infer or estimate the content category/type of a video or channel; you may only use the content type
  returned by the YouTube API"
- "Merge or combine YouTube API data with any other data"
- "Estimate the monetization status of a video or channel"
- "Estimate viewer satisfaction or dissatisfaction"

The amendment (derived-metrics policy) would allow custom scores, financial projections labelled as estimates,
content tagging labelled as ours, and leaderboards.

The foundation computing a metric does **not** authorize ViralTrack to show it.

## Mechanism

| Piece | Role |
|---|---|
| `Exposure` | `ALLOWED` (may be shown, labelled "not a YouTube metric") · `RESTRICTED` (shown only once the named approval is held) · `INTERNAL_ONLY` (never user-visible) |
| `MetricPolicy` | One `MetricRule` per derived value. **Unknown names are denied.** A RESTRICTED rule must name its approval. |
| Approvals | `youtube_analytics_amendment`, granted only by `VT_YOUTUBE_ANALYTICS_AMENDMENT_ACCEPTED=true`. Nothing else grants approvals. |
| Mapping (allow-list) | Only listed upstream fields are read. A derived value is copied into `Content.derived` only when `policy.exposable(name)`. |
| `Content` invariant | `Content` raises if any metric (raw, derived or creator) has a provenance exposure other than `ALLOWED`, so no other code path can insert a restricted value |
| Ordering | Sorting by a value discloses it. The adapter always sends an explicit `sort_by` (default: raw `views`); upstream's own defaults (`viral`, `outlier`) rank by restricted scores. Sorting by a non-allowed metric raises `RestrictedMetric` before any request |
| Labels | The `short` content-type label is itself a rule (`short_form_label`). Without approval every YouTube item is `VIDEO`. Filtering by duration (≤ 180 s) remains possible, because it filters raw data |
| Contract test | `test_every_upstream_numeric_field_is_classified` fails when the foundation adds a numeric field that is not explicitly mapped or ignored |

## Classification of every value niche-finder derives for videos

| ViralTrack name | niche-finder field | Basis | Exposure | Review |
|---|---|---|---|---|
| engagement_rate | engagementRate | (likes + comments) / views × 100 | ALLOWED | |
| views_per_hour_lifetime | vphLifetime | views / hours since publication | ALLOWED | |
| views_per_hour_24h | vph24h | view delta between two stored snapshots / hours | ALLOWED | needs snapshots, which are limited to 30 days (retention) |
| views_gained_24h | viewsGained24h | view delta between snapshots | ALLOWED | |
| acceleration | acceleration | ratio of two views-per-hour rates | ALLOWED | **review**: confirm a ratio of rates is not a "custom score" |
| views_per_follower | viewsPerSubscriber | video views / own channel subscribers | ALLOWED | **review**: compares a video with its own channel; confirm it is not channel gamification |
| outlier_score | outlierScore | views / median of the channel's previous 10 uploads, banded into labels | RESTRICTED | |
| outlier_score_age_adjusted | outlierScoreAgeAdjusted | divided by a fitted maturity curve (model) | RESTRICTED | |
| outlier_score_nexlev | outlierScoreNexlev | third-party method | RESTRICTED | |
| outlier_band | outlierBand | label from the outlier score | RESTRICTED (not mapped) | |
| viral_score | viralScore | projected views per subscriber | RESTRICTED | |
| projected_30d_views | projected30dViews | projection | RESTRICTED | |
| estimated_rpm | estimatedRpm / estimatedRpmRange | niche RPM tables from third-party sources | RESTRICTED | **review**: external data. Even with the amendment, only as a clearly labelled third-party estimate |
| short_form_label | isShort | duration ≤ 180 s inference | RESTRICTED | **review**: the guide says to use only the API's content type |
| baseline_median_views | baselineMedianViews(Period) | input to outlier score | INTERNAL_ONLY (not mapped) | |
| semantic_score | semanticScore | embedding similarity for search ordering | INTERNAL_ONLY (not mapped) | |
| — | outlierScoreRolling, outlierScorePeriod, ageHours, ageDays, snapshots | variants or bookkeeping | not mapped | |

Channel-level values (momentum, grade, YPP eligibility, revenue range, projections, niche scores, niche ranking,
policy signals, template risk, AI labels, sentiment, collaboration and sponsor scores) are **not mapped** by the
adapter at all. The adapter's creator mapping reads only raw `subscribers` and `videoCount`.

## What the policy cannot cover (read carefully)

1. **The foundation's own dashboard, HTTP API, MCP server and Chrome extension show every restricted metric.**
   ViralTrack does not modify upstream, so it cannot filter them. Status: **INTERNAL_ONLY**. They are an
   operator and research tool, bound to `127.0.0.1` by the upstream compose file, and **must not be offered to
   end users** until the amendment is accepted. ViralTrack has no production UI yet; a future UI must be
   built on the ViralTrack provider layer, not on the foundation's screens. (This is a change from
   UI_REUSE_DECISION.md, which reused the dashboard. That reuse is now limited to internal use.)
2. Discovery filters: `/api/viral` filters by `views_per_follower` ≥ 1.0 (an ALLOWED metric). Upstream may
   change its defaults. The adapter sends only allowed parameters.
3. Retention: snapshots behind views-per-hour live at most 30 days (DATA_RETENTION_POLICY.md).

## Human / legal review items

- **File the YouTube API Compliance Audit with the Analytics & Reporting amendment.** Until it is accepted,
  RESTRICTED stays restricted.
- Confirm the ALLOWED classification of `acceleration` and `views_per_follower`.
- Decide whether the Shorts label may be shown, with or without the amendment.
- Decide whether RPM or revenue estimates should ever be shown (external data).
