"""D5: the ViralTrack HTTP API (viraltrack.api), offline.

Unit tests drive the real `YouTubeProvider` over recorded synthetic foundation responses (the fixtures carry
every restricted field the foundation computes, so a leak would show). Integration tests at the end run the
pinned foundation code on PostgreSQL (VT_TEST_DATABASE_URL + VT_TEST_UPSTREAM_PYTHON) and skip without it.
No test can reach YouTube or spend quota: every transport is a mock or the offline in-process runner.
"""

import json
import logging
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.conftest import ROOT, load_fixture
from viraltrack.api import create_app, guard
from viraltrack.api.settings import load_api_settings
from viraltrack.config import load_settings
from viraltrack.domain import (
    Capability,
    CapabilityInfo,
    ConfigError,
    Content,
    ContentPage,
    ContentType,
    Creator,
    DataOrigin,
    Exposure,
    Metric,
    MetricKind,
    Platform,
    PlatformCapabilities,
    Provenance,
)
from viraltrack.providers.base import PlatformProvider
from viraltrack.providers.youtube import YouTubeProvider
from viraltrack.providers.youtube.metric_policy import RULES

NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
CHANNEL = "UC0000000000000000000f"
ROUTES = {
    "/api/viral": "viral.json",
    "/api/search": "search.json",
    f"/api/channels/{CHANNEL}": "channel.json",
}
HEALTH = {"ok": True, "hasApiKey": False, "db": {"videos": 3}}
ENDPOINTS = [
    "/api/v1/health",
    "/api/v1/health/ready",
    "/api/v1/capabilities",
    "/api/v1/discover?period=all",
    "/api/v1/search?query=ai",
    "/api/v1/creators?period=all",
    f"/api/v1/creators/{CHANNEL}",
]
# every key the foundation fixtures carry that must never appear in an API response
UPSTREAM_ONLY = {
    "acceleration",
    "baselineMedianViews",
    "baselineMedianViewsPeriod",
    "estimatedRpm",
    "estimatedRpmRange",
    "isShort",
    "outlierBand",
    "outlierScore",
    "outlierScoreAgeAdjusted",
    "outlierScoreNexlev",
    "outlierScorePeriod",
    "outlierScoreRolling",
    "projected30dViews",
    "viewsPerSubscriber",
    "viralScore",
    "vph24h",
    "viewsGained24h",
    "snapshots",
    "quotaUsed",
}


class Foundation:
    """Answers like the foundation from recorded fixtures; records every request."""

    def __init__(self, routes=None, health=HEALTH, fail=None):
        self.routes = {**ROUTES, **(routes or {})}
        self.health, self.fail = health, fail
        self.requests: list[httpx.Request] = []

    def __call__(self, request):
        self.requests.append(request)
        if self.fail:
            raise self.fail(f"boom at http://nf.internal.example:8080{request.url.path}", request=request)
        if request.url.path == "/api/health":
            return httpx.Response(200, json=self.health)
        name = self.routes.get(request.url.path)
        if name is None:
            return httpx.Response(404, json={"detail": f"{request.url.path} not here, see /api/admin"})
        body = name if isinstance(name, dict) else load_fixture(name)
        return httpx.Response(200, json=body)

    def last(self, path):
        return next(r for r in reversed(self.requests) if r.url.path == path)


def settings(origin="test", **env):
    return load_settings(
        {"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test", "VT_YOUTUBE_DATA_ORIGIN": origin, **env}
    )


def client(nf=None, origin="test", providers=None, db_check=None, api_env=None):
    s = settings(origin)
    if providers is None:
        nf = nf or Foundation()
        http = httpx.Client(transport=httpx.MockTransport(nf))
        providers = {Platform.YOUTUBE: YouTubeProvider(s.youtube, http_client=http, clock=lambda: NOW)}
    app = create_app(s, load_api_settings(api_env or {}), providers=providers, db_check=db_check)
    return TestClient(app, raise_server_exceptions=False)


def keys(body) -> set[str]:
    if isinstance(body, dict):
        return set(body) | set().union(*(keys(v) for v in body.values()))
    if isinstance(body, list):
        return set().union(*(keys(v) for v in body)) if body else set()
    return set()


# ---- A. endpoints ---------------------------------------------------------------------------------


def test_liveness_checks_no_dependency_and_exposes_no_configuration():
    nf = Foundation()
    r = client(nf).get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "viraltrack-api", "version": "1.0.0", "checks": None}
    assert nf.requests == []
    assert "nf.test" not in r.text


def test_readiness_reports_each_check_without_details():
    r = client(db_check=lambda: True).get("/api/v1/health/ready")
    assert r.status_code == 200 and r.json()["status"] == "ready"
    assert r.json()["checks"] == {
        "youtube": {"status": "ok", "required": True},
        "database": {"status": "ok", "required": True} | {"required": False},
    }


