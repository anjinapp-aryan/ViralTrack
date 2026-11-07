"""Response and error schemas of the ViralTrack HTTP API, version 1.

Every model forbids extra fields, so a value that is not part of this contract cannot be added to a response
by accident. Metric fields are named one by one: the contract can only carry what the metric policy allows
(raw views, likes, comments, followers and uploads; derived engagement rate and lifetime views per hour).
A value the platform did not report, or the creator hid, is `null`. It is never 0.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

PlatformName = Literal["youtube", "instagram", "tiktok"]
OriginName = Literal["real_provider_data", "demo", "test"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MetricValue(_Strict):
    """One number from outside ViralTrack, with where it came from."""

    value: float | int
    kind: Literal["raw", "derived"] = Field(description="raw: returned by the platform; derived: calculated")
    source: str = Field(description="who produced the value, e.g. youtube-data-api")
    provider: str
    origin: OriginName = Field(description="real provider data, or synthetic demo or test data")
    collected_at: datetime | None = Field(
        description="when the value was read from the platform; null when the provider does not report it"
    )
    foundation_first_seen_at: datetime | None = Field(
        description="when the foundation first stored the item; not the read time of this value"
    )
    note: str | None = Field(description="formula or caveat; set for derived values")


class VideoMetrics(_Strict):
    views: MetricValue | None
    likes: MetricValue | None = Field(description="null when the creator hides likes or none was reported")
    comments: MetricValue | None


class VideoDerived(_Strict):
    engagement_rate: MetricValue | None = Field(
        description="(likes + comments) / views x 100; null when likes are hidden. Display only: not a sort"
    )
    views_per_hour_lifetime: MetricValue | None = Field(
        description="views / hours since publication; null without a valid publication date. Display only"
    )


class CreatorRef(_Strict):
    id: str
    platform: PlatformName
    name: str | None
    handle: str | None
    url: str | None
    followers: MetricValue | None = Field(description="null when hidden or not reported")
    content_count: MetricValue | None


class Video(_Strict):
    id: str
    platform: PlatformName
    url: str
    title: str | None
    thumbnail_url: str | None = Field(description="the platform's own image URL; ViralTrack stores no image")
    published_at: datetime | None
    duration_seconds: int | None
    content_type: Literal["video", "short", "unknown"]
    category: str | None
    language: str | None
    region: str | None
    creator: CreatorRef
    metrics: VideoMetrics
    derived: VideoDerived
    origin: OriginName
    retrieved_at: datetime | None = Field(description="when ViralTrack read the item from its provider")


class PageMeta(_Strict):
    platform: PlatformName
    sort: Literal["views", "published_at", "relevance"] | None = Field(
        description="the order actually applied: views or published_at when browsing; relevance for topic "
        "search (the data source ranks the collected videos by how closely they match the text); null when "
        "no single order applies"
    )
    page: int
    page_size: int
    returned: int
    has_more: bool | None = Field(description="null when it cannot be known (the 1000-item window is full)")
    total: int | None = Field(
        description="items matching the filters as the provider reports; null if unknown"
    )
    data_origin: OriginName = Field(description="what the provider's corpus contains")
    demo: bool = Field(description="true when the data is synthetic and must be labelled DEMO")
    notes: list[str] = Field(description="caveats the provider attached, e.g. dropped duplicates")


class Page(_Strict, Generic[T]):
    data: list[T]
    meta: PageMeta


class CreatorSummary(_Strict):
    creator: CreatorRef
    videos_in_result: int = Field(description="videos of this creator among the discovered videos considered")


class CreatorDetail(_Strict):
    creator: CreatorRef
    origin: OriginName
    demo: bool
    videos: None = Field(
        default=None, description="not available: the provider has no per-creator video list"
    )
    notes: list[str]


class Item(_Strict, Generic[T]):
    data: T


class CapabilityOut(_Strict):
    name: str
    supported: bool
    description: str


class FilterOut(_Strict):
    name: str
    type: str
    description: str
    values: list[str] | None = None
    default: str | int | None = None
    minimum: int | None = None
    maximum: int | None = None
    applies_to: list[str]


class SortOut(_Strict):
    name: str
    available: bool
    applies_to: Literal["browse", "topic_search"] = Field(
        description="browse: chosen with the sort parameter; topic_search: applied automatically to text "
        "search"
    )
    reason: str | None = None
    description: str | None = None


class MetricOut(_Strict):
    name: str
    kind: Literal["raw", "derived"]
    sortable: bool
    description: str


class PlatformOut(_Strict):
    platform: PlatformName
    available: bool
    reason: str | None
    data_origin: OriginName | None
    capabilities: list[CapabilityOut]


class CapabilitiesOut(_Strict):
    api_version: Literal["v1"]
    platforms: list[PlatformOut]
    filters: list[FilterOut]
    sorts: list[SortOut]
    metrics: list[MetricOut]
    page_size_max: int
    result_window_max: int


class CheckOut(_Strict):
    status: Literal["ok", "unavailable", "not_configured"]
    required: bool


class HealthOut(_Strict):
    status: Literal["ok", "ready", "not_ready"]
    service: Literal["viraltrack-api"]
    version: str
    checks: dict[str, CheckOut] | None = None


class ErrorDetail(_Strict):
    field: str | None
    message: str


class ErrorBody(_Strict):
    code: str
    message: str
    details: list[ErrorDetail] = []


class ErrorOut(_Strict):
    error: ErrorBody
