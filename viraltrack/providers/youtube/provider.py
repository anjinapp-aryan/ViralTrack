"""YouTube provider: adapter over the niche-finder foundation."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from viraltrack.config import YouTubeProviderSettings
from viraltrack.domain import (
    Capability,
    CapabilityInfo,
    ContentPage,
    Creator,
    Platform,
    PlatformCapabilities,
    ProviderError,
)
from viraltrack.providers.base import (
    CreatorSnapshot,
    DiscoveryQuery,
    PlatformProvider,
    SearchQuery,
)
from viraltrack.providers.youtube import mapping
from viraltrack.providers.youtube.client import PROVIDER_ID, FoundationClient

_PERIOD = re.compile(r"^(all|\d{1,4}[hd])$")

CAPABILITIES = PlatformCapabilities({
    Capability.DISCOVER_CONTENT: CapabilityInfo(
        True, "Outliers within the collected corpus (niche-finder /api/viral); "
              "coverage = collected niches and tracked channels, not all of YouTube"),
    Capability.SEARCH_CONTENT: CapabilityInfo(
        True, "Search within the collected corpus (niche-finder /api/search); no quota"),
    Capability.GET_CONTENT: CapabilityInfo(
        False, "niche-finder exposes no single-video read endpoint"),
    Capability.GET_CREATOR: CapabilityInfo(
        True, "Channels already collected (niche-finder /api/channels/{id})"),
    Capability.CREATOR_HISTORY: CapabilityInfo(
        True, "Stored channel snapshots; limited by the retention policy"),
    Capability.GLOBAL_TRENDING: CapabilityInfo(
        False, "chart=mostPopular covers only Music, Movies and Gaming since 2025-07-21; "
               "YouTube offers no general trending feed"),
    Capability.SHORT_FORM: CapabilityInfo(
        True, "Heuristic: duration <= 180 s; the API has no Shorts flag"),
    Capability.ENGAGEMENT_METRICS: CapabilityInfo(True, "likeCount, commentCount"),
    Capability.HASHTAGS: CapabilityInfo(False, "not exposed by the foundation's read API"),
    Capability.AUDIO: CapabilityInfo(False, "no YouTube API for trending audio"),
    Capability.DERIVED_VELOCITY: CapabilityInfo(
        True, "Calculated by niche-finder from its own snapshots; passed through as DERIVED"),
})


def _check_period(period: str) -> str:
    if not _PERIOD.match(period):
        raise ValueError(f"period must look like 24h, 7d or all, got {period!r}")
    return period


def _shorts_params(short_form: bool | None) -> dict:
    if short_form is True:
        return {"only_shorts": "true", "exclude_shorts": "false"}
    if short_form is False:
        return {"only_shorts": "false", "exclude_shorts": "true"}
    return {"only_shorts": "false", "exclude_shorts": "false"}


class YouTubeProvider(PlatformProvider):
    provider_id = PROVIDER_ID
    platform = Platform.YOUTUBE

    def __init__(self, settings: YouTubeProviderSettings, http_client=None,
                 clock=lambda: datetime.now(timezone.utc)):
        self._client = FoundationClient(settings.base_url, settings.api_token,
                                        settings.timeout_seconds, http_client=http_client)
        self._clock = clock

    def capabilities(self) -> PlatformCapabilities:
        return CAPABILITIES

    def close(self) -> None:
        self._client.close()

    def _page(self, body: dict) -> ContentPage:
        results = body.get("results")
        if not isinstance(results, list):
            raise ProviderError(PROVIDER_ID, "response has no results list")
        now = self._clock()
        items = tuple(mapping.map_video(r, now) for r in results if isinstance(r, dict))
        notes = tuple(n for n in (body.get("hint"),) if isinstance(n, str) and n)
        total = body.get("matched")
        return ContentPage(items=items, total=total if isinstance(total, int) else None,
                           notes=notes)

    def discover_content(self, query: DiscoveryQuery) -> ContentPage:
        params = {
            "period": _check_period(query.period),
            "limit": query.limit,
            "region": query.region,
            "niche": query.niche,
            "max_subscribers": query.max_creator_followers,
            "min_views": query.min_views,
            **_shorts_params(query.short_form),
        }
        return self._page(self._client.get("/api/viral", params))

    def search_content(self, query: SearchQuery) -> ContentPage:
        params = {
            "query": query.text,
            "period": _check_period(query.period),
            "limit": query.limit,
            "niche": query.niche,
            **_shorts_params(query.short_form),
        }
        return self._page(self._client.get("/api/search", params))

    def get_creator(self, creator_id: str) -> Creator:
        return mapping.map_channel(self._client.get(f"/api/channels/{creator_id}"))

    def get_creator_history(self, creator_id: str) -> list[CreatorSnapshot]:
        body = self._client.get(f"/api/channels/{creator_id}/history")
        points = body.get("points")
        if not isinstance(points, list):
            raise ProviderError(PROVIDER_ID, "history response has no points list")
        out = []
        for p in points:
            mapped = mapping.map_channel_point(p) if isinstance(p, dict) else None
            if mapped:
                out.append(CreatorSnapshot(captured_at=mapped[0], metrics=mapped[1]))
        return out