@pytest.mark.parametrize(
    "nf",
    [
        Foundation(health={"ok": False}),
        Foundation(fail=httpx.ConnectError),
        Foundation(fail=httpx.ReadTimeout),
    ],
)
def test_readiness_is_not_ready_when_the_foundation_is_down(nf):
    r = client(nf).get("/api/v1/health/ready")
    assert r.status_code == 503 and r.json()["status"] == "not_ready"
    assert r.json()["checks"]["youtube"]["status"] == "unavailable"
    assert "nf.internal" not in r.text and "boom" not in r.text


def test_an_unconfigured_or_failing_database_is_reported_but_not_required():
    assert client().get("/api/v1/health/ready").json()["checks"]["database"]["status"] == "not_configured"

    def broken():
        raise ConnectionError("password=secret host=db.internal")

    r = client(db_check=broken).get("/api/v1/health/ready")
    assert r.status_code == 200 and r.json()["checks"]["database"]["status"] == "unavailable"
    assert "secret" not in r.text and "db.internal" not in r.text


def test_a_database_that_refuses_connections_is_unavailable():
    from viraltrack.api.app import _database_check, db_check_status

    s = load_settings({"DATABASE_URL": "postgresql://u:p@127.0.0.1:1/x", "DATABASE_CONNECT_TIMEOUT": "2"})
    assert db_check_status(_database_check(s)) == "unavailable"


def test_capabilities_show_youtube_active_and_instagram_tiktok_unavailable():
    body = client().get("/api/v1/capabilities").json()
    platforms = {p["platform"]: p for p in body["platforms"]}
    assert platforms["youtube"]["available"] is True and platforms["youtube"]["data_origin"] == "test"
    for name in ("instagram", "tiktok"):
        assert (
            platforms[name]["available"] is False and "No approved data source" in platforms[name]["reason"]
        )
        assert platforms[name]["capabilities"] == [] and platforms[name]["data_origin"] is None
    caps = {c["name"]: c["supported"] for c in platforms["youtube"]["capabilities"]}
    assert caps["discover_content"] and caps["search_content"] and not caps["global_trending"]
    assert not {
        c.value
        for c in (
            Capability.COLLECT_QUERY,
            Capability.COLLECT_CREATOR,
            Capability.REFRESH_STATS,
            Capability.INGESTION_STATUS,
        )
    } & set(caps)


def test_capabilities_list_only_the_approved_sorts_as_available():
    sorts = client().get("/api/v1/capabilities").json()["sorts"]
    assert [s["name"] for s in sorts if s["available"]] == ["views", "published_at"]
    refused = {s["name"] for s in sorts if not s["available"]}
    assert refused == {"engagement_rate", "views_per_hour_lifetime", "views_per_hour_24h", "views_gained_24h"}
    assert all(s["reason"] for s in sorts if not s["available"])


def test_capabilities_list_only_allowed_metrics_and_only_views_is_sortable():
    metrics = client().get("/api/v1/capabilities").json()["metrics"]
    names = {m["name"] for m in metrics}
    allowed = {r.name for r in RULES if r.exposure is Exposure.ALLOWED}
    assert names == {"views", "likes", "comments", "followers", "content_count"} | {
        "engagement_rate",
        "views_per_hour_lifetime",
    }
    assert {m["name"] for m in metrics if m["kind"] == "derived"} <= allowed
    assert [m["name"] for m in metrics if m["sortable"]] == ["views"]


def test_discover_returns_videos_through_the_provider_with_its_safe_defaults():
    nf = Foundation()
    r = client(nf).get("/api/v1/discover?period=all")
    assert r.status_code == 200
    body = r.json()
    assert [v["id"] for v in body["data"]] == ["bvid008", "avid016", "evid025"]
    sent = nf.last("/api/viral").url.params
    assert sent["sort_by"] == "views" and sent["max_subscribers"] == "1000000" and sent["min_views"] == "0"
    assert sent["min_views_per_subscriber"] == "0" and sent["limit"] == "25"
    assert body["meta"]["sort"] == "views" and body["meta"]["platform"] == "youtube"


def test_discover_sort_published_at_is_sent_as_the_foundation_name():
    nf = Foundation()
    assert client(nf).get("/api/v1/discover?sort=published_at").status_code == 200
    assert nf.last("/api/viral").url.params["sort_by"] == "published"


