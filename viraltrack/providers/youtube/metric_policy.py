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
    MetricRule("engagement_rate", A, "(likes + comments) / views x 100"),
    MetricRule("views_per_hour_lifetime", A, "views / hours since publication"),
    MetricRule("views_per_hour_24h", A, "view delta between two stored snapshots / hours between them"),
    MetricRule("views_gained_24h", A, "view delta between two stored snapshots"),
    MetricRule("acceleration", A, "views_per_hour_24h / views per hour of the previous window",
               review="ratio of two simple rates; confirm it is not a 'custom score'"),
    MetricRule("views_per_follower", A, "video views / channel subscribers",
               review="compares a video with its own channel; confirm it is not channel gamification"),
    # --- need the accepted Analytics & Reporting amendment ---------------------
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
