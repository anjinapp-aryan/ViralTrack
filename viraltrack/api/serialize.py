"""Domain objects to API schemas. The only place the API reads `Content`, `Creator` and `Metric`.

`Content` already refuses any metric whose exposure is not ALLOWED. This module adds the contract: only the
named fields of `schemas.VideoMetrics` and `schemas.VideoDerived` are filled; any other metric a future
approval might let through is not part of API v1 and is left out, deliberately and visibly here.
"""

from __future__ import annotations

from viraltrack.api import schemas
from viraltrack.domain import Content, Creator, DataOrigin, Metric

RAW_FIELDS = tuple(schemas.VideoMetrics.model_fields)  # views, likes, comments
DERIVED_FIELDS = tuple(schemas.VideoDerived.model_fields)  # engagement_rate, views_per_hour_lifetime


def metric(m: Metric | None) -> schemas.MetricValue | None:
    if m is None:
        return None
    p = m.provenance
    return schemas.MetricValue(
        value=m.value,
        kind=p.kind.value,
        source=p.source,
        provider=p.provider,
        origin=p.origin.value,
        collected_at=p.collected_at,
        foundation_first_seen_at=p.foundation_first_seen_at,
        note=p.note,
    )


def creator(c: Creator) -> schemas.CreatorRef:
    return schemas.CreatorRef(
        id=c.creator_id,
        platform=c.platform.value,
        name=c.name,
        handle=c.handle,
        url=c.url,
        followers=metric(c.followers),
        content_count=metric(c.content_count),
    )


def video(c: Content) -> schemas.Video:
    raw = {m.name: m for m in c.metrics}
    derived = {m.name: m for m in c.derived}
    return schemas.Video(
        id=c.content_id,
        platform=c.platform.value,
        url=c.url,
        title=c.title,
        thumbnail_url=c.thumbnail_url,
        published_at=c.published_at,
        duration_seconds=c.duration_seconds,
        content_type=c.content_type.value,
        category=c.category,
        language=c.language,
        region=c.region,
        creator=creator(c.creator),
        metrics=schemas.VideoMetrics(**{f: metric(raw.get(f)) for f in RAW_FIELDS}),
        derived=schemas.VideoDerived(**{f: metric(derived.get(f)) for f in DERIVED_FIELDS}),
        origin=c.origin.value,
        retrieved_at=c.retrieved_at,
    )


def is_demo(origin: DataOrigin) -> bool:
    return origin is not DataOrigin.REAL_PROVIDER_DATA