@pytest.mark.parametrize(
    "size,bound",
    [("up_to_10k", "10000"), ("up_to_100k", "100000"), ("up_to_1m", "1000000"), ("any", "1000000")],
)
def test_creator_size_maps_to_a_bounded_follower_limit(size, bound):
    nf = Foundation()
    client(nf).get(f"/api/v1/discover?creator_size={size}")
    assert nf.last("/api/viral").url.params["max_subscribers"] == bound


def test_discover_with_query_uses_text_search():
    nf = Foundation()
    r = client(nf).get("/api/v1/discover?query=ai&period=30d")
    assert r.status_code == 200
    sent = nf.last("/api/search").url.params
    assert sent["query"] == "ai" and sent["period"] == "30d"


def test_search_requires_a_query_and_uses_the_search_route():
    nf = Foundation()
    c = client(nf)
    assert c.get("/api/v1/search").status_code == 422
    r = c.get("/api/v1/search?query=history")
    assert r.status_code == 200 and len(r.json()["data"]) == 3
    assert nf.last("/api/search").url.params["query"] == "history"


def test_creators_lists_the_distinct_creators_of_the_discovered_videos():
    nf = Foundation()
    body = client(nf).get("/api/v1/creators?period=all").json()
    assert nf.last("/api/viral").url.params["limit"] == "1000"
    ids = [c["creator"]["id"] for c in body["data"]]
    assert len(ids) == len(set(ids))
    assert sum(c["videos_in_result"] for c in body["data"]) == 3
    assert body["meta"]["total"] == len(ids) and body["meta"]["sort"] is None
    assert any("not their whole channel" in n for n in body["meta"]["notes"])


def test_creator_detail_returns_identity_and_says_videos_are_unavailable():
    body = client().get(f"/api/v1/creators/{CHANNEL}").json()["data"]
    assert body["creator"]["id"] == CHANNEL and body["creator"]["platform"] == "youtube"
    assert body["videos"] is None and "not available" in body["notes"][0]
    assert body["creator"]["followers"]["kind"] == "raw"


def test_unknown_creator_is_404_without_the_foundation_message():
    r = client().get("/api/v1/creators/UC0000000000000000000z")
    assert r.status_code == 404 and r.json()["error"] == {
        "code": "not_found",
        "message": "not found",
        "details": [],
    }
    assert "/api/" not in r.text


# ---- B. validation ----------------------------------------------------------------------------------

BAD = [
    "/api/v1/discover?period=0d",
    "/api/v1/discover?period=7",
    "/api/v1/discover?period=7D",
    "/api/v1/discover?period=10000d",
    "/api/v1/discover?period=7d%0A",
    "/api/v1/discover?period=07d",
    "/api/v1/discover?page=0",
    "/api/v1/discover?page_size=0",
    "/api/v1/discover?page_size=101",
    "/api/v1/discover?page=abc",
    "/api/v1/discover?page_size=true",
    "/api/v1/discover?sort=outlier_score",
    "/api/v1/discover?sort=viral_score",
    "/api/v1/discover?sort=engagement_rate",
    "/api/v1/discover?sort=views_per_hour_24h",
    "/api/v1/discover?sort=views_per_hour_lifetime",
    "/api/v1/discover?sort=views_per_follower",
    "/api/v1/discover?sort=VIEWS",
    "/api/v1/discover?sort=",
    "/api/v1/discover?creator_size=unlimited",
    "/api/v1/discover?creator_size=2000000",
    "/api/v1/discover?duration=shorts",
    "/api/v1/discover?region=us",
    "/api/v1/discover?region=USA",
    "/api/v1/discover?min_views=-1",
    "/api/v1/discover?platform=facebook",
    "/api/v1/discover?query=" + "x" * 201,
    "/api/v1/discover?niche=" + "n" * 101,
    "/api/v1/search?query=",
    "/api/v1/search?query=ai&sort=engagement_rate",
    "/api/v1/creators?period=week",
    "/api/v1/creators/a.b",
    "/api/v1/creators/" + "a" * 65,
]


@pytest.mark.parametrize("url", BAD)
def test_invalid_requests_are_422_before_any_foundation_request(url):
    nf = Foundation()
    r = client(nf).get(url)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] in {"invalid_request", "invalid_parameter"}
    assert [q for q in nf.requests if q.url.path != "/api/health"] == []


def test_validation_errors_do_not_echo_the_input():
    r = client().get("/api/v1/discover?region=<script>alert(1)</script>")
    assert r.status_code == 422 and "<script>" not in r.text


@pytest.mark.parametrize("platform", ["instagram", "tiktok"])
@pytest.mark.parametrize(
    "path", ["/api/v1/discover", "/api/v1/search?query=x", "/api/v1/creators", f"/api/v1/creators/{CHANNEL}"]
)
def test_unavailable_platforms_are_refused_with_the_reason(platform, path):
    nf = Foundation()
    sep = "&" if "?" in path else "?"
    r = client(nf).get(f"{path}{sep}platform={platform}")
    assert r.status_code == 422 and r.json()["error"]["code"] == "platform_unavailable"
    assert "No approved data source" in r.json()["error"]["message"] and nf.requests == []


