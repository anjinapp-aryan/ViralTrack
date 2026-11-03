"""The provider boundary: the only way ViralTrack code reaches a platform.

A provider declares its capabilities. Every operation it does not support
raises `UnsupportedCapability` (the base class default), so a missing feature
can never be mistaken for an empty result.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from viraltrack.domain import (
    Capability,
    ContentPage,
    Creator,
    Metric,
    Platform,
    PlatformCapabilities,
    UnsupportedCapability,
)


@dataclass(frozen=True)
class DiscoveryQuery:
    """Ranked discovery over what the provider has collected."""
    period: str = "7d"               # e.g. 24h, 7d, 30d
    limit: int = 24
    short_form: bool | None = None   # True = only short-form, False = exclude, None = both
    region: str | None = None
    niche: str | None = None
    max_creator_followers: int | None = None
    min_views: int | None = None
    # ViralTrack metric to order by ("views", "published_at" or a derived metric name).
    # Ordering by a metric the policy does not allow raises RestrictedMetric.
    sort: str = "views"


@dataclass(frozen=True)
class SearchQuery:
    text: str | None = None
    period: str = "all"
    limit: int = 30
    short_form: bool | None = None
    niche: str | None = None
    sort: str = "views"   # ignored by providers that order text searches by relevance


@dataclass(frozen=True)
class CreatorSnapshot:
    captured_at: datetime
    metrics: tuple[Metric, ...]


class PlatformProvider(ABC):
    provider_id: str
    platform: Platform

    @abstractmethod
    def capabilities(self) -> PlatformCapabilities: ...

    def _unsupported(self, capability: Capability):
        raise UnsupportedCapability(self.provider_id, capability,
                                    self.capabilities().note(capability))

    def discover_content(self, query: DiscoveryQuery) -> ContentPage:
        self._unsupported(Capability.DISCOVER_CONTENT)

    def search_content(self, query: SearchQuery) -> ContentPage:
        self._unsupported(Capability.SEARCH_CONTENT)

    def get_content(self, content_id: str):
        self._unsupported(Capability.GET_CONTENT)

    def get_creator(self, creator_id: str) -> Creator:
        self._unsupported(Capability.GET_CREATOR)

    def get_creator_history(self, creator_id: str) -> list[CreatorSnapshot]:
        self._unsupported(Capability.CREATOR_HISTORY)

    def get_trending_content(self, region: str | None = None) -> ContentPage:
        self._unsupported(Capability.GLOBAL_TRENDING)

    def close(self) -> None:
        pass
