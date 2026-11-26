"""The AI content taxonomy and the records the classifier produces. Platform-neutral."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AIStatus(str, Enum):
    CONFIRMED_AI = "CONFIRMED_AI"   # the platform's disclosure flag, or the creator states it and names how
    LIKELY_AI = "LIKELY_AI"         # a creator statement alone, or a named generation tool, or several labels
    POSSIBLY_AI = "POSSIBLY_AI"     # one weak label, or AI tools named in what may be a video about them
    NOT_AI = "NOT_AI"               # the creator states that no AI was used
    UNKNOWN = "UNKNOWN"             # no usable evidence, or evidence that contradicts itself


# Statuses the AI views show by default. POSSIBLY_AI is opt-in: one weak label is not enough.
DEFAULT_AI_STATUSES = (AIStatus.CONFIRMED_AI, AIStatus.LIKELY_AI)
AI_STATUSES = (AIStatus.CONFIRMED_AI, AIStatus.LIKELY_AI, AIStatus.POSSIBLY_AI)


class Confidence(str, Enum):
    """A label, not a probability: the classifier has no calibrated model behind it."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ContentCategory(str, Enum):
    AI_MUSIC_VIDEO = "AI_MUSIC_VIDEO"
    AI_MUSIC_AUDIO = "AI_MUSIC_AUDIO"
    AI_VIDEO_WITH_MUSIC = "AI_VIDEO_WITH_MUSIC"
    AI_NORMAL_VIDEO = "AI_NORMAL_VIDEO"
    NORMAL_NON_AI = "NORMAL_NON_AI"
    UNKNOWN = "UNKNOWN"


AI_CATEGORIES = (
    ContentCategory.AI_MUSIC_VIDEO,
    ContentCategory.AI_MUSIC_AUDIO,
    ContentCategory.AI_VIDEO_WITH_MUSIC,
    ContentCategory.AI_NORMAL_VIDEO,
)


class FormatType(str, Enum):
    """A ViralTrack duration tag, not the platform's own Shorts classification (which is not available)."""
    SHORT_FORM = "short_form"   # known length of 1 to 180 s
    LONG_FORM = "long_form"     # known length above 180 s
    LIVE = "live"               # the platform reports a live or upcoming broadcast
    UNKNOWN = "unknown"         # no usable length


@dataclass(frozen=True)
class ContentSignals:
    """Metadata a provider holds about one item beyond the discovery record. None = not reported."""
    found: bool
    tags: tuple[str, ...] = ()                 # the creator's own tags
    synthetic_disclosure: bool | None = None   # platform's altered/synthetic-content flag; None = absent
    creator_country: str | None = None         # ISO 3166-1 alpha-2 the creator declared on the channel
    live_status: str | None = None             # "live", "upcoming", "none" as the platform reports it


@dataclass(frozen=True)
class CountryDimensions:
    """Kept apart on purpose: where it was found, where the creator says they are, and the language."""
    discovery_countries: tuple[str, ...] = ()  # markets of ViralTrack's own regional collections
    discovery_source: str | None = None
    creator_country: str | None = None
    creator_country_source: str | None = None
    creator_country_confidence: Confidence = Confidence.NONE
    language_code: str | None = None
    language_source: str | None = None


@dataclass(frozen=True)
class FormatClassification:
    format_type: FormatType
    format_confidence: Confidence
    reason: str


@dataclass(frozen=True)
class Classification:
    status: AIStatus
    confidence: Confidence
    category: ContentCategory
    reason: str
    category_reason: str
    evidence_sources: tuple[str, ...]
    evidence: tuple[str, ...]
    format: FormatClassification
    classifier_version: str
    classified_at: datetime
    excluded_reason: str | None = None          # set when the item is left out of the AI views (Gaming)
    matched_terms: tuple[str, ...] = field(default_factory=tuple)
