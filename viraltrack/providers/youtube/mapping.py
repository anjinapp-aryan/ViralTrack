"""Maps niche-finder JSON to ViralTrack's platform-neutral model.

Raw values (YouTube Data API numbers) and derived values (calculated by
niche-finder) are separated here, following niche-finder's own
`/api/scores` classification (`source: youtube` vs `source: niche-finder`).
"""
from __future__ import annotations

from datetime import datetime

from viraltrack.domain import (
    Content,
    ContentType,
    Creator,
    Metric,
    MetricKind,
    Platform,
    Provenance,
    ProviderError,
)
from viraltrack.providers.youtube.client import PROVIDER_ID

RAW_SOURCE = "youtube-data-api"
DERIVED_SOURCE = "niche-finder"

# niche-finder field -> ViralTrack metric name, raw YouTube numbers
RAW_VIDEO_METRICS = {"views": "views", "likes": "likes", "comments": "comments"}

# niche-finder field -> ViralTrack metric name, values niche-finder calculates.
# Passed through as-is with DERIVED provenance; ViralTrack does not compute them.
DERIVED_VIDEO_METRICS = {
    "viewsPerSubscriber": "views_per_follower",
    "engagementRate": "engagement_rate",
    "outlierScore": "outlier_score",
    "outlierScoreAgeAdjusted": "outlier_score_age_adjusted",
    "vphLifetime": "views_per_hour_lifetime",
    "vph24h": "views_per_hour_24h",
    "viewsGained24h": "views_gained_24h",
    "acceleration": "acceleration",
}


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


def raw_provenance(collected_at: datetime | None) -> Provenance:
    return Provenance(provider=PROVIDER_ID, source=RAW_SOURCE, collected_at=collected_at,
                      kind=MetricKind.RAW)


def derived_provenance(collected_at: datetime | None) -> Provenance:
    return Provenance(provider=PROVIDER_ID, source=DERIVED_SOURCE, collected_at=collected_at,
                      kind=MetricKind.DERIVED,
                      note="Calculated by niche-finder from YouTube data; not a YouTube metric")


def _metrics(item: dict, fields: dict, provenance: Provenance) -> tuple[Metric, ...]:
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


def map_video(item: dict, retrieved_at: datetime) -> Content:
    """One element of `results` from /api/viral or /api/search."""
    video_id = item.get("videoId")
    channel_id = item.get("channelId")
    if not video_id or not channel_id:
        raise ProviderError(PROVIDER_ID, "video item without videoId/channelId")

    # niche-finder does not report per-item fetch times on these endpoints, so
    # the collection time of the numbers is unknown (None), not invented.
    raw = raw_provenance(None)
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
    is_short = item.get("isShort")
    content_type = (ContentType.SHORT if is_short is True
                    else ContentType.VIDEO if is_short is False else ContentType.UNKNOWN)
    return Content(
        platform=Platform.YOUTUBE,
        content_id=video_id,
        content_type=content_type,
        url=item.get("url") or f"https://www.youtube.com/watch?v={video_id}",
        creator=creator,
        title=item.get("title"),
        thumbnail_url=item.get("thumbnail"),
        published_at=parse_time(item.get("publishedAt")),
        duration_seconds=_num(item.get("lengthSeconds")),
        language=item.get("language"),
        category=item.get("category"),
        metrics=_metrics(item, RAW_VIDEO_METRICS, raw),
        derived=_metrics(item, DERIVED_VIDEO_METRICS, derived_provenance(None)),
        retrieved_at=retrieved_at,
        provider=PROVIDER_ID,
    )


def map_channel(body: dict) -> Creator:
    """/api/channels/{channel_id}"""
    channel_id = body.get("channelId")
    profile = body.get("profile")
    if not channel_id or not isinstance(profile, dict):
        raise ProviderError(PROVIDER_ID, "channel payload without channelId/profile")
    raw = raw_provenance(None)
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


def map_channel_point(point: dict) -> tuple[datetime, tuple[Metric, ...]] | None:
    """One element of /api/channels/{id}/history `points` (a stored snapshot)."""
    captured = parse_time(point.get("t"))
    if captured is None:
        return None
    raw = raw_provenance(captured)
    fields = {"subscribers": "followers", "videos": "content_count", "views": "total_views"}
    return captured, _metrics(point, fields, raw)
