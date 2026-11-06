"""Maps niche-finder JSON to ViralTrack's platform-neutral model.

Raw values (YouTube Data API numbers) and derived values (calculated by
niche-finder) are separated here, following niche-finder's own
`/api/scores` classification (`source: youtube` vs `source: niche-finder`).
Derived values pass through `MetricPolicy`: a value whose exposure is not
allowed is dropped here and never reaches `Content`. Upstream fields not
listed below are ignored (allow-list).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from viraltrack.domain import (
    Content,
    ContentType,
    Creator,
    DataOrigin,
    Exposure,
    FunnelStage,
    Metric,
    MetricKind,
    MetricPolicy,
    Platform,
    Provenance,
    ProviderError,
)
from viraltrack.providers.youtube.client import PROVIDER_ID

ADAPTER_ID = "youtube/niche-finder-http"
RAW_SOURCE = "youtube-data-api"
DERIVED_SOURCE = "niche-finder"

# niche-finder field -> ViralTrack metric name, raw YouTube numbers
RAW_VIDEO_METRICS = {"views": "views", "likes": "likes", "comments": "comments"}

# niche-finder field -> ViralTrack metric name (policy rule name), values niche-finder
# calculates. Passed through unchanged, and only when the policy allows exposure.
DERIVED_VIDEO_METRICS = {
    "engagementRate": "engagement_rate",
    "vphLifetime": "views_per_hour_lifetime",
    "vph24h": "views_per_hour_24h",
    "viewsGained24h": "views_gained_24h",
    "acceleration": "acceleration",
    "viewsPerSubscriber": "views_per_follower",
    "outlierScore": "outlier_score",
    "outlierScoreAgeAdjusted": "outlier_score_age_adjusted",
    "outlierScoreNexlev": "outlier_score_nexlev",
    "viralScore": "viral_score",
    "projected30dViews": "projected_30d_views",
    "estimatedRpm": "estimated_rpm",
}

# Derived values that are only meaningful when a raw input is present. niche-finder
# counts a hidden like count as 0 in engagementRate, which understates it.
REQUIRES_RAW = {"engagement_rate": ("likes",), "views_per_hour_lifetime": ("views",)}

# D3-05: the foundation computes these over "the latest snapshot at least 24 h older, else the oldest one",
# and reports no snapshot time. How recent the window is, and how long, is therefore unknown; a rate over
# two hours
# or over weeks would be shown as a current 24-hour rate. They are withheld until a snapshot time is reported.
# Neither the response time nor the collection time stands in for it, and no lifetime value is substituted.
WITHHELD_UNKNOWN_SNAPSHOT_RECENCY = frozenset({"views_per_hour_24h", "views_gained_24h"})

# D3-06: a lifetime rate is "views / hours since publication"; without a usable publication date the
# foundation computes it from an age of 0 h (floored to 1 h). It is shown only for a dated video that is not
# in the future.
NEEDS_PUBLICATION_DATE = frozenset({"views_per_hour_lifetime"})

# Real YouTube ids. The niche-finder demo seed uses ids like "bvid008", so a demo
# corpus served as "real" is rejected instead of being passed off as provider data.
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")

ORIGINS = {"real": DataOrigin.REAL_PROVIDER_DATA, "demo": DataOrigin.DEMO, "test": DataOrigin.TEST}


@dataclass(frozen=True)
class MappingContext:
    origin: DataOrigin
    policy: MetricPolicy
    retrieved_at: datetime


def parse_time(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _bad(item: dict, key: str, expected: str):
    kind = type(item.get(key)).__name__
    raise ProviderError(PROVIDER_ID, f"video item field {key!r} must be {expected}, got {kind}")


def _number(item: dict, key: str):
    """A numeric field: absent or null is None (unknown); a boolean, string or non-finite number is bad."""
    value = item.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _bad(item, key, "a number")
    if isinstance(value, float) and not math.isfinite(value):
        _bad(item, key, "a finite number")
    return value


def _text(item: dict, key: str) -> str | None:
    value = item.get(key)
    if value is not None and not isinstance(value, str):
        _bad(item, key, "text")
    return value


def count(value) -> int | None:
    """A count or total: a non-negative integer. A boolean (an int in Python), a negative, a float, a string
    or anything else is not a count and is None (unknown), never coerced."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


# Funnel steps that name a RESTRICTED threshold. The adapter never sends those thresholds, so a step like this
# means the response is not what was asked for; the funnel (and the hint built from it) is withheld.
_RESTRICTED_STEP = re.compile(r"per subscriber|outlier|viral|acceleration", re.I)


