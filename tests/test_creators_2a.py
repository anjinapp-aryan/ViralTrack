"""Phase 2A: a creator's videos (provider mapping, API contract, ordering) and the creator pages' API surface.

Offline. The fixture `channel_velocity.json` has the real shape of the foundation's
`/api/channels/{id}/velocity` payload, including every restricted field it carries,
and its order is the foundation's own: by the withheld 24-hour rate, not by date.
The real-foundation tests at the end run the pinned foundation code on PostgreSQL
(VT_TEST_DATABASE_URL + VT_TEST_UPSTREAM_PYTHON) and skip without them.
"""

from datetime import timezone

import httpx
import pytest

from tests.conftest import load_fixture
from tests.test_api_d5 import (  # noqa: F401  (real_foundation is a fixture)
    CHANNEL,
    Foundation,
    client,
    keys,
    real_foundation,
)
from tests.test_youtube_provider import Recorder, make_provider
from viraltrack.domain import (
    Capability,
    ContentType,
    NotFound,
    Platform,
    ProviderError,
    UnsupportedCapability,
)
from viraltrack.providers.base import PlatformProvider
from viraltrack.providers.youtube.provider import CREATOR_CONTENT_WINDOW

VELOCITY = f"/api/channels/{CHANNEL}/velocity"
ROUTES = {
    f"/api/channels/{CHANNEL}": "channel.json",
    VELOCITY: "channel_velocity.json",
}
UPSTREAM_ORDER = ["fvid029", "fvid006", "fvid032", "fvid040", "fvid011"]  # by vph24h, as the foundation sends
EXPECTED_ORDER = ["fvid032", "fvid006", "fvid029", "fvid011", "fvid040"]  # newest first; undated last
# everything in the payload that ViralTrack must never expose
FORBIDDEN_KEYS = {
    "ageHours",
    "isShort",
    "trend",
    "snapshots",
    "vphLifetime",
    "vph24h",
    "viewsGained24h",
    "acceleration",
    "outlierScore",
    "viralScore",
    "viewsPerSubscriber",
    "estimatedRpm",
    "channelId",
    "period",
    "videos",
}
FOUNDATION_NOTE = "vph24h/acceleration need at least two snapshots"


def provider(handler=None, env=None):
    return make_provider(handler or Recorder(ROUTES), env)


def test_the_fixture_is_ordered_by_the_withheld_rate_not_by_date():
    ids = [v["videoId"] for v in load_fixture("channel_velocity.json")["videos"]]
    assert ids == UPSTREAM_ORDER and ids != EXPECTED_ORDER
    rates = [v["vph24h"] for v in load_fixture("channel_velocity.json")["videos"] if v["vph24h"] is not None]
    assert rates == sorted(rates, reverse=True)


# ---- provider: ordering ------------------------------------------------------------------------------


def test_videos_are_ordered_by_publication_time_by_viraltrack_not_by_the_foundation():
    page = provider().get_creator_content(CHANNEL)
    assert [c.content_id for c in page.items] == EXPECTED_ORDER


def test_ties_break_by_id_and_undated_videos_come_last_whatever_the_upstream_order():
    body = load_fixture("channel_velocity.json")
    same = "2026-11-01T00:00:00+00:00"
    body["videos"] = [
        dict(body["videos"][0], videoId=i, publishedAt=same) for i in ("fvid3", "fvid1", "fvid2")
    ]
    body["videos"] += [dict(body["videos"][0], videoId=i, publishedAt=None) for i in ("fvidz", "fvida")]
    routes = {f"/api/channels/{CHANNEL}": "channel.json"}

    def handler(request):
        if request.url.path == VELOCITY:
            return httpx.Response(200, json=body)
        return Recorder(routes)(request)

    page = provider(handler).get_creator_content(CHANNEL)
    assert [c.content_id for c in page.items] == ["fvid1", "fvid2", "fvid3", "fvida", "fvidz"]


@pytest.mark.parametrize("reverse", [False, True])
def test_the_result_does_not_depend_on_the_order_the_foundation_used(reverse):
    body = load_fixture("channel_velocity.json")
    if reverse:
        body["videos"].reverse()

    def handler(request):
        if request.url.path == VELOCITY:
            return httpx.Response(200, json=body)
        return Recorder(ROUTES)(request)

    assert [c.content_id for c in provider(handler).get_creator_content(CHANNEL).items] == EXPECTED_ORDER


