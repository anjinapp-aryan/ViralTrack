import os
from datetime import datetime, timezone

import httpx
import pytest

from tests.conftest import load_fixture
from viraltrack.config import load_settings
from viraltrack.domain import (
    Capability,
    ContentType,
    MetricKind,
    NotFound,
    Platform,
    ProviderError,
    ProviderUnavailable,
    UnsupportedCapability,
)
from viraltrack.providers import DiscoveryQuery, SearchQuery, build_providers
from viraltrack.providers.youtube import YouTubeProvider

NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
CHANNEL = "UC0000000000000000000f"

ROUTES = {
    "/api/viral": "viral.json",
    "/api/search": "search.json",
    f"/api/channels/{CHANNEL}": "channel.json",
    f"/api/channels/{CHANNEL}/history": "channel_history.json",
}


class Recorder:
    def __init__(self, routes=ROUTES, status=200, body=None):
        self.routes, self.status, self.body = routes, status, body
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.body is not None:
            return httpx.Response(self.status, content=self.body)
        name = self.routes.get(request.url.path)
        if name is None:
            return httpx.Response(404, json={"detail": "Run collect_channel / track_channel first."})
        if request.url.params.get("only_shorts") == "true":
            name = "viral_shorts.json"
        return httpx.Response(self.status, json=load_fixture(name))


def make_provider(handler, env=None):
    settings = load_settings({"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test", **(env or {})})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return YouTubeProvider(settings.youtube, http_client=client, clock=lambda: NOW)


# 1. provider initialization ---------------------------------------------------

def test_registry_builds_youtube_only():
    providers = build_providers(load_settings({}))
    assert list(providers) == [Platform.YOUTUBE]
    assert build_providers(load_settings({"VT_YOUTUBE_ENABLED": "false"})) == {}


def test_token_sent_only_when_configured():
    rec = Recorder()
    make_provider(rec).discover_content(DiscoveryQuery())
    assert "authorization" not in rec.requests[-1].headers
    assert rec.requests[-1].headers["x-nf-locale"] == "en"
    rec = Recorder()
    make_provider(rec, {"VT_YOUTUBE_FOUNDATION_TOKEN": "t0k"}).discover_content(DiscoveryQuery())
    assert rec.requests[-1].headers["authorization"] == "Bearer t0k"


# 2. normalized content mapping ------------------------------------------------

def test_discovery_maps_to_normalized_content():
    page = make_provider(Recorder()).discover_content(DiscoveryQuery(period="30d", limit=3))
    assert page.total == 25 and len(page.items) == 3
    c = page.items[0]
    assert c.platform is Platform.YOUTUBE and c.provider == "youtube"
    assert c.content_id == "bvid008"
    assert c.url == "https://www.youtube.com/watch?v=bvid008"
    assert c.content_type is ContentType.VIDEO
    assert c.creator.creator_id == "UC0000000000000000000b"
    assert c.creator.url == "https://www.youtube.com/@facelesshistory"
    assert c.creator.followers.value == 9400
    assert c.published_at == datetime.fromisoformat("2026-10-15T14:11:45.824508+00:00")
    assert c.duration_seconds == 302 and c.category == "Education"
    assert c.retrieved_at == NOW


def test_shorts_query_maps_short_form():
    rec = Recorder()
    page = make_provider(rec).discover_content(DiscoveryQuery(short_form=True))
    assert rec.requests[-1].url.params["only_shorts"] == "true"
    assert {c.content_type for c in page.items} == {ContentType.SHORT}


def test_search_and_creator():
    p = make_provider(Recorder())
    assert len(p.search_content(SearchQuery(text="dinner")).items) == 3
    creator = p.get_creator(CHANNEL)
    assert creator.name == "Cooking Shorts Co" and creator.handle == "@cookingshortsco"
    history = p.get_creator_history(CHANNEL)
    assert len(history) == 3 and history[0].captured_at < history[-1].captured_at


# 6. data provenance -----------------------------------------------------------

