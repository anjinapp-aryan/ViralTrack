import json
import os
from datetime import datetime, timezone

import httpx
import pytest

from tests.conftest import load_fixture
from viraltrack.config import load_settings
from viraltrack.domain import (
    Capability,
    ContentType,
    DataOrigin,
    MetricKind,
    NotFound,
    Platform,
    ProviderError,
    ProviderUnavailable,
    RestrictedMetric,
    UnsupportedCapability,
)
from viraltrack.providers import DiscoveryQuery, SearchQuery, build_providers
from viraltrack.providers.youtube import YouTubeProvider
from viraltrack.providers.youtube.mapping import ADAPTER_ID, DERIVED_VIDEO_METRICS, RAW_VIDEO_METRICS
from viraltrack.providers.youtube.metric_policy import RULES

NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
CHANNEL = "UC0000000000000000000f"
AMENDMENT = {"VT_YOUTUBE_ANALYTICS_AMENDMENT_ACCEPTED": "true"}

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
    # fixtures are the foundation's synthetic demo corpus, so they are TEST data
    settings = load_settings({"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test",
                              "VT_YOUTUBE_DATA_ORIGIN": "test", **(env or {})})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return YouTubeProvider(settings.youtube, http_client=client, clock=lambda: NOW)


# 1. provider initialization ---------------------------------------------------

def test_registry_builds_youtube_only():
    providers = build_providers(load_settings({}))
    assert list(providers) == [Platform.YOUTUBE]
    assert build_providers(load_settings({"VT_YOUTUBE_ENABLED": "false"})) == {}


def test_headers():
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


def test_shorts_filter_is_allowed_but_label_is_restricted():
    rec = Recorder()
    page = make_provider(rec).discover_content(DiscoveryQuery(short_form=True))
    assert rec.requests[-1].url.params["only_shorts"] == "true"
    assert {c.content_type for c in page.items} == {ContentType.VIDEO}
    page = make_provider(Recorder(), AMENDMENT).discover_content(DiscoveryQuery(short_form=True))
    assert {c.content_type for c in page.items} == {ContentType.SHORT}


def test_search_and_creator():
    p = make_provider(Recorder())
    assert len(p.search_content(SearchQuery(text="dinner")).items) == 3
    creator = p.get_creator(CHANNEL)
    assert creator.name == "Cooking Shorts Co" and creator.handle == "@cookingshortsco"
    history = p.get_creator_history(CHANNEL)
    assert len(history) == 3 and history[0].captured_at < history[-1].captured_at


def test_creator_id_is_encoded_in_the_path():
    rec = Recorder()
    with pytest.raises(NotFound):
        make_provider(rec).get_creator("../admin")
    assert rec.requests[-1].url.raw_path.startswith(b"/api/channels/..%2Fadmin")
    with pytest.raises(ValueError):
        make_provider(rec).get_creator(" ")


# 6. data provenance -----------------------------------------------------------

def test_every_record_answers_the_provenance_questions():
    c = make_provider(Recorder()).discover_content(DiscoveryQuery()).items[0]
    assert c.platform is Platform.YOUTUBE                     # which platform
    assert c.provider == "youtube"                            # which provider
    assert c.content_id == "bvid008"                          # which external id
    assert c.retrieved_at == NOW                              # when ViralTrack read it
    assert c.origin is DataOrigin.TEST                        # real, demo or test
    for m in c.metrics + c.derived + (c.creator.followers,):
        assert m.provenance.adapter == ADAPTER_ID             # which adapter
        assert m.provenance.origin is DataOrigin.TEST
        assert m.provenance.kind in (MetricKind.RAW, MetricKind.DERIVED)
    # niche-finder reports no per-item fetch time on these endpoints: unknown, not invented
    assert c.metric("views").provenance.collected_at is None


def test_raw_and_allowed_derived_by_default():
    c = make_provider(Recorder()).discover_content(DiscoveryQuery()).items[0]
    assert {m.name for m in c.metrics} == {"views", "likes", "comments"}
    assert all(m.provenance.source == "youtube-data-api" for m in c.metrics)
    assert {m.name for m in c.derived} == {
        "engagement_rate", "views_per_hour_lifetime", "views_per_hour_24h", "views_gained_24h",
        "acceleration", "views_per_follower"}
    assert all(m.provenance.source == "niche-finder" and "not a YouTube metric" in m.provenance.note
               for m in c.derived)


def test_history_points_carry_their_capture_time():
    snap = make_provider(Recorder()).get_creator_history(CHANNEL)[0]
    assert all(m.provenance.collected_at == snap.captured_at for m in snap.metrics)


# derived-metric policy --------------------------------------------------------

RESTRICTED = {"outlier_score", "outlier_score_age_adjusted", "outlier_score_nexlev", "viral_score",
              "projected_30d_views", "estimated_rpm"}


def test_restricted_metrics_never_mapped_without_approval():
    p = make_provider(Recorder())
    for page in (p.discover_content(DiscoveryQuery()), p.search_content(SearchQuery())):
        for c in page.items:
            assert not RESTRICTED & {m.name for m in c.derived}


