# Metric Inventory and Approval (Phase 1.2)

Source of truth: `viraltrack/providers/youtube/metric_policy.py` (`RULES`) and
`viraltrack/providers/youtube/mapping.py`. Formulas are read from the upstream code at `d872014`
(`backend/domain/metrics.py`, `backend/application/discovery.py`). Classifications are engineering
judgements, not legal conclusions.

## Count reconciliation

**Current (Phase 2 Batch 1, owner decision 2026-11-04):** the code has **16 rules**. The counts are enforced by
`test_policy_inventory_is_exactly_4_10_2`.

| Exposure | Count | Names |
|---|---:|---|
| ALLOWED | **4** | engagement_rate, views_per_hour_lifetime, views_per_hour_24h, views_gained_24h |
| RESTRICTED | **10** | acceleration, views_per_follower, outlier_score, outlier_score_age_adjusted, outlier_score_nexlev, outlier_band, viral_score, projected_30d_views, estimated_rpm, short_form_label |
| INTERNAL_ONLY | **2** | baseline_median_views, semantic_score |

`acceleration` and `views_per_follower` were ALLOWED (with review) in Phases 1.1 and 1.2. They were moved to
RESTRICTED because their compliance status is uncertain and the formulas have defects; see
docs/phase-2/PHASE_2_EXECUTION_PLAN.md, section 1. Either returns to ALLOWED only with written confirmation from
the Google audit or counsel.

Of the 10 restricted rules:

- **8** correspond to numeric fields the mapping knows about. They pass through only with approval.
- `outlier_band` is a string, so it is never mapped.
- `short_form_label` gates the `SHORT` content-type label rather than a number.
- `short_form` (the query filter) is a different thing: a **duration filter on raw metadata** (owner decision F-6, 2026-11-06): a video is short when its duration is more than 0 and at most 180 seconds, inclusive. A zero, missing, null or invalid duration is not short. ViralTrack applies it itself; the foundation's `is_short` flag is ignored. It is not YouTube's Shorts classification and does not make the `SHORT` label available.

History: Phase 1.1 reported 6 / 8 / 2. Its summary listed fewer names because "views per hour (lifetime / 24 h)"
counted as one entry and `outlier_band` was grouped with the outlier scores.

Raw metrics are not policy rules: `views`, `likes`, `comments`, plus the creator's `followers`,
`content_count` and, in history, `total_views`.

## Provenance requirements (all metrics)