# ---- provider: allow-list and nulls ------------------------------------------------------------------


def test_only_the_allowed_raw_fields_become_content():
    page = provider().get_creator_content(CHANNEL)
    for c in page.items:
        assert c.derived == ()
        assert {m.name for m in c.metrics} <= {"views"}
        assert c.thumbnail_url is None and c.duration_seconds is None
        assert c.content_type is ContentType.VIDEO  # isShort in the payload is RESTRICTED and ignored
        assert c.platform is Platform.YOUTUBE and c.creator.creator_id == CHANNEL
        assert c.url == f"https://www.youtube.com/watch?v={c.content_id}"
        assert c.published_at is None or c.published_at.tzinfo is timezone.utc
        assert c.language is None and c.category is None and c.region is None and c.hashtags == ()


def test_the_creator_on_each_video_is_the_collected_profile_with_provenance():
    first = provider().get_creator_content(CHANNEL).items[0]
    assert first.creator.name == "Synthetic Channel" or first.creator.name  # from channel.json
    assert first.creator.followers is not None and first.creator.followers.provenance.kind.value == "raw"


def test_a_missing_view_count_is_unknown_never_zero():
    by_id = {c.content_id: c for c in provider().get_creator_content(CHANNEL).items}
    assert by_id["fvid011"].metrics == ()  # views null upstream
    assert by_id["fvid029"].metric("views").value == 69222


def test_a_reported_zero_view_count_stays_zero():
    body = load_fixture("channel_velocity.json")
    body["videos"][0]["views"] = 0

    def handler(request):
        return httpx.Response(200, json=body) if request.url.path == VELOCITY else Recorder(ROUTES)(request)

    by_id = {c.content_id: c for c in provider(handler).get_creator_content(CHANNEL).items}
    assert by_id["fvid029"].metric("views").value == 0


def test_a_missing_publication_date_is_unknown_not_the_collection_time():
    by_id = {c.content_id: c for c in provider().get_creator_content(CHANNEL).items}
    assert by_id["fvid040"].published_at is None


def test_the_foundations_own_note_is_not_passed_on():
    page = provider().get_creator_content(CHANNEL)
    assert not any(FOUNDATION_NOTE in n or "vph" in n for n in page.notes)


def test_views_carry_raw_provenance_with_unknown_read_time():
    m = provider().get_creator_content(CHANNEL).items[0].metric("views")
    assert m.provenance.kind.value == "raw" and m.provenance.source == "youtube-data-api"
    assert m.provenance.collected_at is None and m.provenance.origin.value == "test"


# ---- provider: requests and validation ---------------------------------------------------------------


def test_the_creator_is_checked_first_and_the_velocity_request_carries_only_period_and_limit():
    rec = Recorder(ROUTES)
    provider(rec).get_creator_content(CHANNEL, period="7d", limit=9)
    assert [r.url.path for r in rec.requests] == [f"/api/channels/{CHANNEL}", VELOCITY]
    assert dict(rec.requests[1].url.params) == {"period": "7d", "limit": "9"}
    assert all(r.method == "GET" for r in rec.requests)


def test_an_unknown_creator_is_not_found_and_no_video_request_is_made():
    rec = Recorder({VELOCITY: "channel_velocity.json"})  # the profile route answers 404
    with pytest.raises(NotFound):
        provider(rec).get_creator_content(CHANNEL)
    assert [r.url.path for r in rec.requests] == [f"/api/channels/{CHANNEL}"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": 0},
        {"limit": -1},
        {"limit": CREATOR_CONTENT_WINDOW + 1},
        {"limit": True},
        {"limit": 1.5},
        {"limit": "5"},
        {"period": "forever"},
        {"period": "0d"},
        {"period": "7D"},
        {"period": "7d\n"},
        {"period": "10000d"},
    ],
)
def test_invalid_arguments_are_refused_before_any_request(kwargs):
    rec = Recorder(ROUTES)
    with pytest.raises(ValueError):
        provider(rec).get_creator_content(CHANNEL, **kwargs)
    assert rec.requests == []


@pytest.mark.parametrize("creator", ["", "   ", ".", "..", " .. "])
def test_an_empty_or_dot_creator_id_is_refused_before_any_request(creator):
    rec = Recorder(ROUTES)
    with pytest.raises(ValueError):
        provider(rec).get_creator_content(creator)
    assert rec.requests == []