def test_raw_and_derived_provenance():
    c = make_provider(Recorder()).discover_content(DiscoveryQuery()).items[0]
    raw = {m.name: m for m in c.metrics}
    derived = {m.name: m for m in c.derived}
    assert set(raw) == {"views", "likes", "comments"}
    assert raw["views"].value == 1086943
    assert all(m.provenance.kind is MetricKind.RAW and m.provenance.source == "youtube-data-api"
               for m in raw.values())
    assert {"outlier_score", "views_per_hour_24h", "acceleration"} <= set(derived)
    assert all(m.provenance.kind is MetricKind.DERIVED and m.provenance.source == "niche-finder"
               for m in derived.values())
    # niche-finder reports no per-item fetch time on these endpoints: unknown, not invented
    assert raw["views"].provenance.collected_at is None


def test_history_points_carry_their_capture_time():
    snap = make_provider(Recorder()).get_creator_history(CHANNEL)[0]
    assert all(m.provenance.collected_at == snap.captured_at for m in snap.metrics)


# 3. provider error handling ---------------------------------------------------

def test_unreachable_foundation():
    def boom(request):
        raise httpx.ConnectError("refused", request=request)
    with pytest.raises(ProviderUnavailable):
        make_provider(boom).discover_content(DiscoveryQuery())


def test_not_found_creator():
    with pytest.raises(NotFound, match="collect_channel"):
        make_provider(Recorder()).get_creator("UCunknown")


@pytest.mark.parametrize("status,body", [(500, b'{"detail": "boom"}'), (200, b"<html>"),
                                         (200, b"[1, 2]"), (401, b"{}")])
def test_bad_responses(status, body):
    with pytest.raises(ProviderError):
        make_provider(Recorder(status=status, body=body)).discover_content(DiscoveryQuery())


def test_invalid_period_rejected_before_any_call():
    rec = Recorder()
    with pytest.raises(ValueError):
        make_provider(rec).discover_content(DiscoveryQuery(period="last week"))
    assert rec.requests == []


# 4. unsupported capability handling -------------------------------------------

@pytest.mark.parametrize("call,cap", [
    (lambda p: p.get_trending_content(), Capability.GLOBAL_TRENDING),
    (lambda p: p.get_content("bvid008"), Capability.GET_CONTENT),
])
def test_unsupported_raises_and_makes_no_call(call, cap):
    rec = Recorder()
    p = make_provider(rec)
    assert not p.capabilities().supports(cap)
    with pytest.raises(UnsupportedCapability) as err:
        call(p)
    assert err.value.capability is cap and err.value.note
    assert rec.requests == []


def test_audio_and_hashtags_declared_unsupported():
    caps = make_provider(Recorder()).capabilities()
    assert not caps.supports(Capability.AUDIO)
    assert not caps.supports(Capability.HASHTAGS)
    assert caps.supports(Capability.SHORT_FORM)


# 8. persistence boundary ------------------------------------------------------

def test_provider_only_reads():
    rec = Recorder()
    p = make_provider(rec)
    p.discover_content(DiscoveryQuery())
    p.search_content(SearchQuery())
    p.get_creator(CHANNEL)
    p.get_creator_history(CHANNEL)
    assert {r.method for r in rec.requests} == {"GET"}


# live smoke against a running foundation (local only) -------------------------

@pytest.mark.live_foundation
def test_live_foundation():
    url = os.environ.get("VT_TEST_FOUNDATION_URL")
    if not url:
        pytest.skip("VT_TEST_FOUNDATION_URL not set")
    settings = load_settings({"VT_YOUTUBE_FOUNDATION_URL": url})
    p = YouTubeProvider(settings.youtube)
    try:
        page = p.discover_content(DiscoveryQuery(period="30d", limit=5))
        # an empty corpus is a valid answer; whatever comes back must map cleanly
        assert isinstance(page.total, int)
        assert all(c.platform is Platform.YOUTUBE and c.metric("views") for c in page.items)
    finally:
        p.close()
