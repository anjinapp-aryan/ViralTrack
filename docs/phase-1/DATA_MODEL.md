# Data Model

Code: `viraltrack/domain/models.py`. It is platform-neutral: no field or type names YouTube.

```text
Content
 ├── identity      platform, content_id, url, content_type (video | short | unknown)
 ├── creator       Creator(platform, creator_id, name, handle, url, followers*, content_count*)
 ├── metadata      title, thumbnail_url, duration_seconds, language, region, category, hashtags
 ├── publication   published_at
 ├── metrics       tuple[Metric]  -- RAW only (views, likes, comments)
 ├── derived       tuple[Metric]  -- DERIVED only, ALLOWED by policy (views_per_hour_24h, engagement_rate, ...)
 └── provenance    provider, retrieved_at, plus a Provenance on every Metric

Metric      name, value, provenance
Content.origin  REAL_PROVIDER_DATA | DEMO | TEST  (Phase 1.1; must match every metric's origin)

Provenance  provider  (ViralTrack provider id, "youtube")
            adapter   (which adapter produced it, "youtube/niche-finder-http")
            origin    REAL_PROVIDER_DATA | DEMO | TEST
            exposure  ALLOWED | RESTRICTED | INTERNAL_ONLY; Content accepts only ALLOWED
            source    ("youtube-data-api" = raw platform data, "niche-finder" = computed by the foundation)
            collected_at  (when the provider read the value; None = unknown, never guessed)
            kind      RAW | DERIVED
            note      (for derived values: "Calculated by niche-finder from YouTube data; not a YouTube metric")
```

`*` followers and content_count are `Metric`s too, so they carry provenance.

## Raw and derived cannot be mixed

`Content.__post_init__` rejects a DERIVED metric in `metrics` and a RAW metric in `derived`
(tests: `tests/test_domain.py`). That makes YouTube's rule enforceable in code: "You must distinguish these
metrics from metrics sourced from API Data" (derived-metrics policy).

## YouTube mapping (from niche-finder JSON)

| ViralTrack | niche-finder field | Kind |
|---|---|---|
| content_id / url | videoId / url | identifier |
| content_type | isShort (duration ≤ 180 s heuristic) | `SHORT` only with the amendment approval (rule `short_form_label`), otherwise `VIDEO` |
| title, thumbnail_url, category, duration_seconds, published_at | title, thumbnail, category, lengthSeconds, publishedAt | raw metadata |
| language | language | detected by niche-finder (langdetect or `defaultLanguage`), so treat as approximate |
| metrics: views, likes, comments | views, likes, comments | RAW |
| creator.followers, creator.content_count | channelSubscribers, channelVideoCount | RAW |
| derived (ALLOWED): engagement_rate (omitted when likes are hidden), views_per_hour_lifetime, views_per_hour_24h, views_gained_24h | engagementRate, vphLifetime, vph24h, viewsGained24h | DERIVED, passed through |
| derived (RESTRICTED, only with approval): acceleration, views_per_follower, outlier_score, outlier_score_age_adjusted, outlier_score_nexlev, viral_score, projected_30d_views, estimated_rpm | acceleration, viewsPerSubscriber, outlierScore, … | DERIVED; see DERIVED_METRIC_POLICY.md |

The raw/derived split follows niche-finder's own `/api/scores`, which labels every number `source: youtube` or
`source: niche-finder`.

## Known gaps

| Gap | Effect | Plan |
|---|---|---|
| niche-finder's list endpoints do not return each item's last-fetch time | `collected_at` is `None` for video metrics (honestly unknown). History snapshots do carry their time. | Phase 2: propose an `updatedAt` field upstream (small PR) |
| No single-video read endpoint upstream | `GET_CONTENT` is declared unsupported | Same upstream PR |
| Hashtags not exposed by upstream read API | `HASHTAGS` unsupported for YouTube | Revisit if needed |
| Region | `region` left empty; upstream `regionCode` means "viewable in", not "popular in" | Documented, not mapped |
