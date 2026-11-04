"""Ingestion through the foundation's documented collection routes (Phase 2 Batch 2).

The response bodies below are synthetic. Their shapes follow upstream d872014
(`backend/interfaces/http/api.py` health/collect/refresh routes and
`backend/application/collecting.py` return values); the numbers are invented
and no real YouTube data is involved. Every test is offline.
"""
import json
import os
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from viraltrack.config import load_settings
from viraltrack.domain import (
    Capability,
    IngestionDisabled,
    NotFound,
    ProviderAuthFailed,
    ProviderCredentialsMissing,
    ProviderError,
    QuotaExhausted,
    RateLimited,
    UnsupportedCapability,
)
from viraltrack.providers import PlatformProvider
from viraltrack.providers.youtube import YouTubeProvider
from viraltrack.providers.youtube.client import WRITE_ROUTES, FoundationClient

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
ENABLED = {"VT_YOUTUBE_INGESTION_ENABLED": "true"}


def health(has_key=True, units_left=9000, calls_left=90):
    return {"ok": True, "hasApiKey": has_key, "db": {}, "historyAvailable": True,
            "searchQuota": {"callsToday": 100 - calls_left, "dailyLimit": 100,
                            "callsLeft": calls_left},
            "unitQuota": {"unitsToday": 10000 - units_left, "dailyLimit": 10000,
                          "unitsLeft": units_left},
            "maturityCurve": {}}


COLLECT_CHANNEL = {"channelId": "UC0000000000000000000f", "channelTitle": "Synthetic",
                   "videos_found": 120, "videos_stored": 118,
                   "quota": {"search_calls": 0, "search_calls_today": 3,
                             "search_calls_left_today": 97, "units_from_shared_pool": 6,
                             "note": "..."}}
COLLECT_NICHE = {"niche": "cooking", "query": "cooking", "min_upload_date": None,
                 "videos_found": 50, "videos_stored": 50, "channels_stored": 41,
                 "quota": {"search_calls": 1, "search_calls_today": 4,
                           "search_calls_left_today": 96, "units_from_shared_pool": 3,
                           "note": "..."}}
REFRESH = {"videos": {"scope": "recent", "period": "7d", "requested": 200, "refreshed": 198,
                      "failed": 0, "title_or_thumbnail_changes_detected": 2,
                      "gone": {"missing": 2, "confirmed": 0},
                      "quota": {"units_from_shared_pool": 4, "search_calls": 0}},
           "channels": {"refreshed": 12, "gone": {"missing": 0, "confirmed": 0},
                        "quota": {"units_from_shared_pool": 1, "search_calls": 0}}}


class Foundation:
    """Records every request; answers by (method, path)."""

    def __init__(self, routes=None):
        self.routes = {("GET", "/api/health"): (200, health()),
                       ("POST", "/api/collect/channel"): (200, COLLECT_CHANNEL),
                       ("POST", "/api/collect/niche"): (200, COLLECT_NICHE),
                       ("POST", "/api/refresh"): (200, REFRESH), **(routes or {})}
        self.requests: list[httpx.Request] = []

    def __call__(self, request):
        self.requests.append(request)
        status, body, *headers = self.routes.get((request.method, request.url.path),
                                                 (404, {"detail": "no route"}))
        return httpx.Response(status, json=body, headers=headers[0] if headers else None)

    def posts(self):
        return [r for r in self.requests if r.method == "POST"]


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


def make(handler, env=None, clock=None):
    settings = load_settings({"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test",
                              "VT_YOUTUBE_DATA_ORIGIN": "test", **(env or {})})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return YouTubeProvider(settings.youtube, http_client=client, clock=clock or (lambda: NOW))


CALLS = {
    "collect_creator": lambda p: p.collect_creator("@synthetic"),
    "collect_query": lambda p: p.collect_query("cooking"),
    "refresh_stats": lambda p: p.refresh_stats(),
    "ingestion_status": lambda p: p.ingestion_status(),
}


# disabled by default ----------------------------------------------------------

def test_ingestion_is_disabled_by_default():
    assert load_settings({}).youtube.ingestion.enabled is False