def test_a_disabled_youtube_provider_is_503_not_an_empty_result():
    r = client(providers={}).get("/api/v1/discover")
    assert r.status_code == 503 and r.json()["error"]["code"] == "platform_disabled"


def test_a_page_beyond_the_result_window_is_refused():
    nf = Foundation()
    r = client(nf).get("/api/v1/discover?page=11&page_size=100")
    assert r.status_code == 422 and r.json()["error"]["code"] == "page_out_of_range" and nf.requests == []


@pytest.mark.parametrize("extra", ["creator_size=up_to_10k", "min_views=5", "region=US"])
def test_query_with_a_discover_only_filter_is_refused(extra):
    r = client().get(f"/api/v1/discover?query=ai&{extra}")
    assert r.status_code == 422 and r.json()["error"]["code"] == "filter_not_supported_with_query"


def test_only_get_is_routed_and_no_ingestion_route_exists():
    app = client().app
    paths = {r.path: r.methods for r in app.routes if hasattr(r, "methods")}
    api = {p: m for p, m in paths.items() if p.startswith("/api/")}
    assert set(api) == {
        "/api/v1/health",
        "/api/v1/health/ready",
        "/api/v1/capabilities",
        "/api/v1/discover",
        "/api/v1/search",
        "/api/v1/creators",
        "/api/v1/creators/{creator_id}",
    }
    assert all(m <= {"GET", "HEAD"} for m in api.values())
    assert client().post("/api/v1/discover").status_code == 405


# ---- C. policy -------------------------------------------------------------------------------------


@pytest.mark.parametrize("url", ENDPOINTS)
def test_no_restricted_or_upstream_only_key_reaches_any_response(url):
    body = client().get(url).json()
    found = keys(body)
    assert not found & UPSTREAM_ONLY
    restricted = {r.name for r in RULES if r.exposure is not Exposure.ALLOWED}
    assert not found & restricted
    assert not found & {"views_per_hour_24h", "views_gained_24h", "semantic_score"}
    guard.check(body)


def test_video_fields_are_exactly_the_contract():
    v = client().get("/api/v1/discover?period=all").json()["data"][0]
    assert set(v) == {
        "id",
        "platform",
        "url",
        "title",
        "thumbnail_url",
        "published_at",
        "duration_seconds",
        "content_type",
        "category",
        "language",
        "region",
        "creator",
        "metrics",
        "derived",
        "origin",
        "retrieved_at",
    }
    assert set(v["metrics"]) == {"views", "likes", "comments"}
    assert set(v["derived"]) == {"engagement_rate", "views_per_hour_lifetime"}


def test_hidden_likes_are_null_and_engagement_is_null_never_zero():
    body = load_fixture("viral.json")
    for item in body["results"]:
        item["likes"] = None  # hidden by the creator; the foundation still sends an engagementRate
        assert item["engagementRate"] is not None
    data = client(Foundation(routes={"/api/viral": body})).get("/api/v1/discover?period=all").json()["data"]
    assert data
    for v in data:
        assert v["metrics"]["likes"] is None
        assert v["derived"]["engagement_rate"] is None


def test_a_reported_zero_stays_zero_and_is_distinguishable_from_hidden():
    body = load_fixture("viral.json")
    body["results"][0]["likes"] = 0
    body["results"][0]["comments"] = 0
    nf = Foundation(routes={"/api/viral": body})
    v = client(nf).get("/api/v1/discover?period=all").json()["data"][0]
    assert v["metrics"]["likes"]["value"] == 0 and v["metrics"]["comments"]["value"] == 0
    assert v["derived"]["engagement_rate"]["value"] == body["results"][0]["engagementRate"]


def test_missing_raw_values_are_null():
    body = load_fixture("viral.json")
    for k in ("views", "comments", "channelSubscribers", "channelVideoCount", "lengthSeconds", "publishedAt"):
        body["results"][0].pop(k, None)
    v = client(Foundation(routes={"/api/viral": body})).get("/api/v1/discover?period=all").json()["data"][0]
    assert v["metrics"]["views"] is None and v["metrics"]["comments"] is None
    assert v["creator"]["followers"] is None and v["creator"]["content_count"] is None
    assert v["duration_seconds"] is None and v["published_at"] is None
    assert v["derived"]["views_per_hour_lifetime"] is None