def test_restricted_metrics_mapped_with_approval():
    c = make_provider(Recorder(), AMENDMENT).discover_content(DiscoveryQuery()).items[0]
    assert {"outlier_score", "viral_score", "estimated_rpm"} <= {m.name for m in c.derived}


def test_internal_only_metrics_never_mapped():
    c = make_provider(Recorder(), AMENDMENT).search_content(SearchQuery(text="x")).items[0]
    assert not {"baseline_median_views", "semantic_score"} & {m.name for m in c.derived}


def test_every_mapped_derived_field_has_a_policy_rule():
    names = {r.name for r in RULES}
    assert set(DERIVED_VIDEO_METRICS.values()) <= names
    assert not set(RAW_VIDEO_METRICS.values()) & names


# niche-finder fields ViralTrack deliberately does not map (allow-list contract).
IGNORED_FIELDS = {
    "ageHours", "ageDays", "lengthSeconds", "channelSubscribers", "channelVideoCount", "snapshots",
    "outlierScoreRolling", "outlierScorePeriod", "baselineMedianViews", "baselineMedianViewsPeriod",
    "semanticScore",
}


def test_every_upstream_numeric_field_is_classified():
    """A new numeric field from the foundation must be classified before it can be used."""
    known = set(RAW_VIDEO_METRICS) | set(DERIVED_VIDEO_METRICS) | IGNORED_FIELDS
    for name in ("viral.json", "search.json", "viral_shorts.json"):
        for item in load_fixture(name)["results"]:
            numeric = {k for k, v in item.items()
                       if isinstance(v, (int, float)) and not isinstance(v, bool)}
            assert numeric <= known, numeric - known


def test_default_sort_is_by_raw_views():
    rec = Recorder()
    p = make_provider(rec)
    p.discover_content(DiscoveryQuery())
    p.search_content(SearchQuery())
    assert [r.url.params["sort_by"] for r in rec.requests] == ["views", "views"]


def test_sorting_by_a_restricted_metric_is_refused_before_any_call():
    rec = Recorder()
    with pytest.raises(RestrictedMetric):
        make_provider(rec).discover_content(DiscoveryQuery(sort="outlier_score"))
    assert rec.requests == []
    rec = Recorder()
    make_provider(rec, AMENDMENT).discover_content(DiscoveryQuery(sort="outlier_score"))
    assert rec.requests[-1].url.params["sort_by"] == "outlier"


# The only query parameters the adapter may send. Anything that filters or ranks by a
# restricted score (min_outlier_score, preset, sort_by=viral/outlier) is absent.
SENT_PARAMS = {"period", "sort_by", "limit", "region", "niche", "max_subscribers", "min_views",
               "only_shorts", "exclude_shorts", "query"}


def test_adapter_never_filters_or_ranks_by_restricted_scores():
    rec = Recorder()
    p = make_provider(rec)
    p.discover_content(DiscoveryQuery(region="US", niche="cooking", max_creator_followers=5000,
                                      min_views=10, short_form=False))
    p.search_content(SearchQuery(text="x", niche="cooking", short_form=True))
    for r in rec.requests:
        assert set(r.url.params) <= SENT_PARAMS
        assert r.url.params["sort_by"] in {"views", "published"}


def test_allowed_derived_sort_and_unknown_sort():
    rec = Recorder()
    make_provider(rec).discover_content(DiscoveryQuery(sort="views_per_hour_24h"))
    assert rec.requests[-1].url.params["sort_by"] == "vph"
    with pytest.raises(ValueError):
        make_provider(rec).discover_content(DiscoveryQuery(sort="random"))


# demo / test / real data ------------------------------------------------------

def test_demo_corpus_cannot_pass_as_real_provider_data():
    with pytest.raises(ProviderError, match="demo data"):
        make_provider(Recorder(), {"VT_YOUTUBE_DATA_ORIGIN": "real"}).discover_content(DiscoveryQuery())


def test_real_ids_accepted_as_real():
    item = dict(load_fixture("viral.json")["results"][0],
                videoId="dQw4w9WgXcQ", channelId="UCuAXFkgsw1L7xaCfnd5JJOw")
    body = json.dumps({"results": [item]}).encode()
    p = make_provider(Recorder(body=body), {"VT_YOUTUBE_DATA_ORIGIN": "real"})
    c = p.discover_content(DiscoveryQuery()).items[0]
    assert c.origin is DataOrigin.REAL_PROVIDER_DATA
    assert c.metric("views").provenance.origin is DataOrigin.REAL_PROVIDER_DATA


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
    origin = os.environ.get("VT_TEST_FOUNDATION_ORIGIN", "demo")
    settings = load_settings({"VT_YOUTUBE_FOUNDATION_URL": url, "VT_YOUTUBE_DATA_ORIGIN": origin})
    p = YouTubeProvider(settings.youtube)
    try:
        page = p.discover_content(DiscoveryQuery(period="30d", limit=5))
        # an empty corpus is a valid answer; whatever comes back must map cleanly
        assert isinstance(page.total, int)
        assert all(c.platform is Platform.YOUTUBE and c.metric("views") for c in page.items)
        assert all(not RESTRICTED & {m.name for m in c.derived} for c in page.items)
    finally:
        p.close()