@pytest.mark.parametrize("name", sorted(CALLS))
def test_disabled_ingestion_makes_zero_requests(name):
    nf = Foundation()
    with pytest.raises(IngestionDisabled, match="VT_YOUTUBE_INGESTION_ENABLED"):
        CALLS[name](make(nf))
    assert nf.requests == []


def test_disabled_check_comes_before_argument_validation():
    nf = Foundation()
    with pytest.raises(IngestionDisabled):
        make(nf).collect_query("", pages=99)
    assert nf.requests == []


# successful calls -------------------------------------------------------------

def test_collect_creator():
    nf = Foundation()
    res = make(nf, ENABLED).collect_creator(" @synthetic ")
    assert [(r.method, r.url.path) for r in nf.requests] == [
        ("GET", "/api/health"), ("POST", "/api/collect/channel")]
    post = nf.posts()[0]
    assert json.loads(post.content) == {"channel": "@synthetic", "max_videos": 200}
    assert post.headers["X-NF-Client"] == "viraltrack"
    assert post.headers["X-NF-Locale"] == "en"
    assert res.operation == "collect_creator" and res.provider == "youtube"
    assert res.creator_id == "UC0000000000000000000f"
    assert res.counts == {"videos_found": 120, "videos_stored": 118}
    # the foundation's own figures, copied; never computed by ViralTrack
    assert (res.quota_units_reported, res.search_calls_reported) == (6, 0)
    assert res.finished_at == NOW


def test_collect_query():
    nf = Foundation()
    res = make(nf, ENABLED).collect_query("cooking", region="US", language="en")
    assert json.loads(nf.posts()[0].content) == {"query": "cooking", "pages": 1,
                                                 "region": "US", "language": "en"}
    assert res.counts == {"videos_found": 50, "videos_stored": 50, "channels_stored": 41}
    assert (res.quota_units_reported, res.search_calls_reported) == (3, 1)


def test_refresh_stats():
    nf = Foundation()
    res = make(nf, ENABLED).refresh_stats(period="7d")
    assert json.loads(nf.posts()[0].content) == {"scope": "recent", "period": "7d", "limit": 200}
    assert res.counts["videos_refreshed"] == 198
    assert res.counts["videos_gone_missing"] == 2
    assert res.counts["channels_refreshed"] == 12
    assert res.quota_units_reported == 5       # 4 + 1, both reported by the foundation


def test_quota_not_reported_stays_unknown():
    body = {k: v for k, v in COLLECT_CHANNEL.items() if k != "quota"}
    nf = Foundation({("POST", "/api/collect/channel"): (200, body)})
    res = make(nf, ENABLED).collect_creator("@synthetic")
    assert res.quota_units_reported is None and res.search_calls_reported is None


def test_ingestion_status():
    nf = Foundation({("GET", "/api/health"): (200, health(units_left=4321, calls_left=7))})
    status = make(nf, ENABLED).ingestion_status()
    assert (status.units_left, status.unit_limit) == (4321, 10000)
    assert (status.search_calls_left, status.search_call_limit) == (7, 100)
    assert status.has_credentials is True and status.checked_at == NOW
    assert {r.method for r in nf.requests} == {"GET"}


# pre-flight: nothing is spent unless the foundation says it can be -------------

def test_missing_api_key_is_detected_before_any_post():
    nf = Foundation({("GET", "/api/health"): (200, health(has_key=False))})
    with pytest.raises(ProviderCredentialsMissing):
        make(nf, ENABLED).collect_creator("@synthetic")
    assert nf.posts() == []


def test_missing_api_key_reported_by_the_route():
    nf = Foundation({("POST", "/api/collect/niche"): (428, {"detail": "YOUTUBE_API_KEY ..."})})
    with pytest.raises(ProviderCredentialsMissing):
        make(nf, ENABLED).collect_query("cooking")


def test_unit_floor_refuses_before_any_post():
    nf = Foundation({("GET", "/api/health"): (200, health(units_left=999))})
    with pytest.raises(QuotaExhausted, match="VT_YOUTUBE_QUOTA_FLOOR_UNITS"):
        make(nf, ENABLED).refresh_stats()
    assert nf.posts() == []