def test_provenance_is_preserved_on_every_metric():
    v = client().get("/api/v1/discover?period=all").json()["data"][0]
    views = v["metrics"]["views"]
    assert views["kind"] == "raw" and views["source"] == "youtube-data-api" and views["provider"] == "youtube"
    assert views["collected_at"] is None  # unknown, not invented
    assert views["foundation_first_seen_at"] is not None
    for m in (x for x in v["derived"].values() if x):
        assert m["kind"] == "derived" and m["note"] and m["source"] != "youtube-data-api"
    assert v["retrieved_at"].startswith("2026-11-03T12:00:00")


@pytest.mark.parametrize("origin,value", [("demo", "demo"), ("test", "test")])
def test_demo_and_test_data_are_labelled_demo(origin, value):
    body = client(origin=origin).get("/api/v1/discover?period=all").json()
    assert body["meta"]["demo"] is True and body["meta"]["data_origin"] == value
    assert {v["origin"] for v in body["data"]} == {value}
    assert {v["metrics"]["views"]["origin"] for v in body["data"]} == {value}
    detail = client(origin=origin).get(f"/api/v1/creators/{CHANNEL}").json()["data"]
    assert detail["demo"] is True and detail["origin"] == value


def test_real_provider_data_is_not_labelled_demo():
    fake = FakeProvider([video(1, origin=DataOrigin.REAL_PROVIDER_DATA)])
    body = client(origin="real", providers={Platform.YOUTUBE: fake}).get("/api/v1/discover").json()
    assert body["meta"]["demo"] is False and body["meta"]["data_origin"] == "real_provider_data"
    assert body["data"][0]["origin"] == "real_provider_data"


def test_the_synthetic_fixtures_are_refused_when_the_deployment_claims_real_data():
    # the provider checks ids against the origin: synthetic ids cannot pass as real provider data
    r = client(origin="real").get("/api/v1/discover?period=all")
    assert r.status_code == 502 and "data" not in r.json()


def test_upstream_hint_and_funnel_texts_naming_restricted_metrics_are_not_passed_on():
    body = load_fixture("viral.json")
    body["hint"] = "Lower min_outlier_score to see more"
    r = client(Foundation(routes={"/api/viral": body})).get("/api/v1/discover?period=all")
    assert r.status_code == 200 and "outlier" not in r.text.lower()


# guard: independent of the schemas


@pytest.mark.parametrize(
    "body",
    [
        {"data": [{"metrics": {"outlierScore": 3}}]},
        {"data": {"nested": [{"deep": {"viral_score": 1}}]}},
        {"meta": {"vsr": 2}},
        {"x": [{"views_per_hour_24h": 1}]},
        {"x": {"Outlier-Score": 1}},
        {"meta": {"notes": ["sorted by outlier score"]}},
        {"data": {"metric": {"note": "acceleration of views"}}},
    ],
)
def test_the_guard_refuses_restricted_keys_and_notes_anywhere(body):
    with pytest.raises(guard.PolicyViolation):
        guard.check(body)


def test_the_guard_does_not_flag_titles_or_the_product_name():
    guard.check(
        {
            "data": [{"title": "Going viral in 30 days: outlier tips", "creator": {"name": "Viral Labs"}}],
            "meta": {"notes": ["omitted by ViralTrack when hidden"]},
        }
    )


class FakeProvider(PlatformProvider):
    provider_id = "youtube"
    platform = Platform.YOUTUBE

    def __init__(self, items=(), notes=(), total=None):
        self.items, self.notes, self.total, self.calls = tuple(items), tuple(notes), total, []

    def capabilities(self):
        return PlatformCapabilities(
            {
                Capability.DISCOVER_CONTENT: CapabilityInfo(True, "x"),
                Capability.SEARCH_CONTENT: CapabilityInfo(True, "x"),
            }
        )

    def discover_content(self, query):
        self.calls.append(query)
        return ContentPage(items=self.items[: query.limit], notes=self.notes, total=self.total)

    def search_content(self, query):
        self.calls.append(query)
        return ContentPage(items=self.items[: query.limit], notes=self.notes, total=self.total)


def video(n: int, creator="UC0000000000000000000a", origin=DataOrigin.TEST) -> Content:
    prov = Provenance("youtube", "youtube-data-api", None, MetricKind.RAW, origin, "fake", Exposure.ALLOWED)
    return Content(
        platform=Platform.YOUTUBE,
        content_id=f"vid{n:05d}",
        content_type=ContentType.VIDEO,
        url=f"https://www.youtube.com/watch?v=vid{n:05d}",
        origin=origin,
        creator=Creator(Platform.YOUTUBE, creator),
        metrics=(Metric("views", 1000 - n, prov),),
    )


