"""Platform-neutral content model.

Every number that came from outside ViralTrack is a `Metric` carrying its
`Provenance`: which provider produced it, from which upstream source, when it
was collected, and whether it is raw platform data or derived by software.
Raw and derived metrics live in separate collections so they cannot be mixed
up when displayed or stored.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Platform(str, Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class ContentType(str, Enum):
    VIDEO = "video"
    SHORT = "short"   # YouTube Short / Instagram Reel / TikTok video
    UNKNOWN = "unknown"


class MetricKind(str, Enum):
    RAW = "raw"          # returned by the platform API as-is
    DERIVED = "derived"  # calculated by software from raw data


@dataclass(frozen=True)
class Provenance:
    provider: str            # ViralTrack provider id, e.g. "youtube"
    source: str              # who produced the value, e.g. "youtube-data-api", "niche-finder"
    collected_at: datetime | None  # when the provider last read it; None = unknown
    kind: MetricKind
    note: str | None = None  # formula or caveat, shown to users for derived values


@dataclass(frozen=True)
class Metric:
    name: str
    value: float | int
    provenance: Provenance


@dataclass(frozen=True)
class Creator:
    platform: Platform
    creator_id: str
    name: str | None = None
    handle: str | None = None
    url: str | None = None
    followers: Metric | None = None
    content_count: Metric | None = None


@dataclass(frozen=True)
class Content:
    platform: Platform
    content_id: str
    content_type: ContentType
    url: str
    creator: Creator
    title: str | None = None
    thumbnail_url: str | None = None
    published_at: datetime | None = None
    duration_seconds: int | None = None
    language: str | None = None
    region: str | None = None
    category: str | None = None
    hashtags: tuple[str, ...] = ()
    metrics: tuple[Metric, ...] = ()          # RAW only
    derived: tuple[Metric, ...] = ()          # DERIVED only
    retrieved_at: datetime | None = None      # when ViralTrack read it from the provider
    provider: str = ""

    def __post_init__(self):
        for m in self.metrics:
            if m.provenance.kind is not MetricKind.RAW:
                raise ValueError(f"metric {m.name!r} is not raw; put it in `derived`")
        for m in self.derived:
            if m.provenance.kind is not MetricKind.DERIVED:
                raise ValueError(f"metric {m.name!r} is not derived; put it in `metrics`")

    def metric(self, name: str) -> Metric | None:
        return next((m for m in self.metrics + self.derived if m.name == name), None)


@dataclass(frozen=True)
class ContentPage:
    items: tuple[Content, ...]
    total: int | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)
