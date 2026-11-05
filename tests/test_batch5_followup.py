"""Batch 5 follow-up: ingested_at (UTC), unknown collected_at, and the collection timeout."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.test_ingestion import COLLECT_CHANNEL, ENABLED, Foundation, health, make
from tests.test_youtube_provider import Recorder, make_provider
from viraltrack.config import load_settings
from viraltrack.domain import (
    DataOrigin,
    Exposure,
    MetricKind,
    Provenance,
    ProviderUnavailable,
)
from viraltrack.providers import SearchQuery
from viraltrack.providers.youtube.mapping import ingested_time

UTC = timezone.utc


def prov(**kw):
    return Provenance("youtube", "s", None, MetricKind.RAW, DataOrigin.TEST, "a", Exposure.ALLOWED, **kw)


# ---- ingested_at --------------------------------------------------------------------------------

def test_ingested_at_defaults_to_unknown_and_collected_at_is_independent():
    p = prov()
    assert p.ingested_at is None and p.collected_at is None


def test_ingested_at_is_normalised_to_utc():
    p = prov(ingested_at=datetime(2026, 11, 4, 22, 38, tzinfo=timezone(timedelta(hours=5))))
    assert p.ingested_at == datetime(2026, 11, 4, 17, 38, tzinfo=UTC)
    assert p.ingested_at.utcoffset() == timedelta(0)


def test_naive_ingested_at_is_refused():
    with pytest.raises(ValueError, match="timezone-aware"):
        prov(ingested_at=datetime(2026, 11, 4, 17, 38))


@pytest.mark.parametrize("value,expected", [
    ("2026-11-04T17:38:33.683039+00:00", datetime(2026, 11, 4, 17, 38, 33, 683039, tzinfo=UTC)),
    ("2026-11-04T17:38:33Z", datetime(2026, 11, 4, 17, 38, 33, tzinfo=UTC)),
    ("2026-11-04T22:38:33+05:00", datetime(2026, 11, 4, 17, 38, 33, tzinfo=UTC)),
    ("2026-11-04T17:38:33", None),        # no offset: unknown, never assumed to be UTC
    ("garbage", None), ("", None), (None, None),
])
def test_ingested_time_parsing(value, expected):
    assert ingested_time(value) == expected


def test_search_results_carry_first_seen_as_ingested_at_and_leave_collected_at_unknown():
    page = make_provider(Recorder()).search_content(SearchQuery(text="x"))
    assert page.items
    for c in page.items:
        for m in c.metrics + c.derived:
            assert m.provenance.collected_at is None          # genuine capture time unavailable
            assert m.provenance.ingested_at is None or m.provenance.ingested_at.utcoffset() == timedelta(0)


def test_first_seen_at_in_the_payload_becomes_ingested_at_on_every_metric(monkeypatch):
    from tests.conftest import load_fixture
    body = load_fixture("search.json")
    body["results"][0]["firstSeenAt"] = "2026-11-04T22:38:33+05:00"
    for r in body["results"][1:]:
        r.pop("firstSeenAt", None)
    raw = httpx.Response(200, json=body).content
    page = make_provider(Recorder(body=raw)).search_content(SearchQuery(text="x"))
    first, others = page.items[0], page.items[1:]
    expected = datetime(2026, 11, 4, 17, 38, 33, tzinfo=UTC)
    assert first.metrics and first.derived
    assert {m.provenance.ingested_at for m in first.metrics + first.derived + (first.creator.followers,)
            if m} == {expected}
    assert all(m.provenance.collected_at is None for m in first.metrics + first.derived)
    assert all(m.provenance.ingested_at is None for c in others for m in c.metrics + c.derived)


# ---- collection timeout ---------------------------------------------------------------------------

def test_default_collection_timeout_is_120_seconds_and_reads_keep_20():
    s = load_settings({})
    assert s.youtube.ingestion.collect_timeout_seconds == 120
    assert s.youtube.timeout_seconds == 20


@pytest.mark.parametrize("bad", ["0", "901", "-1", "slow"])
def test_collection_timeout_is_validated(bad):
    from viraltrack.domain import ConfigError
    with pytest.raises(ConfigError, match="VT_YOUTUBE_COLLECT_TIMEOUT_SECONDS"):
        load_settings({"VT_YOUTUBE_COLLECT_TIMEOUT_SECONDS": bad})


def test_collection_timeout_is_configurable():
    s = load_settings({"VT_YOUTUBE_COLLECT_TIMEOUT_SECONDS": "300"})
    assert s.youtube.ingestion.collect_timeout_seconds == 300


def test_posts_use_the_collection_timeout_and_gets_use_the_read_timeout():
    seen = []

    def handler(request):
        seen.append((request.method, request.extensions["timeout"]))
        status, body = (200, health()) if request.method == "GET" else (200, COLLECT_CHANNEL)
        return httpx.Response(status, json=body)

    settings = load_settings({"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test", "VT_YOUTUBE_DATA_ORIGIN": "test",
                              "VT_YOUTUBE_TIMEOUT_SECONDS": "7",
                              "VT_YOUTUBE_COLLECT_TIMEOUT_SECONDS": "90", **ENABLED})
    from viraltrack.providers.youtube import YouTubeProvider
    # no injected http client: the provider builds its own, with the read timeout as default
    p = YouTubeProvider(settings.youtube)
    p._client._http = httpx.Client(transport=httpx.MockTransport(handler), timeout=7)
    p.collect_creator("@synthetic")
    p.close()
    get = next(t for m, t in seen if m == "GET")
    post = next(t for m, t in seen if m == "POST")
    assert get["read"] == 7 and post["read"] == 90 and post["connect"] == 90


def test_a_timed_out_collection_is_never_retried_and_charges_nothing_twice():
    f = Foundation()
    state = {"posts": 0}

    def handler(request):
        if request.method == "POST":
            state["posts"] += 1
            raise httpx.ReadTimeout("slow", request=request)
        return f(request)

    p = make(handler, ENABLED)
    with pytest.raises(ProviderUnavailable, match="timed out|slow"):
        p.collect_creator("@synthetic")
    assert state["posts"] == 1                       # exactly one attempt
    with pytest.raises(ProviderUnavailable):         # a second call is the caller's decision
        p.collect_query("cooking")
    assert state["posts"] == 2