def test_a_provider_note_naming_a_restricted_metric_is_withheld_with_a_500():
    fake = FakeProvider([video(1)], notes=("ranked by outlier score",))
    r = client(providers={Platform.YOUTUBE: fake}).get("/api/v1/discover")
    assert r.status_code == 500 and r.json()["error"]["code"] == "policy_violation"
    assert "data" not in r.json() and "outlier" not in r.text


def test_content_refuses_a_restricted_metric_before_the_api_sees_it():
    prov = Provenance(
        "youtube", "niche-finder", None, MetricKind.DERIVED, DataOrigin.TEST, "fake", Exposure.RESTRICTED
    )
    with pytest.raises(ValueError):
        Content(
            platform=Platform.YOUTUBE,
            content_id="v",
            content_type=ContentType.VIDEO,
            url="u",
            origin=DataOrigin.TEST,
            creator=Creator(Platform.YOUTUBE, "c"),
            derived=(Metric("outlier_score", 3, prov),),
        )


# ---- D. pagination, empty and failures --------------------------------------------------------------


def test_pages_are_consecutive_slices_of_one_window():
    fake = FakeProvider([video(i) for i in range(60)], total=60)
    c = client(providers={Platform.YOUTUBE: fake})
    p1 = c.get("/api/v1/discover?page=1&page_size=25").json()
    p2 = c.get("/api/v1/discover?page=2&page_size=25").json()
    p3 = c.get("/api/v1/discover?page=3&page_size=25").json()
    ids = [v["id"] for p in (p1, p2, p3) for v in p["data"]]
    assert ids == [f"vid{i:05d}" for i in range(60)]
    assert [p["meta"]["has_more"] for p in (p1, p2, p3)] == [True, True, False]
    assert [p["meta"]["returned"] for p in (p1, p2, p3)] == [25, 25, 10]
    assert [q.limit for q in fake.calls] == [26, 51, 76]
    assert p1["meta"]["total"] == 60


def test_has_more_is_unknown_when_the_window_is_full():
    fake = FakeProvider([video(i) for i in range(1000)])
    body = client(providers={Platform.YOUTUBE: fake}).get("/api/v1/discover?page=10&page_size=100").json()
    assert body["meta"]["returned"] == 100 and body["meta"]["has_more"] is None


def test_an_empty_result_is_an_empty_page_not_an_error():
    nf = Foundation(routes={"/api/viral": {"results": [], "matched": 0}})
    body = client(nf).get("/api/v1/discover").json()
    assert body["data"] == [] and body["meta"]["has_more"] is False and body["meta"]["total"] == 0


def test_a_page_past_the_last_item_is_empty():
    fake = FakeProvider([video(i) for i in range(5)])
    body = client(providers={Platform.YOUTUBE: fake}).get("/api/v1/discover?page=3&page_size=5").json()
    assert body["data"] == [] and body["meta"]["has_more"] is False


def test_duration_filter_is_applied_by_viraltrack_and_reported():
    nf = Foundation()
    body = client(nf).get("/api/v1/discover?period=all&duration=up_to_3_min").json()
    sent = nf.last("/api/viral").url.params
    assert sent["only_shorts"] == "false" and sent["exclude_shorts"] == "false" and sent["limit"] == "1000"
    assert all(0 < v["duration_seconds"] <= 180 for v in body["data"])
    assert body["meta"]["total"] is None and any("duration filter" in n for n in body["meta"]["notes"])


@pytest.mark.parametrize(
    "fail,status,code",
    [
        (httpx.ConnectError, 503, "provider_unavailable"),
        (httpx.ReadTimeout, 504, "provider_timeout"),
        (httpx.ConnectTimeout, 504, "provider_timeout"),
    ],
)
def test_foundation_failures_map_to_clear_errors_without_internal_details(fail, status, code):
    r = client(Foundation(fail=fail)).get("/api/v1/discover")
    assert r.status_code == status and r.json()["error"]["code"] == code
    assert "nf.internal" not in r.text and "nf.test" not in r.text and "/api/viral" not in r.text


@pytest.mark.parametrize("body", [{"results": "nope"}, {"results": [{"videoId": "x"}]}, {"no": "results"}])
def test_a_malformed_foundation_answer_is_502(body):
    r = client(Foundation(routes={"/api/viral": body})).get("/api/v1/discover")
    assert r.status_code == 502 and r.json()["error"]["code"] == "provider_error"
    assert "results" not in r.json()["error"]["message"]


def test_partial_data_keeps_the_valid_fields_and_nulls_the_rest():
    body = load_fixture("viral.json")
    body["results"][1]["title"] = None
    body["results"][1]["thumbnail"] = None
    v = client(Foundation(routes={"/api/viral": body})).get("/api/v1/discover?period=all").json()["data"][1]
    assert v["title"] is None and v["thumbnail_url"] is None and v["metrics"]["views"]["value"] > 0