def mentions_restricted_metric(text: str) -> bool:
    return bool(_RESTRICTED_STEP.search(text))


def map_funnel(raw) -> tuple[tuple[FunnelStage, ...] | None, str | None]:
    """The foundation's `funnel` -> (stages, note). (None, None): not reported. (None, note): reported but not
    usable, and the note says so. An empty list is a reported, empty funnel, which is not the same as none."""
    if raw is None:
        return None, None
    if not isinstance(raw, list):
        return None, "the foundation's funnel is malformed and was not used"
    stages = []
    for entry in raw:
        valid = (isinstance(entry, dict) and isinstance(entry.get("step"), str)
                 and count(entry.get("remaining")) is not None)
        if not valid:
            return None, "the foundation's funnel has an invalid stage and was not used"
        if mentions_restricted_metric(entry["step"]):
            return None, "the foundation's funnel names a restricted metric and was withheld"
        stages.append(FunnelStage(entry["step"], entry["remaining"]))
    return tuple(stages), None


# `short_form` is a DURATION test on raw video metadata, not YouTube's Shorts classification (owner
# decision, F-6):
# short = a known duration of more than 0 and at most 180 seconds, inclusive. Zero, missing, null and invalid
# durations are NOT short. The foundation's own `is_short` flag never decides this.
SHORT_FORM_MAX_SECONDS = 180


