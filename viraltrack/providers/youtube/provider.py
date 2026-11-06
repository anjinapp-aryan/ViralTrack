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

# A period: `all`, or a whole number of hours or days from 1 to 9999, lowercase, no leading zero. The
# foundation would also accept uppercase, zero, aliases and `m` (30 days); none of that is accepted here.
_PERIOD = re.compile(r"all|[1-9][0-9]{0,3}[hd]")
# Keyword collection: `all`, or a whole number of hours or days from 1 to 9999, lowercase, no leading zero.
_COLLECT_PERIOD = re.compile(r"all|[1-9][0-9]{0,3}[hd]")
_REGION = re.compile(r"^[A-Z]{2}$")
_LANGUAGE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$")

# ViralTrack sort key -> niche-finder `sort_by` (upstream discovery.SORTS).
# niche-finder's own defaults ("viral", "outlier") rank by RESTRICTED scores, so
# the adapter always sends an explicit sort that the policy has cleared.
#
# `_SORTS` and `_SORTS_NEEDING_APPROVAL` are the ONLY orders ViralTrack will request (D3-07): anything else is
# refused before a request is made, so an unknown name can never reach the foundation, which would otherwise
# fall back to its restricted `viral` order. A new order is added here and nowhere else.
_SORTS = {
    "views": "views",
    "published_at": "published",
}
# Restricted metrics: refused (RestrictedMetric) until the policy carries their approval.
_SORTS_NEEDING_APPROVAL = {
    "acceleration": "acceleration",
    "views_per_follower": "vsr",
    "outlier_score": "outlier",
    "outlier_score_age_adjusted": "outlier_adjusted",
    "viral_score": "viral",
}
_RAW_SORTS = {"views", "published_at"}
# Orders that are refused outright, with the reason. Ordering by a value discloses it, and the foundation's
# order can be wrong even where the value is hidden, so these are not sortable at all (owner decisions, D3).
_REFUSED_SORTS = {
    "views_per_hour_24h": "the foundation reports no snapshot time, so the recency of the rate is unknown",
    "views_gained_24h": "the foundation reports no snapshot time, so the recency of the rate is unknown",
    "views_per_hour_lifetime": "the foundation ranks an undated video by a fabricated rate (age 0 h) and "
                               "places it first; hiding the value does not remove it from the ordering",
    "engagement_rate": "the foundation counts a hidden like count as zero when it orders by this rate, so a "
                       "video with hidden likes is placed by an understated value that ViralTrack omits",
}
# The most subscribers a discovery query may allow a channel to have: a bounded limit, never "no limit".
MAX_CREATOR_FOLLOWERS = 1_000_000

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
        True, "Duration filter on raw metadata (<= 180 s inclusive; zero, missing or invalid duration is "
              "not short), applied by ViralTrack. Not YouTube's Shorts classification; the 'short' label "
              "itself is RESTRICTED (the API has no Shorts flag)"),
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
    if not isinstance(period, str) or not _PERIOD.fullmatch(period):
        raise ValueError("period must be 'all' or a whole number of hours or days from 1 to 9999, "
                         f"lowercase, such as 24h or 7d, got {period!r}")
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


# The foundation's Shorts filters are never used: it decides "short" from a stored `is_short` flag before the
# duration, and the owner-approved `short_form` policy is a duration test (<= 180 s inclusive, unknown is not
# short). Both are sent as false explicitly (its /api/viral default would exclude Shorts), and ViralTrack
# applies the filter itself on `lengthSeconds`.
_NO_UPSTREAM_SHORTS_FILTER = {"only_shorts": "false", "exclude_shorts": "false"}
# With `short_form` set the foundation is asked for this many candidates, in the requested order, so that the
# duration filter has enough to choose `limit` items from; the foundation has no upper cap on `limit`.
_SHORT_FORM_FETCH_LIMIT = 1000


