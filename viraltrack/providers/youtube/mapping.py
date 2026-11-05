"""Maps niche-finder JSON to ViralTrack's platform-neutral model.

Raw values (YouTube Data API numbers) and derived values (calculated by
niche-finder) are separated here, following niche-finder's own
`/api/scores` classification (`source: youtube` vs `source: niche-finder`).
Derived values pass through `MetricPolicy`: a value whose exposure is not
allowed is dropped here and never reaches `Content`. Upstream fields not
listed below are ignored (allow-list).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from viraltrack.domain import (
    Content,
    ContentType,
    Creator,
    DataOrigin,
    Exposure,
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
REQUIRES_RAW = {"engagement_rate": ("likes",)}

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


def _check_ids(ctx: MappingContext, video_id: str | None, channel_id: str) -> None:
    if ctx.origin is not DataOrigin.REAL_PROVIDER_DATA:
        return
    if video_id is not None and not _VIDEO_ID.match(video_id):
        raise ProviderError(PROVIDER_ID, f"{video_id!r} is not a YouTube video id; "
                            "is the foundation serving demo data? (set VT_YOUTUBE_DATA_ORIGIN=demo)")
    if not _CHANNEL_ID.match(channel_id):
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


def _derived(ctx: MappingContext, item: dict,
             first_seen: datetime | None = None) -> tuple[Metric, ...]:
    out = []
    for key, name in DERIVED_VIDEO_METRICS.items():
        value = _num(item.get(key))
        if value is None or not ctx.policy.exposable(name):
            continue
        if any(_num(item.get(raw)) is None for raw in REQUIRES_RAW.get(name, ())):
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
        value = _num(item.get(key))
        if value is not None:
            out.append(Metric(name=name, value=value, provenance=provenance))
    return tuple(out)


def channel_url(channel_id: str, handle: str | None) -> str:
    if handle and handle.startswith("@"):
        return f"https://www.youtube.com/{handle}"
    return f"https://www.youtube.com/channel/{channel_id}"


def map_video(item: dict, ctx: MappingContext) -> Content:
    """One element of `results` from /api/viral or /api/search."""
    video_id = item.get("videoId")
    channel_id = item.get("channelId")
    if not video_id or not channel_id:
        raise ProviderError(PROVIDER_ID, "video item without videoId/channelId")
    _check_ids(ctx, video_id, channel_id)

    # niche-finder does not report per-item fetch times on these endpoints, so the time the
    # numbers were read from YouTube (`collected_at`) is unknown: None, not invented. What it does
    # report is `firstSeenAt`, when it first stored the item: kept as `foundation_first_seen_at`.
    # ViralTrack's own receive time is `Content.retrieved_at`.
    first_seen = foundation_first_seen_time(item.get("firstSeenAt"))
    raw = raw_provenance(ctx, None, first_seen)
    handle = item.get("channelUrl")
    followers = _num(item.get("channelSubscribers"))
    uploads = _num(item.get("channelVideoCount"))
    creator = Creator(
        platform=Platform.YOUTUBE,
        creator_id=channel_id,
        name=item.get("channelTitle"),
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
        url=item.get("url") or f"https://www.youtube.com/watch?v={video_id}",
        creator=creator,
        origin=ctx.origin,
        title=item.get("title"),
        thumbnail_url=item.get("thumbnail"),
        published_at=parse_time(item.get("publishedAt")),
        duration_seconds=_num(item.get("lengthSeconds")),
        language=item.get("language"),
        category=item.get("category"),
        metrics=_raw(item, RAW_VIDEO_METRICS, raw),
        derived=_derived(ctx, item, first_seen),
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