@pytest.mark.parametrize("creator", ["a/b", "../x", "a%2Fb", "x y", "a?b=1", "a#c"])
def test_a_creator_id_is_percent_encoded_into_exactly_one_path_segment(creator):
    rec = Recorder(ROUTES)
    with pytest.raises(NotFound):
        provider(rec).get_creator_content(creator)
    raw = rec.requests[0].url.raw_path.decode()
    assert raw.startswith("/api/channels/") and raw.count("/") == 3 and "?" not in raw and "#" not in raw


def test_the_largest_window_is_accepted():
    rec = Recorder(ROUTES)
    provider(rec).get_creator_content(CHANNEL, limit=CREATOR_CONTENT_WINDOW)
    assert rec.requests[-1].url.params["limit"] == str(CREATOR_CONTENT_WINDOW)


# ---- provider: malformed answers, duplicates, totals ------------------------------------------------


def serve(videos, **extra):
    body = {"channelId": CHANNEL, "period": "all", "videos": videos, **extra}

    def handler(request):
        return httpx.Response(200, json=body) if request.url.path == VELOCITY else Recorder(ROUTES)(request)

    return provider(handler)


@pytest.mark.parametrize(
    "videos,fragment",
    [
        (["not an object"], "videos[0]"),
        ([{"title": "no id"}], "videos[0]"),
        ([{"videoId": 5}], "videos[0]"),
        ([{"videoId": "ok1", "views": "many"}], "videos[0]"),
        ([{"videoId": "ok1", "views": True}], "videos[0]"),
        ([{"videoId": "ok1", "title": 7}], "videos[0]"),
        ([{"videoId": "ok1"}, {"videoId": "ok2", "title": ["a list"]}], "videos[1]"),
    ],
)
def test_one_malformed_entry_fails_the_whole_response(videos, fragment):
    with pytest.raises(ProviderError) as caught:
        serve(videos).get_creator_content(CHANNEL)
    assert fragment in str(caught.value)


@pytest.mark.parametrize(
    "body", [{"videos": "nope"}, {"videos": None}, {"no": "videos"}, {"videos": {"a": 1}}]
)
def test_a_response_without_a_video_list_is_an_error_not_an_empty_list(body):
    def handler(request):
        return httpx.Response(200, json=body) if request.url.path == VELOCITY else Recorder(ROUTES)(request)

    with pytest.raises(ProviderError):
        provider(handler).get_creator_content(CHANNEL)


def test_a_duplicate_video_id_keeps_one_entry_and_says_so():
    a = {"videoId": "dup1", "title": "first", "publishedAt": "2026-11-01T00:00:00+00:00", "views": 5}
    b = {"videoId": "dup1", "title": "second", "publishedAt": "2026-10-01T00:00:00+00:00", "views": 9}
    page = serve([b, a]).get_creator_content(CHANNEL)
    assert [c.content_id for c in page.items] == ["dup1"] and page.items[
        0
    ].title == "first"  # newest copy wins
    assert any("duplicate video id" in n for n in page.notes)


def test_no_videos_is_an_empty_page_with_a_known_total():
    page = serve([]).get_creator_content(CHANNEL, limit=24)
    assert page.items == () and page.total == 0


@pytest.mark.parametrize("limit,total", [(5, None), (6, 5), (24, 5)])
def test_the_total_is_known_only_when_the_list_is_shorter_than_the_window_asked(limit, total):
    assert provider().get_creator_content(CHANNEL, limit=limit).total == total


def test_synthetic_ids_are_refused_when_the_deployment_claims_real_data():
    with pytest.raises(ProviderError):
        provider(env={"VT_YOUTUBE_DATA_ORIGIN": "real"}).get_creator_content(CHANNEL)


# ---- interface and capability -------------------------------------------------------------------------


def test_the_capability_is_declared_with_its_limits():
    caps = provider().capabilities()
    assert caps.supports(Capability.CREATOR_CONTENT)
    note = caps.info[Capability.CREATOR_CONTENT].note
    assert "no likes, comments, length or thumbnail" in note and "at most 200" in note