def test_search_call_floor_counts_the_pages_asked_for():
    env = {**ENABLED, "VT_YOUTUBE_MAX_SEARCH_PAGES": "3"}
    nf = Foundation({("GET", "/api/health"): (200, health(calls_left=12))})
    with pytest.raises(QuotaExhausted, match="SEARCH_CALLS"):
        make(nf, env).collect_query("cooking", pages=3)     # 3 + 10 reserve > 12
    assert nf.posts() == []
    make(nf, env).collect_query("cooking", pages=2)         # 2 + 10 <= 12
    assert len(nf.posts()) == 1


def test_creator_collection_does_not_need_search_calls():
    nf = Foundation({("GET", "/api/health"): (200, health(calls_left=0))})
    make(nf, ENABLED).collect_creator("@synthetic")
    assert len(nf.posts()) == 1


@pytest.mark.parametrize("body", [{"ok": True}, {"ok": True, "hasApiKey": True},
                                  {**health(), "unitQuota": {"unitsLeft": "9000"}}])
def test_unreported_quota_fails_closed(body):
    nf = Foundation({("GET", "/api/health"): (200, body)})
    with pytest.raises(ProviderError, match="did not report its quota"):
        make(nf, ENABLED).collect_creator("@synthetic")
    assert nf.posts() == []


# upstream refusals --------------------------------------------------------------

def test_quota_exhausted_by_the_foundation():
    nf = Foundation({("POST", "/api/collect/channel"):
                     (429, {"error": "QuotaExceeded", "detail": "YouTube API quota exceeded"})})
    with pytest.raises(QuotaExhausted):
        make(nf, ENABLED).collect_creator("@synthetic")


def test_cooldown_is_respected_without_further_requests():
    limited = (429, {"error": "ManualRunLimit", "operation": "refresh", "retryAfter": 120,
                     "detail": "too many manual runs"}, {"Retry-After": "120"})
    nf = Foundation({("POST", "/api/refresh"): limited})
    clock = Clock()
    p = make(nf, ENABLED, clock)
    with pytest.raises(RateLimited) as err:
        p.refresh_stats()
    assert err.value.retry_after == 120
    seen = len(nf.requests)
    clock.now = NOW + timedelta(seconds=60)
    with pytest.raises(RateLimited) as err:
        p.collect_creator("@synthetic")
    assert len(nf.requests) == seen                         # nothing sent during the cooldown
    assert 0 < err.value.retry_after <= 61
    clock.now = NOW + timedelta(seconds=121)
    nf.routes[("POST", "/api/refresh")] = (200, REFRESH)
    p.refresh_stats()
    assert nf.posts()[-1].url.path == "/api/refresh"


@pytest.mark.parametrize("status,body,error", [
    (401, {"detail": "sign in"}, ProviderAuthFailed),
    (403, {"detail": "Forbidden"}, ProviderAuthFailed),
    (403, {"error": "PlanLimit", "limit": "channels", "max": 5, "detail": "plan"}, ProviderError),
    (403, {"error": "ReadOnlyView", "detail": "view as user"}, ProviderError),
    (404, {"detail": "channel not found: @x"}, NotFound),
    (400, {"detail": "field channel required"}, ProviderError),
    (500, {"error": "RuntimeError", "detail": "boom"}, ProviderError),
])
def test_route_errors_are_typed(status, body, error):
    nf = Foundation({("POST", "/api/collect/channel"): (status, body)})
    with pytest.raises(error) as err:
        make(nf, ENABLED).collect_creator("@synthetic")
    if error is ProviderError:
        assert not isinstance(err.value, ProviderAuthFailed)


def test_reads_now_raise_typed_auth_errors_too():
    nf = Foundation({("GET", "/api/health"): (401, {"detail": "sign in"})})
    with pytest.raises(ProviderAuthFailed):
        make(nf, ENABLED).ingestion_status()


# input limits (validated before anything is sent) -------------------------------

@pytest.mark.parametrize("call", [
    lambda p: p.collect_creator("@synthetic", max_items=201),
    lambda p: p.collect_creator("@synthetic", max_items=0),
    lambda p: p.collect_creator("   "),
    lambda p: p.collect_creator("x" * 201),
    lambda p: p.collect_query("cooking", pages=2),
    lambda p: p.collect_query("cooking", region="usa"),
    lambda p: p.collect_query("cooking", language="English"),
    lambda p: p.refresh_stats(period="last week"),
    lambda p: p.refresh_stats(limit=True),
])
def test_invalid_arguments_rejected_before_any_request(call):
    nf = Foundation()
    with pytest.raises(ValueError):
        call(make(nf, ENABLED))
    assert nf.requests == []


