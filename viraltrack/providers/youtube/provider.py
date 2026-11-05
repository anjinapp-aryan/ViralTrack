"""YouTube provider: adapter over the niche-finder foundation."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from viraltrack.config import YouTubeProviderSettings
from viraltrack.domain import (
    Capability,
    CapabilityInfo,
    ContentPage,
    Creator,
    IngestionDisabled,
    Platform,
    PlatformCapabilities,
    ProviderCredentialsMissing,
    ProviderError,
    QuotaExhausted,
    RateLimited,
    RestrictedMetric,
)
from viraltrack.providers.base import (
    CreatorSnapshot,
    DiscoveryQuery,
    IngestionResult,
    PlatformProvider,
    QuotaStatus,
    SearchQuery,
)
from viraltrack.providers.youtube import ingestion, mapping
from viraltrack.providers.youtube.client import PROVIDER_ID, FoundationClient
from viraltrack.providers.youtube.metric_policy import youtube_metric_policy

_PERIOD = re.compile(r"^(all|\d{1,4}[hd])$")
# Keyword collection: `all`, or a whole number of hours or days from 1 to 9999, lowercase, no leading zero.
_COLLECT_PERIOD = re.compile(r"all|[1-9][0-9]{0,3}[hd]")
_REGION = re.compile(r"^[A-Z]{2}$")
_LANGUAGE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$")

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
        True, "Videos within the collected corpus filtered by raw values (period, channel "
              "subscribers, views, duration) via niche-finder /api/viral; not all of YouTube"),
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
    Capability.COLLECT_CREATOR: CapabilityInfo(
        True, "Internal only. niche-finder POST /api/collect/channel (uploads playlist, ~1 unit "
              "per 50 videos); needs VT_YOUTUBE_INGESTION_ENABLED=true and the foundation's key"),
    Capability.COLLECT_QUERY: CapabilityInfo(
        True, "Internal only. niche-finder POST /api/collect/niche (search.list, 100 calls/day "
              "bucket); needs VT_YOUTUBE_INGESTION_ENABLED=true and the foundation's key"),
    Capability.REFRESH_STATS: CapabilityInfo(
        True, "Internal only. niche-finder POST /api/refresh; needs VT_YOUTUBE_INGESTION_ENABLED=true"),
    Capability.INGESTION_STATUS: CapabilityInfo(
        True, "Internal only. Quota left today as niche-finder GET /api/health reports it"),
    Capability.DERIVED_VELOCITY: CapabilityInfo(
        True, "Views per hour from niche-finder snapshots (simple arithmetic), passed through "
              "as DERIVED; acceleration is RESTRICTED"),
})


def _check_period(period: str) -> str:
    if not _PERIOD.match(period):
        raise ValueError(f"period must look like 24h, 7d or all, got {period!r}")
    return period


def _check_collect_period(period: str | None) -> str | None:
    """The `period` to send with a keyword collection, or None to send none.

    None and `all` both mean "no publication limit" and send nothing, so the request body is the one
    ViralTrack always sent. Anything else must be exactly `N` + `h` or `d`, N from 1 to 9999. The foundation
    would read an empty string as "no limit", accept `0h` and uppercase, and give `m` the meaning of 30 days;
    none of that is accepted here, and nothing is normalised.
    """
    if period is None:
        return None
    if not isinstance(period, str) or not _COLLECT_PERIOD.fullmatch(period):
        raise ValueError("period must be 'all' or a whole number of hours or days from 1 to 9999, "
                         f"lowercase, such as 24h or 7d, got {period!r}")
    return None if period == "all" else period


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
                                        settings.timeout_seconds, http_client=http_client,
                                        collect_timeout_seconds=settings.ingestion.collect_timeout_seconds)
        self._clock = clock
        self._origin = mapping.ORIGINS[settings.data_origin]
        self.metric_policy = youtube_metric_policy(settings.approvals)
        self._ingestion = settings.ingestion
        self._cooldown_until: datetime | None = None

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
            # niche-finder filters by views per subscriber >= 1.0 unless told otherwise;
            # that metric is RESTRICTED, so it must not shape the result set either.
            "min_views_per_subscriber": 0,
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

    # ingestion (internal only; spends YouTube quota through the foundation) ----

    def ingestion_status(self) -> QuotaStatus:
        self._require_ingestion()
        return ingestion.quota_status(self._client.get("/api/health"), self._clock())

    def collect_creator(self, creator_ref: str, max_items: int | None = None) -> IngestionResult:
        self._require_ingestion()
        ref = _ref(creator_ref)
        body = {"channel": ref, "max_videos": self._cap(max_items, "max_items")}
        self._preflight(search_calls=0)
        answer = self._post("/api/collect/channel", body)
        return ingestion.collect_result("collect_creator", answer, self._clock())

    def collect_query(self, text: str, pages: int = 1, region: str | None = None,
                      language: str | None = None, period: str | None = None) -> IngestionResult:
        self._require_ingestion()
        query = _ref(text)
        pages = self._cap(pages, "max_search_pages")
        period = _check_collect_period(period)      # before any request, the health check included
        if region is not None and not _REGION.match(region):
            raise ValueError(f"region must be an ISO 3166-1 alpha-2 code like US, got {region!r}")
        if language is not None and not _LANGUAGE.match(language):
            raise ValueError(f"language must be a code like en or pt-BR, got {language!r}")
        body = {"query": query, "pages": pages, "region": region, "language": language, "period": period}
        self._preflight(search_calls=pages)
        answer = self._post("/api/collect/niche", body)
        return ingestion.collect_result("collect_query", answer, self._clock())

    def refresh_stats(self, period: str = "7d", limit: int | None = None) -> IngestionResult:
        self._require_ingestion()
        body = {"scope": "recent", "period": _check_period(period),
                "limit": self._cap(limit, "max_items")}
        self._preflight(search_calls=0)
        return ingestion.refresh_result(self._post("/api/refresh", body), self._clock())

    def _require_ingestion(self) -> None:
        """First check of every ingestion call: nothing is sent while disabled."""
        if not self._ingestion.enabled:
            raise IngestionDisabled(PROVIDER_ID, "VT_YOUTUBE_INGESTION_ENABLED")

    def _cap(self, value: int | None, setting: str) -> int:
        cap = getattr(self._ingestion, setting)
        if value is None:
            return cap
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= cap:
            raise ValueError(f"must be between 1 and {cap} ({setting}), got {value!r}")
        return value

    def _preflight(self, search_calls: int) -> None:
        """Cooldown, credentials and quota floor, before anything that spends quota."""
        now = self._clock()
        if self._cooldown_until is not None and now < self._cooldown_until:
            wait = int((self._cooldown_until - now).total_seconds()) + 1
            raise RateLimited(PROVIDER_ID, "the foundation asked to wait; cooldown still active",
                              429, retry_after=wait)
        status = ingestion.quota_status(self._client.get("/api/health"), now)
        if not status.has_credentials:
            raise ProviderCredentialsMissing(
                PROVIDER_ID, "the foundation has no YOUTUBE_API_KEY configured")
        if status.units_left < self._ingestion.min_units_left:
            raise QuotaExhausted(PROVIDER_ID, f"{status.units_left} units left today, below the "
                                 f"floor of {self._ingestion.min_units_left} "
                                 "(VT_YOUTUBE_QUOTA_FLOOR_UNITS)")
        if search_calls and (status.search_calls_left
                             < search_calls + self._ingestion.min_search_calls_left):
            raise QuotaExhausted(PROVIDER_ID, f"{status.search_calls_left} search calls left "
                                 f"today; {search_calls} requested and "
                                 f"{self._ingestion.min_search_calls_left} kept in reserve "
                                 "(VT_YOUTUBE_QUOTA_FLOOR_SEARCH_CALLS)")

    def _post(self, path: str, body: dict) -> dict:
        try:
            return self._client.post(path, body)
        except RateLimited as exc:
            if exc.retry_after:
                self._cooldown_until = self._clock() + timedelta(seconds=exc.retry_after)
            raise


def _ref(value: str) -> str:
    """A channel reference or search text sent in a JSON body."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must not be empty")
    value = value.strip()
    if len(value) > 200:
        raise ValueError("must be at most 200 characters")
    return value


__all__ = ["CAPABILITIES", "RestrictedMetric", "YouTubeProvider"]
