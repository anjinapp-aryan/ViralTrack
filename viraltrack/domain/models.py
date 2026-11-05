"""Platform-neutral content model.

Every number that came from outside ViralTrack is a `Metric` carrying its
`Provenance`: which provider produced it, from which upstream source, when it
was collected, and whether it is raw platform data or derived by software.
Raw and derived metrics live in separate collections so they cannot be mixed
up when displayed or stored.

Every record also says whether it is real provider data or demo/test data, and
`Content` only accepts metrics whose exposure is ALLOWED (see metric_policy).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from viraltrack.domain.metric_policy import Exposure


class Platform(str, Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class ContentType(str, Enum):
    VIDEO = "video"
    SHORT = "short"   # YouTube Short / Instagram Reel / TikTok video
    UNKNOWN = "unknown"


class DataOrigin(str, Enum):
    REAL_PROVIDER_DATA = "real_provider_data"  # read from a platform through a provider
    DEMO = "demo"                              # synthetic demo corpus (e.g. niche-finder seed_demo)
    TEST = "test"                              # test fixtures


class MetricKind(str, Enum):
    RAW = "raw"          # returned by the platform API as-is
    DERIVED = "derived"  # calculated by software from raw data


@dataclass(frozen=True)
class Provenance:
    provider: str            # ViralTrack provider id, e.g. "youtube"
    source: str              # who produced the value, e.g. "youtube-data-api", "niche-finder"
    collected_at: datetime | None  # when the provider last read it; None = unknown
    kind: MetricKind
    origin: DataOrigin
    adapter: str             # which ViralTrack adapter produced it, e.g. "youtube/niche-finder-http"
    exposure: Exposure       # ALLOWED, or the reason it may not be shown
    note: str | None = None  # formula or caveat, shown to users for derived values
    # When the provider's store FIRST ingested the item (UTC). Not when this value was read from
    # the platform: that is `collected_at`, which stays None while the real capture time is
    # unknown. Never a substitute for it. A naive datetime is refused.
    ingested_at: datetime | None = None

    def __post_init__(self):
        if self.ingested_at is not None:
            if self.ingested_at.tzinfo is None:
                raise ValueError("ingested_at must be timezone-aware (UTC)")
            object.__setattr__(self, "ingested_at", self.ingested_at.astimezone(timezone.utc))


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
    origin: DataOrigin
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
        everything = list(self.metrics + self.derived)
        everything += [m for m in (self.creator.followers, self.creator.content_count) if m]
        for m in everything:
            if m.provenance.exposure is not Exposure.ALLOWED:
                raise ValueError(f"metric {m.name!r} is {m.provenance.exposure.value}; "
                                 "it cannot be part of user-facing content")
            if m.provenance.origin is not self.origin:
                raise ValueError(f"metric {m.name!r} origin {m.provenance.origin.value} "
                                 f"differs from content origin {self.origin.value}")
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