# boundary ---------------------------------------------------------------------

def test_client_posts_only_to_documented_collection_routes():
    assert WRITE_ROUTES == {"/api/collect/channel", "/api/collect/niche", "/api/refresh"}
    nf = Foundation()
    client = FoundationClient("http://nf.test", http_client=httpx.Client(
        transport=httpx.MockTransport(nf)))
    for path in ("/api/videos/x/comments", "/api/transcripts/x/save", "/api/channels/track",
                 "/api/collect/trending", "/api/collect/channel/../../x"):
        with pytest.raises(ValueError):
            client.post(path, {})
    assert nf.requests == []


def test_reads_stay_get_only_with_ingestion_enabled():
    from tests.test_youtube_provider import CHANNEL, Recorder
    from viraltrack.providers import DiscoveryQuery, SearchQuery

    rec = Recorder()
    settings = load_settings({"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test",
                              "VT_YOUTUBE_DATA_ORIGIN": "test", **ENABLED})
    p = YouTubeProvider(settings.youtube, http_client=httpx.Client(
        transport=httpx.MockTransport(rec)), clock=lambda: NOW)
    p.discover_content(DiscoveryQuery())
    p.search_content(SearchQuery())
    p.get_creator(CHANNEL)
    p.get_creator_history(CHANNEL)
    assert {r.method for r in rec.requests} == {"GET"}


def test_ingestion_capabilities_declared_and_default_unsupported():
    caps = make(Foundation()).capabilities()
    for cap in (Capability.COLLECT_CREATOR, Capability.COLLECT_QUERY, Capability.REFRESH_STATS,
                Capability.INGESTION_STATUS):
        assert caps.supports(cap) and "Internal only" in caps.note(cap)

    class Bare(PlatformProvider):
        provider_id = "bare"

        def capabilities(self):
            return caps

    for name in CALLS:
        with pytest.raises(UnsupportedCapability):
            CALLS[name](Bare())


def test_settings_describe_ingestion():
    d = load_settings({**ENABLED, "VT_YOUTUBE_QUOTA_FLOOR_UNITS": "250"}).describe()
    assert d["youtube.ingestion.enabled"] is True
    assert d["youtube.ingestion.min_units_left"] == 250


@pytest.mark.parametrize("key,value", [("VT_YOUTUBE_INGESTION_ENABLED", "yes please"),
                                       ("VT_YOUTUBE_MAX_SEARCH_PAGES", "6"),
                                       ("VT_YOUTUBE_MAX_VIDEOS_PER_COLLECT", "501"),
                                       ("VT_YOUTUBE_QUOTA_FLOOR_SEARCH_CALLS", "101")])
def test_ingestion_settings_are_bounded(key, value):
    from viraltrack.domain import ConfigError
    with pytest.raises(ConfigError):
        load_settings({key: value})


# live: the demo foundation has no YouTube key, so nothing may be collected ---------

@pytest.mark.live_foundation
def test_live_foundation_without_key_collects_nothing():
    url = os.environ.get("VT_TEST_FOUNDATION_URL")
    if not url:
        pytest.skip("VT_TEST_FOUNDATION_URL not set")
    settings = load_settings({"VT_YOUTUBE_FOUNDATION_URL": url, "VT_YOUTUBE_DATA_ORIGIN": "demo",
                              **ENABLED})
    p = YouTubeProvider(settings.youtube)
    try:
        status = p.ingestion_status()
        if status.has_credentials:
            pytest.skip("this foundation has a YouTube key; the no-key check does not apply")
        before = httpx.get(f"{url}/api/stats", timeout=20).json()
        for call in (lambda: p.collect_creator("@synthetic"), lambda: p.collect_query("cooking"),
                     lambda: p.refresh_stats()):
            with pytest.raises(ProviderCredentialsMissing):
                call()
        assert httpx.get(f"{url}/api/stats", timeout=20).json() == before
    finally:
        p.close()