def _short_form_limit(query) -> tuple[int, int]:
    """(limit to send, limit to return), validated before any request. There is no pagination: one page of
    1 to 1000 items (the foundation has no offset and no cap; 1000 is ViralTrack's own bound)."""
    wanted = query.limit
    if isinstance(wanted, bool) or not isinstance(wanted, int) or not 1 <= wanted <= _SHORT_FORM_FETCH_LIMIT:
        raise ValueError(f"limit must be a whole number from 1 to {_SHORT_FORM_FETCH_LIMIT}, got {wanted!r}")
    if query.short_form is None:
        return wanted, wanted
    if not isinstance(query.short_form, bool):
        raise ValueError(f"short_form must be True, False or None, got {query.short_form!r}")
    return max(wanted, _SHORT_FORM_FETCH_LIMIT), wanted


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
        if not isinstance(key, str):
            raise ValueError(f"sort must be text, got {type(key).__name__}")
        upstream = _SORTS.get(key) or _SORTS_NEEDING_APPROVAL.get(key)
        if upstream is None:
            if key in _REFUSED_SORTS:
                raise ValueError(f"sort {key!r} is not available: {_REFUSED_SORTS[key]}")
            raise ValueError(f"unknown sort {key!r}; use one of {', '.join(_SORTS)}")
        if key not in _RAW_SORTS:
            # ordering by a value discloses it, so it needs the same clearance as showing it
            self.metric_policy.require(key)
        return upstream

    def _page(self, body: dict, short_form: bool | None = None, limit: int | None = None) -> ContentPage:
        results = body.get("results")
        if not isinstance(results, list):
            raise ProviderError(PROVIDER_ID, "response has no results list")
        ctx = self._ctx()
        # D3-02: an entry that is not a valid video object fails the whole response (the same contract as an
        # item without ids); nothing is dropped silently and nothing malformed becomes a default.
        mapped = []
        for index, entry in enumerate(results):
            try:
                mapped.append(mapping.map_video(entry, ctx))
            except ProviderError as exc:
                raise ProviderError(PROVIDER_ID, f"results[{index}] is invalid: {exc.args[-1]}") from exc
        items, notes = _first_of_each(mapped)
        hint = body.get("hint")
        if isinstance(hint, str) and hint and not mapping.mentions_restricted_metric(hint):
            notes = (hint, *notes)
        funnel, funnel_note = mapping.map_funnel(body.get("funnel"))
        if funnel_note:
            notes += (funnel_note,)
        total = mapping.count(body.get("matched"))
        if short_form is not None:
            items = tuple(c for c in items if mapping.is_short_form(c.duration_seconds) is short_form)[:limit]
            total = None    # the foundation's total counts videos of every duration
            notes += (f"short_form is a duration filter (<= {mapping.SHORT_FORM_MAX_SECONDS} s, a video with "
                      "no known duration is not short) applied by ViralTrack after the foundation's funnel, "
                      "which therefore counts videos of every duration",)
            if len(results) >= _SHORT_FORM_FETCH_LIMIT:
                notes += (f"the filter saw only the first {_SHORT_FORM_FETCH_LIMIT} candidates",)
        return ContentPage(items=items, total=total, notes=notes, funnel=funnel)

    def discover_content(self, query: DiscoveryQuery) -> ContentPage:
        # Both thresholds are always sent. The foundation applies max_subscribers=10,000 and min_views=10,000
        # to any request that omits them (and the HTTP client drops None), so "unset" is made explicit here.
        followers = _bounded_followers(query.max_creator_followers)
        min_views = _min_views(query.min_views)
        fetch, wanted = _short_form_limit(query)
        region = query.region
        if region is not None and (not isinstance(region, str) or not _REGION.fullmatch(region)):
            raise ValueError(f"region must be an ISO 3166-1 alpha-2 code like US, got {region!r}")
        params = {
            "period": _check_period(query.period),
            "sort_by": self._sort(query.sort),
            "limit": fetch,
            "region": query.region,
            "niche": query.niche,
            "max_subscribers": followers,
            "min_views": min_views,
            # niche-finder filters by views per subscriber >= 1.0 unless told otherwise;
            # that metric is RESTRICTED, so it must not shape the result set either.
            "min_views_per_subscriber": 0,
            **_NO_UPSTREAM_SHORTS_FILTER,
        }
        return self._page(self._client.get("/api/viral", params), query.short_form, wanted)

    def search_content(self, query: SearchQuery) -> ContentPage:
        fetch, wanted = _short_form_limit(query)
        params = {
            "query": query.text,
            "period": _check_period(query.period),
            "sort_by": self._sort(query.sort),
            "limit": fetch,
            "niche": query.niche,
            **_NO_UPSTREAM_SHORTS_FILTER,
        }
        return self._page(self._client.get("/api/search", params), query.short_form, wanted)

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


def _bounded_followers(value: int | None) -> int:
    """The subscriber ceiling to send: unset is the approved maximum (a bounded limit, never "no limit");
    a given value must be a whole number from 0 to that maximum. 0 keeps only channels with 0 or hidden
    subscribers."""
    if value is None:
        return MAX_CREATOR_FOLLOWERS
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_CREATOR_FOLLOWERS:
        raise ValueError(f"max_creator_followers must be a whole number from 0 to "
                         f"{MAX_CREATOR_FOLLOWERS:,} (a bounded limit), got {value!r}")
    return value


def _min_views(value: int | None) -> int:
    """The minimum views to send: unset is 0, which the foundation treats as "no views filter"."""
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"min_views must be a whole number of 0 or more, got {value!r}")
    return value


def _first_of_each(contents: list) -> tuple[tuple, tuple[str, ...]]:
    """One item per video id, in the foundation's order: the first occurrence wins (that is its rank) and
    later ones are dropped whole, never merged. Only the canonical id is compared. A note says how many were
    dropped and how many differed from the first, so a collapse is never silent."""
    first: dict = {}
    dropped = different = 0
    for content in contents:
        kept = first.get(content.content_id)
        if kept is None:
            first[content.content_id] = content
            continue
        dropped += 1
        different += content != kept
    notes = ()
    if dropped:
        notes = (f"{dropped} duplicate video id entr{'y' if dropped == 1 else 'ies'} dropped "
                 f"({different} with different data); the first occurrence of each id was kept",)
    return tuple(first.values()), notes


def _ref(value: str) -> str:
    """A channel reference or search text sent in a JSON body."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must not be empty")
    value = value.strip()
    if len(value) > 200:
        raise ValueError("must be at most 200 characters")
    return value


__all__ = ["CAPABILITIES", "RestrictedMetric", "YouTubeProvider"]