# ---- F. OpenAPI --------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def openapi():
    return client().get("/openapi.json").json()


def test_openapi_documents_every_endpoint_with_errors(openapi):
    paths = openapi["paths"]
    assert set(paths) == {
        "/api/v1/health",
        "/api/v1/health/ready",
        "/api/v1/capabilities",
        "/api/v1/discover",
        "/api/v1/search",
        "/api/v1/creators",
        "/api/v1/creators/{creator_id}",
    }
    for p in ("/api/v1/discover", "/api/v1/search", "/api/v1/creators", "/api/v1/creators/{creator_id}"):
        responses = paths[p]["get"]["responses"]
        assert {"200", "422", "502", "503", "504"} <= set(responses)
        assert responses["422"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorOut")
    assert "404" in paths["/api/v1/creators/{creator_id}"]["get"]["responses"]


def test_openapi_sort_and_platform_enums_are_exact(openapi):
    params = {p["name"]: p for p in openapi["paths"]["/api/v1/discover"]["get"]["parameters"]}
    assert params["sort"]["schema"]["enum"] == ["views", "published_at"]
    assert params["platform"]["schema"]["enum"] == ["youtube", "instagram", "tiktok"]
    assert params["page_size"]["schema"]["maximum"] == 100


def test_openapi_schemas_carry_no_restricted_property_and_nullable_fields_are_explicit(openapi):
    schemas = openapi["components"]["schemas"]
    props = set().union(*(set(s.get("properties", {})) for s in schemas.values()))
    restricted = {r.name for r in RULES if r.exposure is not Exposure.ALLOWED}
    assert not props & restricted and not props & UPSTREAM_ONLY
    likes = schemas["VideoMetrics"]["properties"]["likes"]
    assert {"type": "null"} in likes["anyOf"]
    assert {"type": "null"} in schemas["MetricValue"]["properties"]["collected_at"]["anyOf"]
    assert all(
        s.get("additionalProperties") is False
        for n, s in schemas.items()
        if n in {"Video", "VideoMetrics", "VideoDerived", "MetricValue", "CreatorRef"}
    )


SNAPSHOT = ROOT / "docs" / "api" / "openapi-v1.json"


def current_openapi() -> dict:
    return client().app.openapi()


def test_the_committed_openapi_snapshot_is_current():
    """The frontend's typed client is generated from docs/api/openapi-v1.json. Regenerate it with
    `python -m viraltrack.api.openapi > docs/api/openapi-v1.json` when the contract changes on purpose."""
    assert json.loads(SNAPSHOT.read_text(encoding="utf-8")) == current_openapi()


# ---- security and settings ---------------------------------------------------------------------------


def test_cors_is_closed_by_default_and_exact_when_configured():
    r = client().get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
    c = client(api_env={"VT_API_CORS_ORIGINS": "http://localhost:5173"})
    ok = c.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    bad = c.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


@pytest.mark.parametrize(
    "env,environment",
    [
        ({"VT_API_CORS_ORIGINS": "*"}, "development"),
        ({"VT_API_CORS_ORIGINS": "localhost:5173"}, "development"),
        ({"VT_API_CORS_ORIGINS": "http://app.example"}, "production"),
        ({"VT_API_PORT": "0"}, "development"),
        ({"VT_API_HOST": "0.0.0.0"}, "development"),
        ({"VT_API_HOST": "192.168.1.10"}, "development"),
        ({"VT_API_HOST": "example.com"}, "production"),
        ({"VT_API_PORT": "http"}, "development"),
    ],
)
def test_invalid_api_settings_are_refused(env, environment):
    with pytest.raises(ConfigError):
        load_api_settings(env, environment)


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_only_loopback_hosts_are_accepted(host):
    assert load_api_settings({"VT_API_HOST": host}).host == host


@pytest.mark.parametrize(
    "method,url,status,code",
    [
        ("get", "/nope", 404, "not_found"),
        ("get", "/api/health", 404, "not_found"),
        ("get", "/api/viral", 404, "not_found"),
        ("get", "/api/channels/tracked", 404, "not_found"),
        ("get", "/api/v1/creators/a%2Fb", 404, "not_found"),
        ("post", "/api/v1/discover", 405, "method_not_allowed"),
        ("delete", "/api/v1/creators/x", 405, "method_not_allowed"),
    ],
)
def test_unknown_paths_and_methods_use_the_error_envelope(method, url, status, code):
    nf = Foundation()
    r = getattr(client(nf), method)(url)
    assert r.status_code == status and r.json() == {
        "error": {"code": code, "message": code.replace("_", " "), "details": []}
    }
    assert nf.requests == []


def test_api_settings_defaults_bind_locally_with_no_cors():
    s = load_api_settings({})
    assert (s.host, s.port, s.cors_origins) == ("127.0.0.1", 8000, ())


def test_the_access_log_carries_no_query_text_and_returns_a_request_id(caplog):
    caplog.set_level(logging.INFO, logger="viraltrack.api")
    r = client().get("/api/v1/search?query=my-secret-topic", headers={"X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"
    events = [json.loads(m.getMessage()) for m in caplog.records if m.name == "viraltrack.api"]
    assert events and events[-1]["path"] == "/api/v1/search" and events[-1]["status"] == 200
    assert "my-secret-topic" not in caplog.text


def test_an_unsafe_request_id_is_replaced():
    r = client().get("/api/v1/health", headers={"X-Request-ID": "bad\r\nid; drop"})
    assert r.headers["x-request-id"].isalnum() and "drop" not in r.headers["x-request-id"]


def test_the_foundation_token_never_appears_in_responses_or_logs(caplog):
    caplog.set_level(logging.DEBUG)
    s = settings(VT_YOUTUBE_FOUNDATION_TOKEN="tok-very-secret")
    nf = Foundation(fail=httpx.ConnectError)
    http = httpx.Client(transport=httpx.MockTransport(nf))
    app = create_app(
        s,
        load_api_settings({}),
        providers={Platform.YOUTUBE: YouTubeProvider(s.youtube, http_client=http, clock=lambda: NOW)},
    )
    c = TestClient(app, raise_server_exceptions=False)
    texts = [c.get(u).text for u in ENDPOINTS]
    assert all("tok-very-secret" not in t for t in texts) and "tok-very-secret" not in caplog.text


# ---- E. integration: the pinned foundation code on PostgreSQL ----------------------------------------


@pytest.fixture
def real_foundation(pg_schema):
    """A provider whose every request is answered by the REAL pinned foundation code over a seeded schema."""
    from tests.support import synthetic_corpus as corpus
    from tests.support.upstream import run_upstream

    conn, schema = pg_schema
    corpus.seed(conn, schema)
    attempts = []

    def handler(request):
        path = request.url.path + ("?" + request.url.query.decode() if request.url.query else "")
        result = run_upstream(schema, [path])
        attempts.append(result["network_attempts"])
        (resp,) = result["responses"]
        return httpx.Response(resp["status"], json=resp["body"])

    s = settings("test")
    http = httpx.Client(transport=httpx.MockTransport(handler))
    provider = YouTubeProvider(s.youtube, http_client=http)
    yield TestClient(
        create_app(s, load_api_settings({}), providers={Platform.YOUTUBE: provider}),
        raise_server_exceptions=False,
    )
    assert sum(attempts) == 0, "the foundation tried to reach the network"


@pytest.mark.postgres
def test_integration_discover_on_the_real_foundation_is_policy_clean(real_foundation):
    r = real_foundation.get("/api/v1/discover?period=all&page_size=10")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"], "the seeded corpus should produce videos"
    assert not keys(body) & UPSTREAM_ONLY
    views = [v["metrics"]["views"]["value"] for v in body["data"] if v["metrics"]["views"]]
    assert views == sorted(views, reverse=True)
    guard.check(body)


@pytest.mark.postgres
def test_integration_pages_do_not_overlap_on_the_real_foundation(real_foundation):
    p1 = real_foundation.get("/api/v1/discover?period=all&page_size=3&page=1").json()
    p2 = real_foundation.get("/api/v1/discover?period=all&page_size=3&page=2").json()
    a, b = [v["id"] for v in p1["data"]], [v["id"] for v in p2["data"]]
    assert a and not set(a) & set(b)


@pytest.mark.postgres
def test_integration_search_creators_and_detail_on_the_real_foundation(real_foundation):
    s = real_foundation.get("/api/v1/search?query=a&period=all")
    assert s.status_code == 200, s.text
    guard.check(s.json())
    creators = real_foundation.get("/api/v1/creators?period=all").json()
    assert creators["data"]
    cid = creators["data"][0]["creator"]["id"]
    d = real_foundation.get(f"/api/v1/creators/{cid}")
    assert d.status_code == 200, d.text
    assert d.json()["data"]["creator"]["id"] == cid
    assert not keys(d.json()) & UPSTREAM_ONLY


@pytest.mark.postgres
def test_integration_database_readiness_against_postgresql():
    import os

    from viraltrack.api.app import _database_check, db_check_status

    url = os.environ.get("VT_TEST_DATABASE_URL")
    if not url:
        pytest.skip("VT_TEST_DATABASE_URL not set")
    assert db_check_status(_database_check(load_settings({"DATABASE_URL": url}))) == "ok"