def test_a_provider_without_the_capability_raises_instead_of_returning_an_empty_list():
    class Bare(PlatformProvider):
        provider_id = "bare"
        platform = Platform.TIKTOK

        def capabilities(self):
            from viraltrack.domain import PlatformCapabilities

            return PlatformCapabilities({})

    with pytest.raises(UnsupportedCapability):
        Bare().get_creator_content("x")


# ---- API ---------------------------------------------------------------------------------------------------


def api(nf=None, **kw):
    return client(nf or Foundation(routes={VELOCITY: "channel_velocity.json"}), **kw)


def videos(c, query=""):
    return c.get(f"/api/v1/creators/{CHANNEL}/videos{query}")


def test_the_endpoint_lists_the_newest_videos_with_the_contract_fields_only():
    r = videos(api())
    assert r.status_code == 200, r.text
    body = r.json()
    assert [v["id"] for v in body["data"]] == EXPECTED_ORDER
    assert body["meta"]["sort"] == "published_at" and body["meta"]["total"] == 5
    assert body["meta"]["has_more"] is False and body["meta"]["demo"] is True
    assert body["meta"]["notes"][0].startswith("Newest collected videos of this creator")
    first = body["data"][0]
    assert set(first) == {
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
    assert first["metrics"]["likes"] is None and first["metrics"]["comments"] is None
    assert first["derived"] == {"engagement_rate": None, "views_per_hour_lifetime": None}
    assert first["thumbnail_url"] is None and first["duration_seconds"] is None
    assert first["metrics"]["views"]["kind"] == "raw" and first["metrics"]["views"]["collected_at"] is None


def test_the_raw_upstream_response_is_never_exposed():
    r = videos(api())
    found = keys(r.json())
    assert not found & FORBIDDEN_KEYS
    text = r.text
    for value in ("115.4", "87.1", "cooling", "0.67", "9.9", "12.5", "410.7"):
        assert value not in text
    assert FOUNDATION_NOTE not in text


def test_a_hidden_view_count_is_null_and_a_missing_date_is_null():
    by_id = {v["id"]: v for v in videos(api()).json()["data"]}
    assert by_id["fvid011"]["metrics"]["views"] is None
    assert by_id["fvid040"]["published_at"] is None
    assert by_id["fvid029"]["metrics"]["views"]["value"] == 69222


def test_pages_are_consecutive_slices_of_the_sorted_window():
    c = api()
    pages = [videos(c, f"?page={n}&page_size=2").json() for n in (1, 2, 3)]
    ids = [v["id"] for p in pages for v in p["data"]]
    assert ids == EXPECTED_ORDER
    assert [p["meta"]["has_more"] for p in pages] == [True, True, False]
    assert [p["meta"]["returned"] for p in pages] == [2, 2, 1]
    assert pages[2]["meta"]["total"] == 5


def test_the_window_is_bounded_and_a_page_beyond_it_is_refused_before_any_request():
    nf = Foundation(routes={VELOCITY: "channel_velocity.json"})
    r = videos(api(nf), "?page=9&page_size=24")  # 216 > 200
    assert r.status_code == 422 and r.json()["error"]["code"] == "page_out_of_range"
    assert nf.requests == []
    assert videos(api(), "?page=2&page_size=100").status_code == 200  # exactly 200


def test_period_is_forwarded_and_the_default_is_all():
    nf = Foundation(routes={VELOCITY: "channel_velocity.json"})
    c = api(nf)
    videos(c)
    assert nf.last(VELOCITY).url.params["period"] == "all"
    videos(c, "?period=7d")
    assert nf.last(VELOCITY).url.params["period"] == "7d"


def test_an_unknown_creator_is_404_and_no_video_list_is_requested():
    nf = Foundation(routes={VELOCITY: "channel_velocity.json"})
    r = client(nf).get("/api/v1/creators/UC0000000000000000000z/videos")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    assert not [q for q in nf.requests if q.url.path.endswith("/velocity")]


@pytest.mark.parametrize(
    "query",
    [
        "?period=forever",
        "?period=0d",
        "?page=0",
        "?page_size=0",
        "?page_size=101",
        "?page=201",
        "?platform=facebook",
        "?sort=views_per_hour_24h",
    ],
)
def test_invalid_requests_are_422_or_ignored_never_forwarded(query):
    nf = Foundation(routes={VELOCITY: "channel_velocity.json"})
    r = videos(api(nf), query)
    if query.startswith("?sort"):  # an unknown parameter is not part of the contract
        assert r.status_code == 200 and [v["id"] for v in r.json()["data"]] == EXPECTED_ORDER
        assert "sort_by" not in str(nf.last(VELOCITY).url)
    else:
        assert r.status_code == 422
        assert not [q for q in nf.requests if q.url.path.endswith("/velocity")]


@pytest.mark.parametrize("creator", ["a.b", "a" * 65, "x y"])
def test_an_unsafe_creator_id_is_refused(creator):
    assert api().get(f"/api/v1/creators/{creator}/videos").status_code in (404, 422)


@pytest.mark.parametrize("platform", ["instagram", "tiktok"])
def test_unavailable_platforms_are_refused_for_creator_videos(platform):
    nf = Foundation()
    r = client(nf).get(f"/api/v1/creators/{CHANNEL}/videos?platform={platform}")
    assert r.status_code == 422 and r.json()["error"]["code"] == "platform_unavailable" and nf.requests == []


@pytest.mark.parametrize("fail,status", [(httpx.ConnectError, 503), (httpx.ReadTimeout, 504)])
def test_foundation_failures_map_to_clear_errors(fail, status):
    r = videos(client(Foundation(fail=fail)))
    assert r.status_code == status and "nf.internal" not in r.text and "/velocity" not in r.text


def test_a_malformed_velocity_answer_is_502():
    nf = Foundation(routes={VELOCITY: {"videos": [{"title": "no id"}]}})
    r = videos(client(nf))
    assert r.status_code == 502 and r.json()["error"]["code"] == "provider_error"


def test_synthetic_data_is_labelled_demo_and_refused_as_real():
    assert videos(api(origin="demo")).json()["meta"]["data_origin"] == "demo"
    assert videos(api(origin="real")).status_code == 502


def test_the_creator_detail_points_to_the_videos_and_says_what_it_shows():
    note = client().get(f"/api/v1/creators/{CHANNEL}").json()["data"]["notes"][0]
    assert "/api/v1/creators/{creator_id}/videos" in note and "null when hidden or not reported" in note


def test_the_capabilities_list_the_creator_videos_capability():
    platforms = {p["platform"]: p for p in client().get("/api/v1/capabilities").json()["platforms"]}
    caps = {c["name"]: c["supported"] for c in platforms["youtube"]["capabilities"]}
    assert caps["creator_content"] is True


def test_only_get_is_routed_for_creator_videos():
    c = api()
    assert c.post(f"/api/v1/creators/{CHANNEL}/videos").status_code == 405
    assert c.delete(f"/api/v1/creators/{CHANNEL}/videos").status_code == 405


def test_creator_videos_are_documented_in_openapi_with_errors():
    spec = client().get("/openapi.json").json()
    op = spec["paths"]["/api/v1/creators/{creator_id}/videos"]["get"]
    assert {"200", "404", "422", "502", "503", "504"} <= set(op["responses"])
    names = {p["name"] for p in op["parameters"]}
    assert names == {"creator_id", "period", "platform", "page", "page_size"}
    assert "sort" not in names


# ---- real foundation (PostgreSQL) -----------------------------------------------------------------------


@pytest.mark.postgres
def test_integration_creator_videos_on_the_real_foundation_are_policy_clean_and_sorted(
    real_foundation,  # noqa: F811
):
    creators = real_foundation.get("/api/v1/creators?period=all&page_size=50").json()
    assert creators["data"]
    checked = 0
    for entry in creators["data"]:
        cid = entry["creator"]["id"]
        r = real_foundation.get(f"/api/v1/creators/{cid}/videos?period=all&page_size=50")
        assert r.status_code == 200, r.text
        body = r.json()
        assert not keys(body) & FORBIDDEN_KEYS
        dated = [v["published_at"] for v in body["data"] if v["published_at"]]
        assert dated == sorted(dated, reverse=True)
        assert all(v["creator"]["id"] == cid and v["metrics"]["likes"] is None for v in body["data"])
        checked += len(body["data"])
    assert checked > 0


@pytest.mark.postgres
def test_integration_an_unknown_creator_is_404_on_the_real_foundation(real_foundation):  # noqa: F811
    r = real_foundation.get("/api/v1/creators/UCzzzzzzzzzzzzzzzzzzzzzz/videos")
    assert r.status_code == 404
