"""YouTube provider: adapter over the niche-finder foundation."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote

from viraltrack.config import YouTubeProviderSettings
from viraltrack.domain import (
    Capability,
    CapabilityInfo,
    ContentPage,
    Creator,
    Platform,
    PlatformCapabilities,
    ProviderError,
    RestrictedMetric,
)
from viraltrack.providers.base import (
    CreatorSnapshot,
    DiscoveryQuery,
    PlatformProvider,
    SearchQuery,
)
from viraltrack.providers.youtube import mapping
from viraltrack.providers.youtube.client import PROVIDER_ID, FoundationClient
from viraltrack.providers.youtube.metric_policy import youtube_metric_policy

_PERIOD = re.compile(r"^(all|\d{1,4}[hd])$")

# ViralTrack sort key -> niche-finder `sort_by` (upstream discovery.SORTS).
# niche-finder's own defaults ("viral", "outlier") rank by RESTRICTED scores, so
# the adapter always sends an explicit sort that the policy has cleared.
_SORTS = {
    "views": "views",
    "published_at": "published",
    "views_per_hour_24h": "vph",
    "views_per_hour_lifetime": "vph_lifetime",
    "views_gained_24h": "velocity",
    "engagement_rate": "engagement",
    "acceleration": "acceleration",
    "views_per_follower": "vsr",
    "outlier_score": "outlier",
    "outlier_score_age_adjusted": "outlier_adjusted",
    "viral_score": "viral",
}
_RAW_SORTS = {"views", "published_at"}

CAPABILITIES = PlatformCapabilities({
    Capability.DISCOVER_CONTENT: CapabilityInfo(
        True, "Videos from small channels with high views per follower within the collected "
              "corpus (niche-finder /api/viral); not all of YouTube"),
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
        True, "Filter by duration <= 180 s; the 'short' label itself is RESTRICTED "
              "(the API has no Shorts flag)"),
    Capability.ENGAGEMENT_METRICS: CapabilityInfo(True, "likeCount, commentCount"),
    Capability.HASHTAGS: CapabilityInfo(False, "not exposed by the foundation's read API"),
    Capability.AUDIO: CapabilityInfo(False, "no YouTube API for trending audio"),
    Capability.DERIVED_VELOCITY: CapabilityInfo(
        True, "Views per hour / gained from niche-finder snapshots (simple arithmetic), "
              "passed through as DERIVED"),
})


def _check_period(period: str) -> str:
    if not _PERIOD.match(period):
        raise ValueError(f"period must look like 24h, 7d or all, got {period!r}")
    return period


def _path_id(value: str) -> str:
    """An id placed in a URL path: non-empty and fully percent-encoded (no '/', '..')."""
    if not value or not value.strip():
        raise ValueError("id must not be empty")
    return quote(value, safe="")


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
        self._origin = mapping.ORIGINS[settings.data_origin]
        self.metric_policy = youtube_metric_policy(settings.approvals)

    def capabilities(self) -> PlatformCapabilities:
        return CAPABILITIES

    def close(self) -> None:
        self._client.close()

    def _ctx(self) -> mapping.MappingContext:
        return mapping.MappingContext(origin=self._origin, policy=self.metric_policy,
                                      retrieved_at=self._clock())

    def _sort(self, key: str) -> str:
        upstream = _SORTS.get(key)
        if upstream is None:
            raise ValueError(f"unknown sort {key!r}; use one of {', '.join(_SORTS)}")
        if key not in _RAW_SORTS:
            # ordering by a value discloses it, so it needs the same clearance as showing it
            self.metric_policy.require(key)
        return upstream

    def _page(self, body: dict) -> ContentPage:
        results = body.get("results")
        if not isinstance(results, list):
            raise ProviderError(PROVIDER_ID, "response has no results list")
        ctx = self._ctx()
        items = tuple(mapping.map_video(r, ctx) for r in results if isinstance(r, dict))
        notes = tuple(n for n in (body.get("hint"),) if isinstance(n, str) and n)
        total = body.get("matched")
        return ContentPage(items=items, total=total if isinstance(total, int) else None,
                           notes=notes)

    def discover_content(self, query: DiscoveryQuery) -> ContentPage:
        params = {
            "period": _check_period(query.period),
            "sort_by": self._sort(query.sort),
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
            "sort_by": self._sort(query.sort),
            "limit": query.limit,
            "niche": query.niche,
            **_shorts_params(query.short_form),
        }
        return self._page(self._client.get("/api/search", params))

    def get_creator(self, creator_id: str) -> Creator:
        return mapping.map_channel(self._client.get(f"/api/channels/{_path_id(creator_id)}"), self._ctx())

    def get_creator_history(self, creator_id: str) -> list[CreatorSnapshot]:
        body = self._client.get(f"/api/channels/{_path_id(creator_id)}/history")
        points = body.get("points")
        if not isinstance(points, list):
            raise ProviderError(PROVIDER_ID, "history response has no points list")
        ctx, out = self._ctx(), []
        for p in points:
            mapped = mapping.map_channel_point(p, ctx) if isinstance(p, dict) else None
            if mapped:
                out.append(CreatorSnapshot(captured_at=mapped[0], metrics=mapped[1]))
        return out


__all__ = ["CAPABILITIES", "RestrictedMetric", "YouTubeProvider"]
