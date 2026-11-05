"""D2, foundation-backed tier: the REAL `/api/collect/niche` route, offline.

Every YouTube call is replaced by a fake inside the upstream process
(tests/support/upstream_collect_runner.py); no
key, no network, no quota. Needs VT_TEST_DATABASE_URL and VT_TEST_UPSTREAM_PYTHON; otherwise the tests skip.

Two kinds of test: (1) what ViralTrack's `period` produces at the foundation, with the adapter's own request
body; (2) pins of the foundation's period behaviour that the D2 specification relies on, so a moved
submodule is noticed.
"""

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.conftest import pg_schema  # noqa: F401  (fixture)
from tests.support.upstream import run_upstream_collect
from tests.test_ingestion import ENABLED
from viraltrack.config import load_settings
from viraltrack.providers.youtube import YouTubeProvider

UTC = timezone.utc


def adapter_body(**kwargs) -> dict:
    """The exact JSON body ViralTrack's `collect_query` would POST (recorded; nothing is sent anywhere)."""
    seen = []

    def handler(request):
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "hasApiKey": True,
                    "unitQuota": {"unitsToday": 0, "dailyLimit": 10000, "unitsLeft": 10000},
                    "searchQuota": {"callsToday": 0, "dailyLimit": 100, "callsLeft": 100},
                },
            )
        return httpx.Response(200, json={})

    settings = load_settings(
        {"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test", "VT_YOUTUBE_DATA_ORIGIN": "test", **ENABLED}
    )
    provider = YouTubeProvider(
        settings.youtube, http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    provider.collect_query("home espresso", **kwargs)
    return json.loads(next(r for r in seen if r.method == "POST").content)


def collect(schema, *bodies, pages_available=1, per_page=2):
    return run_upstream_collect(schema, list(bodies), pages_available=pages_available, per_page=per_page)


def searched(result, index=0):
    calls = [c for c in result["results"][index]["stub_calls"] if c["fn"] == "search_videos"]
    assert calls, "no search call reached the fake"
    return calls


def parse_utc(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def within_window(result, delta: timedelta, index=0):
    """published_after must be (now - delta) at some moment during the call, UTC, whole seconds."""
    call = result["results"][index]
    got = searched(result, index)[0]["published_after"]
    assert got.endswith("Z") and "." not in got
    earliest = datetime.fromtimestamp(call["before"], UTC) - delta - timedelta(seconds=1)
    latest = datetime.fromtimestamp(call["after"], UTC) - delta
    assert earliest <= parse_utc(got) <= latest, (got, earliest, latest)
    return got


# ---- ViralTrack's period reaches search.list as publishedAfter ----


@pytest.mark.parametrize(
    "period,delta",
    [
        ("1h", timedelta(hours=1)),
        ("24h", timedelta(hours=24)),
        ("7d", timedelta(days=7)),
        ("30d", timedelta(days=30)),
        ("9999h", timedelta(hours=9999)),
        ("365d", timedelta(days=365)),
    ],
)
def test_the_period_becomes_a_utc_published_after_of_now_minus_the_window(pg_schema, period, delta):  # noqa: F811
    _conn, schema = pg_schema
    result = collect(schema, adapter_body(period=period))
    assert result["results"][0]["status"] == 200
    within_window(result, delta)


@pytest.mark.parametrize("kwargs", [{}, {"period": None}, {"period": "all"}])
def test_no_period_and_all_apply_no_publication_limit(pg_schema, kwargs):  # noqa: F811
    _conn, schema = pg_schema
    body = adapter_body(**kwargs)
    assert "period" not in body  # ViralTrack sends nothing for these
    result = collect(schema, body)
    assert searched(result)[0]["published_after"] is None
    assert result["results"][0]["body"]["min_upload_date"] is None


def test_the_echoed_min_upload_date_is_what_search_received_and_feeds_applied_since(pg_schema):  # noqa: F811
    _conn, schema = pg_schema
    result = collect(schema, adapter_body(period="7d"))
    answer = result["results"][0]["body"]
    sent = searched(result)[0]["published_after"]
    assert answer["min_upload_date"] == sent
    # replay the foundation's real answer through ViralTrack: applied_since is that exact moment, as UTC
    settings = load_settings(
        {"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test", "VT_YOUTUBE_DATA_ORIGIN": "test", **ENABLED}
    )

    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "hasApiKey": True,
                    "unitQuota": {"unitsLeft": 10000, "dailyLimit": 10000},
                    "searchQuota": {"callsLeft": 100, "dailyLimit": 100},
                },
            )
        return httpx.Response(200, json=answer)

    provider = YouTubeProvider(
        settings.youtube, http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    got = provider.collect_query("home espresso", period="7d")
    assert got.applied_since == parse_utc(sent)
    assert got.applied_since.utcoffset() == timedelta(0)


def test_a_collection_without_a_window_has_no_applied_since(pg_schema):  # noqa: F811
    _conn, schema = pg_schema
    answer = collect(schema, adapter_body())["results"][0]["body"]
    from viraltrack.providers.youtube import ingestion

    assert (
        ingestion.collect_result("collect_query", answer, datetime(2026, 11, 5, tzinfo=UTC)).applied_since
        is None
    )


def test_the_search_order_is_fixed_by_the_foundation_to_view_count(pg_schema):  # noqa: F811
    """Documented limit: the route cannot be asked for another order: 'most viewed inside the window'."""
    _conn, schema = pg_schema
    call = searched(collect(schema, adapter_body(period="24h")))[0]
    assert (
        call["order"] == "viewCount" and call["video_duration"] is None and call["video_category_id"] is None
    )


def test_region_and_language_still_reach_search_unchanged(pg_schema):  # noqa: F811
    _conn, schema = pg_schema
    call = searched(collect(schema, adapter_body(period="24h", region="US", language="en")))[0]
    assert (call["region_code"], call["relevance_language"]) == ("US", "en")


# ---- niche identity: one query, one niche, whatever the period ----


def test_different_periods_write_into_the_same_niche(pg_schema):  # noqa: F811
    _conn, schema = pg_schema
    result = collect(
        schema,
        adapter_body(),
        adapter_body(period="24h"),
        adapter_body(period="30d"),
        pages_available=1,
        per_page=2,
    )
    assert [r["status"] for r in result["results"]] == [200, 200, 200]
    assert [n["slug"] for n in result["niches"]] == ["home-espresso"]
    assert {r["body"]["niche"] for r in result["results"]} == {"home-espresso"}


# ---- pagination, duplicates, quota report ----


def test_pages_are_followed_and_ids_repeated_across_pages_are_stored_once(pg_schema):  # noqa: F811
    _conn, schema = pg_schema
    result = collect(schema, {**adapter_body(period="7d"), "pages": 3}, pages_available=3, per_page=2)
    calls = searched(result)
    assert [c["page_token"] for c in calls] == [None, "1", "2"]
    assert len({c["published_after"] for c in calls}) == 1  # one cutoff for the whole collection
    body = result["results"][0]["body"]
    assert body["videos_found"] == 4  # 6 results, 2 repeats removed
    assert body["videos_stored"] == 4
    assert body["quota"]["search_calls"] == 3


def test_a_single_page_reports_one_search_call(pg_schema):  # noqa: F811
    _conn, schema = pg_schema
    quota = collect(schema, adapter_body(period="7d"))["results"][0]["body"]["quota"]
    assert quota["search_calls"] == 1 and quota["units_from_shared_pool"] >= 1


# ---- the foundation's own period contract, pinned (what the spec relies on) ----


@pytest.mark.parametrize("raw", [None, "", "all", "ALL", "alltime"])
def test_foundation_reads_empty_null_and_all_as_no_limit(pg_schema, raw):  # noqa: F811
    _conn, schema = pg_schema
    body = {"query": "home espresso"} if raw is None else {"query": "home espresso", "period": raw}
    assert searched(collect(schema, body))[0]["published_after"] is None


@pytest.mark.parametrize(
    "raw,delta",
    [
        ("7D", timedelta(days=7)),
        ("24H", timedelta(hours=24)),
        ("week", timedelta(days=7)),
        ("month", timedelta(days=30)),
        ("1m", timedelta(days=30)),
        ("2w", timedelta(days=14)),
        ("day", timedelta(hours=24)),
        (" 7d ", timedelta(days=7)),
    ],
)
def test_foundation_accepts_spellings_that_viraltrack_rejects(pg_schema, raw, delta):  # noqa: F811
    """Why the adapter does not rely on the foundation to validate: it is wider, and `m` means 30 days."""
    _conn, schema = pg_schema
    result = collect(schema, {"query": "home espresso", "period": raw})
    within_window(result, delta)


def test_foundation_accepts_a_zero_window_and_spends_a_search_call_on_it(pg_schema):  # noqa: F811
    _conn, schema = pg_schema
    result = collect(schema, {"query": "home espresso", "period": "0h"})
    assert result["results"][0]["status"] == 200
    within_window(result, timedelta(0))  # publishedAfter is 'now'
    assert len(searched(result)) == 1


@pytest.mark.parametrize("raw", ["garbage", "10x", "-1d", "1.5d", "d"])
def test_foundation_fails_an_invalid_period_before_any_search_and_before_creating_the_niche(pg_schema, raw):  # noqa: F811
    _conn, schema = pg_schema
    result = collect(schema, {"query": "invalid period niche", "period": raw})
    one = result["results"][0]
    assert one["status"] == 500 and one["body"]["error"] == "ValueError"
    assert one["stub_calls"] == []  # nothing reached search, videos or channels
    assert result["niches"] == []  # not even the niche row was created
