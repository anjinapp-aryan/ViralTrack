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
        default=None, description="always null here; a creator's videos are listed by /creators/{id}/videos"
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


# ---- AI content intelligence (read-only, computed at request time, nothing stored) ----

AIStatusName = Literal["CONFIRMED_AI", "LIKELY_AI", "POSSIBLY_AI", "NOT_AI", "UNKNOWN"]
CategoryName = Literal[
    "AI_MUSIC_VIDEO", "AI_MUSIC_AUDIO", "AI_VIDEO_WITH_MUSIC", "AI_NORMAL_VIDEO", "NORMAL_NON_AI", "UNKNOWN"
]
FormatName = Literal["short_form", "long_form", "live", "unknown"]
ConfidenceName = Literal["high", "medium", "low", "none"]


class AIClassificationOut(_Strict):
    status: AIStatusName
    confidence: ConfidenceName = Field(description="a label, not a probability; no calibrated model is used")
    category: CategoryName
    reason: str = Field(description="why this status, in words")
    category_reason: str
    evidence_sources: list[str] = Field(
        description="platform_disclosure, title, creator_tags, platform_category"
    )
    evidence: list[str] = Field(description="each piece of evidence found, in words")
    classifier_version: str
    classified_at: datetime


class FormatOut(_Strict):
    format_type: FormatName = Field(
        description="a ViralTrack duration tag (short_form: 1 to 180 s), not the platform's Shorts flag"
    )
    format_confidence: ConfidenceName
    reason: str
    duration_seconds: int | None


class CountryOut(_Strict):
    discovery_countries: list[str] = Field(
        description="markets of ViralTrack's own regional collections that found the item; empty when none"
    )
    discovery_source: str | None
    creator_country: str | None = Field(description="the country the creator declared on the channel")
    creator_country_source: str | None
    creator_country_confidence: ConfidenceName = Field(
        description="medium: self-declared and unverified; none: not declared"
    )
    language_code: str | None
    language_source: str | None = Field(
        description="the data source stores the declared audio or metadata language, else its own text "
        "detection, without saying which"
    )


class AIVideo(_Strict):
    video: Video
    classification: AIClassificationOut
    format: FormatOut
    country: CountryOut


class Count(_Strict):
    key: str
    count: int


class CorpusMeta(_Strict):
    platform: PlatformName
    data_origin: OriginName
    demo: bool
    period: str
    candidates_examined: int = Field(description="collected items read for this answer")
    candidate_limit: int
    candidate_limit_reached: bool = Field(description="true when more items may exist than were examined")
    excluded_gaming: int = Field(description="items left out because they are Gaming content")
    signals_missing: int = Field(description="items whose stored tags and disclosure could not be read")
    collected_from: datetime | None = Field(description="earliest time the data source first stored an item")
    collected_to: datetime | None = Field(description="latest time the data source first stored an item")
    classifier_version: str
    notes: list[str]


class AIPageMeta(CorpusMeta):
    sort: Literal["views", "published_at"]
    page: int
    page_size: int
    returned: int
    total: int = Field(description="items matching every filter among those examined")
    has_more: bool


class AIPage(_Strict):
    data: list[AIVideo]
    meta: AIPageMeta


class AISummary(_Strict):
    meta: CorpusMeta
    matching: int = Field(description="items matching every filter")
    by_status: list[Count] = Field(description="all examined items except excluded ones, by AI status")
    by_category: list[Count]
    by_format: list[Count]
    by_confidence: list[Count]
    by_creator_country: list[Count]
    by_discovery_country: list[Count]
    by_language: list[Count]
    recent: list[AIVideo] = Field(description="the most recently published matching items")


class CountryRow(_Strict):
    country: str = Field(description="ISO 3166-1 alpha-2 code, or 'unknown'")
    items: int
    by_category: list[Count]
    by_format: list[Count]
    by_language: list[Count]
    by_published_day: list[Count]


class AICountries(_Strict):
    meta: CorpusMeta
    basis: Literal["creator", "discovery"]
    data: list[CountryRow]


class Theme(_Strict):
    term: str
    items: int = Field(description="supporting items that use the term")


class EvidenceItem(_Strict):
    id: str
    url: str
    title: str | None
    creator_name: str | None
    published_at: datetime | None
    views: MetricValue | None
    status: AIStatusName
    category: CategoryName


class CreativeBrief(_Strict):
    opportunity_title: str
    country: str | None
    country_basis: Literal["creator", "discovery"]
    language_code: str | None
    category: CategoryName
    format_type: FormatName
    audience_hypothesis: str
    theme: str
    original_creative_angle: str
    suggested_duration: str
    hook_concept: str
    story_outline: list[str]
    music_direction: str | None
    visual_direction: str
    platform_recommendations: list[str]
    rights_checklist: list[str]
    generated_by: Literal["template"]
    note: str


class Opportunity(_Strict):
    key: str
    category: CategoryName
    format_type: FormatName
    language_code: str | None
    country: str | None
    country_basis: Literal["creator", "discovery"]
    item_count: int = Field(description="collected items that support it; the only ordering input")
    newest_published_at: datetime | None
    themes: list[Theme]
    summary: str
    evidence: list[EvidenceItem]
    brief: CreativeBrief


class AIOpportunities(_Strict):
    meta: CorpusMeta
    basis: Literal["creator", "discovery"]
    min_items: int
    data: list[Opportunity]
