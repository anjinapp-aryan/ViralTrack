"""Exposure rules for every value niche-finder derives from YouTube data.

Basis: YouTube "Complying with YouTube's Developer Policies" guide (read
2026-11-03). Without approval, acceptable metrics "use only YouTube API data
and combine them via simple mathematical calculations (addition, subtraction,
averages, multiplication, division)" and "must not incorporate any other
external data sources". Custom scores, financial projections, inferred
content types, rankings of channels and projections need the accepted
"Analytics & Reporting" amendment (derived-metrics policy).

These are engineering classifications, not legal conclusions; `review`
marks the ones a human must confirm. docs/phase-1/DERIVED_METRIC_POLICY.md
holds the same table with sources.
"""
from __future__ import annotations

from viraltrack.config import YOUTUBE_ANALYTICS_AMENDMENT
from viraltrack.domain import Exposure, MetricPolicy, MetricRule

A, R, INTERNAL = Exposure.ALLOWED, Exposure.RESTRICTED, Exposure.INTERNAL_ONLY
AMD = YOUTUBE_ANALYTICS_AMENDMENT

RULES: list[MetricRule] = [
    # --- simple arithmetic over YouTube data only ------------------------------
    MetricRule("engagement_rate", A, "(likes + comments) / views x 100; omitted by ViralTrack when "
               "the like count is hidden"),
    MetricRule("views_per_hour_lifetime", A, "views / hours since publication"),
    MetricRule("views_per_hour_24h", A, "(latest stored views - views at the latest snapshot at "
               "least 24 h older) / hours between them, floored at 0; with no snapshot that old, the "
               "oldest one is used, so the window varies: longer than 24 h, or shorter when history is thin"),
    MetricRule("views_gained_24h", A, "views_per_hour_24h x 24: a rate scaled to a day, not a "
               "measured view delta"),
    # --- need the accepted Analytics & Reporting amendment ---------------------
    # Owner decision 2026-11-04 (Phase 2 plan, section 1): compliance uncertain.
    MetricRule("acceleration", R, "views_per_hour_24h / estimated views per hour of the previous "
               "24 h (2 x vph48 - vph24); exactly 1.0 with under 24 h of history, unbounded when "
               "the earlier rate is <= 0, defined differently on other upstream endpoints",
               requires=AMD),
    MetricRule("views_per_follower", R, "video views / channel subscribers; views / 1 when the "
               "subscriber count is hidden; ordering many channels' videos by it is close to "
               "ranking channels", requires=AMD),
    MetricRule("outlier_score", R, "views / median views of the channel's previous 10 uploads, "
               "banded into labels (custom score)", requires=AMD),
    MetricRule("outlier_score_age_adjusted", R, "outlier score divided by a fitted maturity curve "
               "(model projection)", requires=AMD),
    MetricRule("outlier_score_nexlev", R, "views / lifetime mean (third-party method)", requires=AMD),
    MetricRule("outlier_band", R, "label derived from the outlier score", requires=AMD),
    MetricRule("viral_score", R, "projected views per subscriber (maturity-curve projection)",
               requires=AMD),
    MetricRule("projected_30d_views", R, "views projected to day 30 (projection)", requires=AMD),
    MetricRule("estimated_rpm", R, "niche RPM tables from third-party sources: financial estimate "
               "and external data", requires=AMD,
               review="combines YouTube data with external data; may stay prohibited even with "
                      "the amendment unless shown as a third-party estimate"),
    MetricRule("short_form_label", R, "Shorts inferred from duration <= 180 s; the API returns no "
               "content type for Shorts", requires=AMD,
               review="the guide says to use only the content type returned by the API"),
    # --- intermediate values, never user-visible -------------------------------
    MetricRule("baseline_median_views", INTERNAL, "input to the outlier score"),
    MetricRule("semantic_score", INTERNAL, "embedding similarity used to order search results"),
]


def youtube_metric_policy(approvals: frozenset[str] = frozenset()) -> MetricPolicy:
    return MetricPolicy(RULES, approvals)