Every metric carries provider `youtube`, adapter `youtube/niche-finder-http`, origin (`real_provider_data` /
`demo` / `test`, which must equal the record's origin) and kind (RAW / DERIVED). For derived metrics, source
is `niche-finder` and the note reads "Calculated by niche-finder from YouTube data; not a YouTube metric".
With origin `real`, ids must be real YouTube ids (11-character video id, `UC`+22 channel id). `collected_at` is
`None` for video list items (the foundation does not expose fetch times) and is set for history snapshots.

## Full inventory

"ViralTrack exposure" covers the adapter's normalized output, which is the only ViralTrack surface: no
ViralTrack API, dashboard, export or MCP exists yet. "Foundation exposure" covers niche-finder's own
dashboard, HTTP API, export, MCP and alerts (see "Leak surfaces").

| Metric | Formula (upstream) | Source fields | Kind | Google policy basis | Exposure | ViralTrack output | Sort / filter | Foundation exposure | Tests |
|---|---|---|---|---|---|---|---|---|---|
| views, likes, comments | API value | statistics.* | RAW | API data | n/a (raw) | Yes | sort by `views` | Yes | `test_raw_and_allowed_derived_by_default` |
| followers, content_count | API value (subs rounded by YouTube) | channel statistics | RAW | API data | n/a (raw) | Yes (creator) | — | Yes | `test_search_and_creator`, `test_creator_metrics_are_checked_too` |
| engagement_rate | `(likes + comments) / views × 100`; None upstream only if **both** are hidden (a hidden like count counts as 0), so ViralTrack omits it when likes are hidden | views, likes, comments | DERIVED | Simple arithmetic, YouTube data only | **ALLOWED** | Yes (omitted when likes are hidden) | sort **refused** (D3: the foundation orders hidden likes as zero) | Yes | `test_raw_and_allowed_derived_by_default`, `test_engagement_rate_omitted_when_likes_are_hidden`, `test_engagement_rate_is_not_a_sort_and_the_reason_is_stated` |
| views_per_hour_lifetime | `views / hours since publication` | views, publishedAt | DERIVED | Simple arithmetic | **ALLOWED** | Yes (dated videos only, D3-06) | sort **refused** (D3: upstream ranks undated videos first on a fabricated rate) | Yes | same |
| views_per_hour_24h | `(latest views − views at the latest snapshot ≥ 24 h older) / hours between`, floored at 0, over stored snapshots. With no snapshot that old the **oldest** is used, so the window varies: longer than 24 h, or shorter when history is thin. Snapshots before the 2026-08-24 view-count change are dropped once a newer one exists | stored view snapshots | DERIVED | Simple arithmetic; needs stored statistics (≤ 30 d) | **ALLOWED** | **No** (D3-05: snapshot recency unknown) | sort **refused** (D3-05) | Yes | `test_allowed_derived_sort_and_unknown_sort` |
| views_gained_24h | `int(views_per_hour_24h × 24)`: a rate scaled to a day, **not** a measured view delta | snapshots | DERIVED | Multiplication of an allowed value | **ALLOWED** | **No** (D3-05) | sort **refused** (D3-05) | Yes | same |
| acceleration | `vph24 / max(2·vph48 − vph24, 0.01)` in discovery; `vph24 / vph7d` in upstream inspection. Exactly 1.0 with under 24 h of history; unbounded when the earlier rate ≤ 0 | snapshots | DERIVED | Ratio built on an estimated rate; close to a custom score | **RESTRICTED** (Phase 2) | No | sort refused | **Yes** (+ "heating up" / "cooling" labels and alerts upstream) | `test_restricted_since_phase_2_cannot_be_sorted_by`, `test_policy_inventory_is_exactly_4_10_2` |
| views_per_follower | `views / max(subscribers or 0, 1)`; `views / 1` when the subscriber count is hidden | views, channel subscriberCount | DERIVED | Ordering many channels' videos by it is close to ranking channels | **RESTRICTED** (Phase 2) | No | sort `vsr` refused; the adapter sends `min_views_per_subscriber=0` so upstream's default `≥ 1.0` filter does not apply | **Yes** | same, plus `test_adapter_never_filters_or_ranks_by_restricted_scores` |
| outlier_score | `views / median(views of the channel's previous 10 uploads, same format)`, then banded | views, channel's other videos | DERIVED | Custom score assigned from ratios to a baseline | **RESTRICTED** | No | sort refused (`RestrictedMetric`), never filtered | **Yes** | `test_restricted_metrics_never_mapped_without_approval`, `test_sorting_by_a_restricted_metric_is_refused_before_any_call`, `test_adapter_never_filters_or_ranks_by_restricted_scores` |
| outlier_score_age_adjusted | outlier score / fitted maturity curve(age) | + fitted curve | DERIVED | Model projection | **RESTRICTED** | No | refused | **Yes** | same |
| outlier_score_nexlev | `views / lifetime mean views per video` (third-party method) | channel totals | DERIVED | Custom score | **RESTRICTED** | No | not sortable | **Yes** | same |
| outlier_band | label from outlier score ("mega outlier"…) | outlier score | DERIVED | Custom label | **RESTRICTED** | No (string, not mapped) | — | **Yes** | allow-list (`test_every_upstream_numeric_field_is_classified`) |
| viral_score | projected views per subscriber (maturity-curve projection) | views, subs, curve | DERIVED | Projection / custom score | **RESTRICTED** | No | refused | **Yes** (upstream's default sort) | `test_default_sort_is_by_raw_views` |
| projected_30d_views | views projected to day 30 | views, age, curve | DERIVED | Projection | **RESTRICTED** | No | — | **Yes** | restricted-mapping tests |
| estimated_rpm | NexLev-style niche RPM × 0.70 (external tables; Social Blade range) | category + external data | DERIVED | Financial estimate + external data | **RESTRICTED** (review) | No | — | **Yes** | same |
| short_form_label | `duration ≤ 180 s ⇒ Short` | duration | DERIVED label | Inferred content type | **RESTRICTED** (review, decision C) | `SHORT` only with approval; otherwise `VIDEO` | duration filter (`only_shorts`) allowed | **Yes** | `test_shorts_filter_is_allowed_but_label_is_restricted` |
| baseline_median_views | median of the previous 10 uploads | channel videos | DERIVED | Input to a restricted score | **INTERNAL_ONLY** | Never | — | Yes | `test_internal_only_metrics_never_mapped` |
| semantic_score | cosine(query embedding, title embedding) | embeddings | DERIVED | Search ordering only | **INTERNAL_ONLY** | Never (ordering of text search only) | — | Yes | same |

## Leak surfaces

| Surface | Status | Evidence |
|---|---|---|
| ViralTrack normalized content (fields) | **Protected** | Allow-list mapping, policy check, `Content` rejects non-ALLOWED (`test_content_rejects_unexposable_metrics`) |
| ViralTrack sorting | **Protected** | Explicit `sort_by`, restricted sorts refused before any request |
| ViralTrack filtering | **Protected** | The adapter sends only an allow-listed set of parameters, never `min_outlier_score`, `preset` or `sort_by=viral/outlier/vsr/acceleration`; `/api/viral` always gets `min_views_per_subscriber=0` (`test_adapter_never_filters_or_ranks_by_restricted_scores`). Upstream defaults apply no outlier filter (`min_outlier_score` None / 0.0 is ignored upstream) |
| ViralTrack search results | **Protected** | Same mapping as discovery |
| ViralTrack exports, API, dashboard, MCP | **Do not exist** | Nothing to leak today. Any future surface must consume `Content` |
| ViralTrack logs and CLI output | **Protected** | The provider logs nothing; retention and config print counts and masked settings only (`test_describe_masks_secrets`) |
| **Foundation dashboard, HTTP API, CSV/TSV export, MCP (100 tools), Chrome extension** | **EXPOSED (restricted metrics visible)** | Upstream code, not modifiable. Bound to `127.0.0.1`. Classified **INTERNAL_ONLY** and must not be offered to end users (OWNER_DECISIONS.md, E) |
| **Foundation alerts and digest (Telegram, webhook, e-mail)** | **Disabled by default**, would expose restricted values | `NOTIFY_*`/`SMTP_*` are commented out in upstream `.env.example`. Must stay unconfigured until approval (E) |

Hiding a metric in a UI does not count as protection. Protection is enforced where the data leaves the
adapter. The foundation surfaces are not protected; they are restricted by deployment and need an owner
decision.

## Approval state

No metric has been approved by Google or reviewed by counsel. RESTRICTED stays disabled
(`VT_YOUTUBE_ANALYTICS_AMENDMENT_ACCEPTED=false`).
