# Metric Inventory and Approval (Phase 1.2)

Source of truth: `viraltrack/providers/youtube/metric_policy.py` (`RULES`) and
`viraltrack/providers/youtube/mapping.py`. Formulas are read from the upstream code at `d872014`
(`backend/domain/metrics.py`, `backend/application/discovery.py`). Classifications are engineering
judgements, not legal conclusions.

## Count reconciliation

The Phase 1.1 summary said "6 allowed" and "8 restricted" but listed fewer names, because it grouped some of
them. The code has **16 rules**:

| Exposure | Count | Names |
|---|---:|---|
| ALLOWED | **6** | engagement_rate, views_per_hour_lifetime, views_per_hour_24h, views_gained_24h, acceleration, views_per_follower |
| RESTRICTED | **8** | outlier_score, outlier_score_age_adjusted, outlier_score_nexlev, outlier_band, viral_score, projected_30d_views, estimated_rpm, short_form_label |
| INTERNAL_ONLY | **2** | baseline_median_views, semantic_score |

The two missing names:

- "Views per hour (lifetime / 24 h)" was **two** metrics, which gives 6 allowed.
- "Outlier scores (3 variants)" plus **outlier_band** gives the 4 outlier entries; with viral score, 30-day
  projection, RPM and the Shorts label that makes 8 restricted.

Of the 8 restricted rules:

- **6** correspond to numeric fields the mapping knows about and would pass through only with approval.
- `outlier_band` is a string, so it is never mapped.
- `short_form_label` gates the `SHORT` content-type label rather than a number.

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
| engagement_rate | `(likes + comments) / views × 100`; None if likes and comments are hidden | views, likes, comments | DERIVED | Simple arithmetic, YouTube data only | **ALLOWED** | Yes | sort `engagement` allowed | Yes | `test_raw_and_allowed_derived_by_default` |
| views_per_hour_lifetime | `views / hours since publication` | views, publishedAt | DERIVED | Simple arithmetic | **ALLOWED** | Yes | sort allowed | Yes | same |
| views_per_hour_24h | `(latest views − views at ~24 h ago) / hours between` over stored snapshots; drops snapshots before the 2026-08-27 view-count change; uses the oldest snapshot if none is 24 h old | stored view snapshots | DERIVED | Simple arithmetic; needs stored statistics (≤ 30 d) | **ALLOWED** | Yes | sort `vph` allowed | Yes | `test_allowed_derived_sort_and_unknown_sort` |
| views_gained_24h | latest views − views ~24 h earlier | snapshots | DERIVED | Simple arithmetic | **ALLOWED** | Yes | sort `velocity` allowed | Yes | same |
| acceleration | `vph24 / max(vph_prev24, 0.01)`, `vph_prev24 = 2·vph48 − vph24` (discovery) | snapshots | DERIVED | Division of two simple rates | **ALLOWED** (review, decision B) | Yes | sort allowed | Yes (+ "heating up" / "cooling" labels upstream) | same |
| views_per_follower | `views / max(subscribers, 1)` | views, channel subscriberCount | DERIVED | Simple division of YouTube data | **ALLOWED** (review, decision B) | Yes | sort `vsr` allowed; upstream `/api/viral` filters `≥ 1.0` by default | Yes | same |
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
| ViralTrack filtering | **Protected** | The adapter sends only an allow-listed set of parameters, never `min_outlier_score`, `preset` or `sort_by=viral/outlier` (`test_adapter_never_filters_or_ranks_by_restricted_scores`). Upstream defaults apply no outlier filter (`min_outlier_score` None / 0.0 is ignored upstream) |
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
