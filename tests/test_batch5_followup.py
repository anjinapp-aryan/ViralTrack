"""Batch 5 follow-up: foundation_first_seen_at (UTC), unknown collected_at, collection timeout semantics."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.conftest import load_fixture
from tests.test_ingestion import COLLECT_CHANNEL, ENABLED, Foundation, health, make
from tests.test_youtube_provider import NOW, Recorder, make_provider
from viraltrack.config import load_settings
from viraltrack.domain import (
    ConfigError,
    DataOrigin,
    Exposure,
    MetricKind,
    Provenance,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
)
from viraltrack.providers import DiscoveryQuery, SearchQuery
from viraltrack.providers.youtube import YouTubeProvider
from viraltrack.providers.youtube.mapping import foundation_first_seen_time

UTC = timezone.utc


def prov(**kw):
    return Provenance("youtube", "s", None, MetricKind.RAW, DataOrigin.TEST, "a", Exposure.ALLOWED, **kw)


def search_page(first_seen):
    """Fixture search results where only the first item has the given firstSeenAt."""
    body = load_fixture("search.json")
    body["results"][0]["firstSeenAt"] = first_seen
    for r in body["results"][1:]:
        r.pop("firstSeenAt", None)
    raw = httpx.Response(200, json=body).content
    return make_provider(Recorder(body=raw)).search_content(SearchQuery(text="x"))


def all_metrics(content):
    return content.metrics + content.derived + tuple(
        m for m in (content.creator.followers, content.creator.content_count) if m)


# ---- foundation_first_seen_at ------------------------------------------------------------------------

def test_unknown_by_default_and_independent_of_collected_at():
    p = prov()
    assert p.foundation_first_seen_at is None and p.collected_at is None


def test_normalised_to_utc():
    p = prov(foundation_first_seen_at=datetime(2026, 11, 4, 22, 38, tzinfo=timezone(timedelta(hours=5))))
    assert p.foundation_first_seen_at == datetime(2026, 11, 4, 17, 38, tzinfo=UTC)
    assert p.foundation_first_seen_at.utcoffset() == timedelta(0)


def test_naive_value_is_refused():
    with pytest.raises(ValueError, match="timezone-aware"):
        prov(foundation_first_seen_at=datetime(2026, 11, 4, 17, 38))


def test_the_old_ingested_at_name_is_gone():
    """`ingested_at` implied ViralTrack ingestion time. It was never released; no alias is kept."""
    with pytest.raises(TypeError):
        prov(ingested_at=datetime(2026, 11, 4, tzinfo=UTC))
    assert not hasattr(prov(), "ingested_at")


@pytest.mark.parametrize("value,expected", [
    ("2026-11-04T17:38:33.683039+00:00", datetime(2026, 11, 4, 17, 38, 33, 683039, tzinfo=UTC)),
    ("2026-11-04T17:38:33Z", datetime(2026, 11, 4, 17, 38, 33, tzinfo=UTC)),
    ("2026-11-04T22:38:33+05:00", datetime(2026, 11, 4, 17, 38, 33, tzinfo=UTC)),
    ("2026-11-04T17:38:33", None),        # no offset: unknown, never assumed to be UTC
    ("garbage", None), ("", None), (None, None),
])
def test_first_seen_parsing(value, expected):
    assert foundation_first_seen_time(value) == expected


def test_payload_first_seen_lands_on_every_metric_and_never_on_collected_at():
    first = search_page("2026-11-04T22:38:33+05:00").items[0]
    metrics = all_metrics(first)
    assert metrics
    expected = datetime(2026, 11, 4, 17, 38, 33, tzinfo=UTC)
    assert {m.provenance.foundation_first_seen_at for m in metrics} == {expected}
    assert all(m.provenance.collected_at is None for m in metrics)      # not populated from firstSeenAt


def test_items_without_a_usable_first_seen_stay_unknown():
    page = search_page("2026-11-04T17:38:33")           # no offset
    for c in page.items:
        assert all(m.provenance.foundation_first_seen_at is None for m in c.metrics + c.derived)
        assert all(m.provenance.collected_at is None for m in c.metrics + c.derived)


def test_viraltrack_receive_time_is_retrieved_at_and_is_not_the_foundation_timestamp():
    first = search_page("2020-01-01T00:00:00+00:00").items[0]
    assert first.retrieved_at == NOW                                    # the provider clock
    assert first.metrics[0].provenance.foundation_first_seen_at != first.retrieved_at
    assert first.metrics[0].provenance.collected_at is None


# ---- collection timeout: configuration -----------------------------------------------------------------

def test_default_collection_timeout_is_120_seconds_and_reads_keep_20():
    s = load_settings({})
    assert s.youtube.ingestion.collect_timeout_seconds == 120
    assert s.youtube.timeout_seconds == 20


@pytest.mark.parametrize("bad", ["0", "901", "-1", "slow"])
def test_collection_timeout_is_validated(bad):
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
    p = YouTubeProvider(settings.youtube)          # builds its own client, read timeout as its default
    p._client._http = httpx.Client(transport=httpx.MockTransport(handler), timeout=7)
    p.collect_creator("@synthetic")
    p.close()
    get = next(t for m, t in seen if m == "GET")
    post = next(t for m, t in seen if m == "POST")
    assert get["read"] == 7 and post["read"] == 90 and post["connect"] == 90


# ---- collection timeout: error semantics, no retry, no secrets -------------------------------------------

def timing_out(exc_type, executed):
    """A foundation that RUNS the POST (side effect recorded) and then the client gives up."""
    f = Foundation()
    state = {"posts": 0, "gets": 0}

    def handler(request):
        if request.method == "POST":
            state["posts"] += 1
            executed.append(request.url.path)       # the foundation does the work ...
            raise exc_type("client gave up", request=request)     # ... but the client never hears
        state["gets"] += 1
        return f(request)
    return handler, state


def test_client_timeout_is_its_own_error_and_not_a_confirmed_failure():
    executed = []
    handler, state = timing_out(httpx.ReadTimeout, executed)
    with pytest.raises(ProviderTimeout) as caught:
        make(handler, ENABLED).collect_creator("@synthetic")
    err = caught.value
    assert isinstance(err, ProviderUnavailable)             # old `except ProviderUnavailable` still works
    assert err.outcome_unknown is True
    assert err.status is None                               # no HTTP answer was ever received
    assert "not a confirmed failure" in str(err).lower() or "NOT a confirmed failure" in str(err)
    assert "may still complete" in str(err) and "/api/health" in str(err)


def test_the_foundation_may_finish_after_the_client_timed_out_and_it_is_not_retried():
    executed = []
    handler, state = timing_out(httpx.ReadTimeout, executed)
    p = make(handler, ENABLED)
    with pytest.raises(ProviderTimeout):
        p.collect_query("cooking")
    assert executed == ["/api/collect/niche"]               # the operation ran on the foundation side
    assert state["posts"] == 1                              # and ViralTrack sent it exactly once


@pytest.mark.parametrize("call", [lambda p: p.collect_creator("@synthetic"),
                                  lambda p: p.collect_query("cooking"),
                                  lambda p: p.refresh_stats()])
@pytest.mark.parametrize("exc_type", [httpx.ReadTimeout, httpx.WriteTimeout, httpx.ConnectTimeout,
                                      httpx.PoolTimeout, httpx.ConnectError])
def test_no_collection_post_is_ever_retried(call, exc_type):
    handler, state = timing_out(exc_type, [])
    with pytest.raises(ProviderUnavailable):
        call(make(handler, ENABLED))
    assert state["posts"] == 1


def test_a_connect_timeout_says_nothing_was_delivered():
    handler, _ = timing_out(httpx.ConnectTimeout, [])
    with pytest.raises(ProviderTimeout) as caught:
        make(handler, ENABLED).collect_creator("@synthetic")
    assert caught.value.outcome_unknown is False
    assert "not delivered" in str(caught.value)


def test_a_refused_connection_is_unreachable_not_a_timeout():
    handler, _ = timing_out(httpx.ConnectError, [])
    with pytest.raises(ProviderUnavailable) as caught:
        make(handler, ENABLED).collect_creator("@synthetic")
    assert not isinstance(caught.value, ProviderTimeout)


def test_a_confirmed_foundation_failure_is_not_a_timeout():
    f = Foundation({("POST", "/api/collect/channel"): (500, {"detail": "boom"})})
    with pytest.raises(ProviderError) as caught:
        make(f, ENABLED).collect_creator("@synthetic")
    assert not isinstance(caught.value, (ProviderTimeout, ProviderUnavailable))
    assert caught.value.status == 500


def test_a_timed_out_read_is_one_attempt_and_reported_as_a_client_timeout():
    gets = []

    def handler(request):
        gets.append(request.url.path)
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderTimeout):
        make(handler, ENABLED).discover_content(DiscoveryQuery())
    assert len(gets) == 1


def test_timeout_errors_never_contain_the_token_or_the_api_key():
    secret = "tok-SECRET-0123456789"
    key = "AIzaSyFAKEKEY0123456789"
    handler, _ = timing_out(httpx.ReadTimeout, [])
    p = make(handler, {**ENABLED, "VT_YOUTUBE_FOUNDATION_TOKEN": secret, "YOUTUBE_API_KEY": key})
    with pytest.raises(ProviderTimeout) as caught:
        p.collect_creator("@synthetic")
    text = str(caught.value) + repr(caught.value) + repr(caught.value.__cause__)
    assert secret not in text and key not in text
    settings = load_settings({"VT_YOUTUBE_FOUNDATION_TOKEN": secret, "YOUTUBE_API_KEY": key})
    assert secret not in str(settings.describe()) and key not in str(settings.describe())