def duration_seconds(value) -> int | float | None:
    """A video duration: a finite, non-negative number. Missing, null, boolean, text or negative is None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value if value >= 0 else None


def is_short_form(duration) -> bool:
    return duration is not None and 0 < duration <= SHORT_FORM_MAX_SECONDS


def published_time(value) -> datetime | None:
    """A publication time as aware UTC. Missing, malformed, not text, or without an offset is None (unknown):
    the date is never assumed to be UTC, and never replaced by the collection or the current time."""
    if not isinstance(value, str):
        return None
    parsed = parse_time(value)
    if parsed is None or parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _check_ids(ctx: MappingContext, video_id: str | None, channel_id: str) -> None:
    if ctx.origin is not DataOrigin.REAL_PROVIDER_DATA:
        return
    if video_id is not None and not _VIDEO_ID.fullmatch(video_id):
        raise ProviderError(PROVIDER_ID, f"{video_id!r} is not a YouTube video id; "
                            "is the foundation serving demo data? (set VT_YOUTUBE_DATA_ORIGIN=demo)")
    if not _CHANNEL_ID.fullmatch(channel_id):
        raise ProviderError(PROVIDER_ID, f"{channel_id!r} is not a YouTube channel id")


def foundation_first_seen_time(value) -> datetime | None:
    """The foundation's `firstSeenAt` (`first_seen_at`: set once, when the foundation first inserted
    the row; its upserts never rewrite it) as an aware UTC datetime.
    A missing, malformed or offset-less value is None: unknown, never assumed to be UTC."""
    parsed = parse_time(value)
    if parsed is None or parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def raw_provenance(ctx: MappingContext, collected_at: datetime | None,
                   first_seen: datetime | None = None) -> Provenance:
    return Provenance(provider=PROVIDER_ID, source=RAW_SOURCE, collected_at=collected_at,
                      kind=MetricKind.RAW, origin=ctx.origin, adapter=ADAPTER_ID,
                      exposure=Exposure.ALLOWED, foundation_first_seen_at=first_seen)


def _derived(ctx: MappingContext, item: dict, first_seen: datetime | None = None,
             published_at: datetime | None = None) -> tuple[Metric, ...]:
    out = []
    for key, name in DERIVED_VIDEO_METRICS.items():
        value = _number(item, key)
        if value is None or not ctx.policy.exposable(name):
            continue
        if name in WITHHELD_UNKNOWN_SNAPSHOT_RECENCY:
            continue
        if name in NEEDS_PUBLICATION_DATE and (published_at is None or published_at > ctx.retrieved_at):
            continue
        if any(_number(item, raw) is None for raw in REQUIRES_RAW.get(name, ())):
            continue
        rule = ctx.policy.rules[name]
        prov = Provenance(provider=PROVIDER_ID, source=DERIVED_SOURCE, collected_at=None,
                          kind=MetricKind.DERIVED, origin=ctx.origin, adapter=ADAPTER_ID,
                          exposure=Exposure.ALLOWED, foundation_first_seen_at=first_seen,
                          note=f"Calculated by niche-finder from YouTube data; not a YouTube "
                               f"metric. {rule.basis}")
        out.append(Metric(name=name, value=value, provenance=prov))
    return tuple(out)


def _raw(item: dict, fields: dict, provenance: Provenance) -> tuple[Metric, ...]:
    out = []
    for key, name in fields.items():
        value = _number(item, key)
        if value is not None:
            out.append(Metric(name=name, value=value, provenance=provenance))
    return tuple(out)


def channel_url(channel_id: str, handle: str | None) -> str:
    if handle and handle.startswith("@"):
        return f"https://www.youtube.com/{handle}"
    return f"https://www.youtube.com/channel/{channel_id}"


def map_video(item: dict, ctx: MappingContext) -> Content:
    """One element of `results` from /api/viral or /api/search."""
    if not isinstance(item, dict):
        raise ProviderError(PROVIDER_ID, f"video item must be an object, got {type(item).__name__}")
    video_id = item.get("videoId")
    channel_id = item.get("channelId")
    if not video_id or not channel_id:
        raise ProviderError(PROVIDER_ID, "video item without videoId/channelId")
    if not isinstance(video_id, str) or not isinstance(channel_id, str):
        raise ProviderError(PROVIDER_ID, "video item videoId/channelId must be text")
    _check_ids(ctx, video_id, channel_id)

    # niche-finder does not report per-item fetch times on these endpoints, so the time the
    # numbers were read from YouTube (`collected_at`) is unknown: None, not invented. What it does
    # report is `firstSeenAt`, when it first stored the item: kept as `foundation_first_seen_at`.
    # ViralTrack's own receive time is `Content.retrieved_at`.
    first_seen = foundation_first_seen_time(item.get("firstSeenAt"))
    raw = raw_provenance(ctx, None, first_seen)
    handle = _text(item, "channelUrl")
    followers = _number(item, "channelSubscribers")
    uploads = _number(item, "channelVideoCount")
    published_at = published_time(item.get("publishedAt"))
    creator = Creator(
        platform=Platform.YOUTUBE,
        creator_id=channel_id,
        name=_text(item, "channelTitle"),
        handle=handle,
        url=channel_url(channel_id, handle),
        followers=Metric("followers", followers, raw) if followers is not None else None,
        content_count=Metric("content_count", uploads, raw) if uploads is not None else None,
    )
    # "Short" is inferred upstream from duration; it is a label only with approval.
    content_type = ContentType.VIDEO
    if item.get("isShort") is True and ctx.policy.exposable("short_form_label"):
        content_type = ContentType.SHORT
    return Content(
        platform=Platform.YOUTUBE,
        content_id=video_id,
        content_type=content_type,
        url=_text(item, "url") or f"https://www.youtube.com/watch?v={video_id}",
        creator=creator,
        origin=ctx.origin,
        title=_text(item, "title"),
        thumbnail_url=_text(item, "thumbnail"),
        published_at=published_at,
        duration_seconds=duration_seconds(item.get("lengthSeconds")),
        language=_text(item, "language"),
        category=_text(item, "category"),
        metrics=_raw(item, RAW_VIDEO_METRICS, raw),
        derived=_derived(ctx, item, first_seen, published_at),
        retrieved_at=ctx.retrieved_at,
        provider=PROVIDER_ID,
    )


def map_channel(body: dict, ctx: MappingContext) -> Creator:
    """/api/channels/{channel_id}"""
    channel_id = body.get("channelId")
    profile = body.get("profile")
    if not channel_id or not isinstance(profile, dict):
        raise ProviderError(PROVIDER_ID, "channel payload without channelId/profile")
    _check_ids(ctx, None, channel_id)
    raw = raw_provenance(ctx, None)
    followers = None if profile.get("subscribersHidden") else _num(profile.get("subscribers"))
    uploads = _num(profile.get("videoCount"))
    handle = profile.get("handle")
    return Creator(
        platform=Platform.YOUTUBE,
        creator_id=channel_id,
        name=profile.get("title"),
        handle=handle,
        url=channel_url(channel_id, handle),
        followers=Metric("followers", followers, raw) if followers is not None else None,
        content_count=Metric("content_count", uploads, raw) if uploads is not None else None,
    )


def map_channel_point(point: dict, ctx: MappingContext) -> tuple[datetime, tuple[Metric, ...]] | None:
    """One element of /api/channels/{id}/history `points` (a stored snapshot)."""
    captured = parse_time(point.get("t"))
    if captured is None:
        return None
    fields = {"subscribers": "followers", "videos": "content_count", "views": "total_views"}
    return captured, _raw(point, fields, raw_provenance(ctx, captured))
