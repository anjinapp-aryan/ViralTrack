"""D1-A: adapter parameter semantics (offline; no network, no database, no credentials).

These tests began as `xfail(strict=True)` markers for verified defects of the adapter (see
docs/phase-3/YOUTUBE_DISCOVERY_AUDIT.md). D3 and the F-1/F-2 fix resolved every one of them, so none
remains and the CI gate (tests/support/ci_checks.py) expects no xfail at all. A new known defect would
be added as a strict xfail and listed there in the same change.
"""

import json
import re
from pathlib import Path

import httpx
import pytest

from tests.test_youtube_provider import Recorder, make_provider
from viraltrack.domain import ProviderError, ProviderTimeout
from viraltrack.providers import DiscoveryQuery
from viraltrack.providers.youtube.client import FoundationClient

ROOT = Path(__file__).resolve().parent.parent


def viral_params(query: DiscoveryQuery) -> dict:
    rec = Recorder()
    make_provider(rec).discover_content(query)
    request = next(r for r in rec.requests if r.url.path == "/api/viral")
    return dict(request.url.params)


# ---- the root-cause regression ----


def test_an_unset_subscriber_filter_must_not_fall_back_to_the_foundation_default():
    """F-1: fixed; was a strict xfail. Unset is the approved bounded maximum, never the upstream 10,000."""
    assert viral_params(DiscoveryQuery())["max_subscribers"] == "1000000"


def test_an_unset_minimum_views_filter_must_not_fall_back_to_the_foundation_default():
    """F-1: fixed; was a strict xfail. Unset is 0, which the foundation treats as 'no views filter'."""
    assert viral_params(DiscoveryQuery())["min_views"] == "0"


def test_the_batch_5_query_sends_every_threshold_explicitly():  # F-1/F-2: fixed; was a strict xfail
    """The exact query of the Batch 5 discovery call."""
    sent = viral_params(DiscoveryQuery(period="30d", limit=100, sort="views"))
    assert {"max_subscribers", "min_views", "min_views_per_subscriber"} <= set(sent)


def test_the_restricted_views_per_subscriber_default_is_already_neutralised():
    """The one default the adapter does handle: it is sent as 0, which the foundation treats as 'off'."""
    assert viral_params(DiscoveryQuery())["min_views_per_subscriber"] == "0"


# ---- how the client serialises ----


def test_the_client_drops_none_parameters_and_keeps_falsy_ones():
    """This is the mechanism of the defect: None is dropped, 0 is kept."""
    seen = []

    def handler(request):
        seen.append(dict(request.url.params))
        return httpx.Response(200, json={})

    client = FoundationClient(
        "http://nf.test", http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    client.get("/api/viral", {"a": None, "b": 0, "c": "", "d": False, "e": 5})
    assert seen == [{"b": "0", "c": "", "d": "false", "e": "5"}]


@pytest.mark.parametrize(
    "field,value,param",
    [
        ("max_creator_followers", 5000, "max_subscribers"),
        ("min_views", 10, "min_views"),
        ("limit", 1, "limit"),
        ("limit", 24, "limit"),
        ("limit", 100, "limit"),
        ("region", "US", "region"),
        ("niche", "cooking", "niche"),
        ("period", "7d", "period"),
    ],
)
def test_explicit_values_are_sent_verbatim(field, value, param):
    assert viral_params(DiscoveryQuery(**{field: value}))[param] == str(value)


def test_an_explicit_zero_is_sent_as_zero_and_means_at_most_zero_subscribers_upstream():
    """`max_creator_followers=0` is NOT 'no limit'. It is sent as 0, and the foundation then keeps
    only channels with 0 or hidden subscribers (proved in test_discovery_d1_upstream.py).
    Never use 0 to mean unbounded."""
    params = viral_params(DiscoveryQuery(max_creator_followers=0, min_views=0))
    assert params["max_subscribers"] == "0" and params["min_views"] == "0"


def test_unset_optional_parameters_are_omitted_not_sent_empty():
    params = viral_params(DiscoveryQuery())
    assert "region" not in params and "niche" not in params
    assert all(value != "" and value != "None" for value in params.values())


# ---- the plan must not teach the mistake ----


def test_no_document_uses_zero_to_disable_the_subscriber_filter():
    """Flags a query that writes 0 as the subscriber bound (code or URL) unless the line calls it wrong."""
    as_a_query = re.compile(
        r"DiscoveryQuery\([^)]*max_creator_followers\s*=\s*0(?!\d)|[?&]max_subscribers=0(?!\d)"
    )
    disclaimer = re.compile(
        r"(?<!\w)(never|not|wrong|mistake|incorrect|removes|keeps only|at most)(?!\w)", re.I
    )
    offenders = []
    for path in (ROOT / "docs").rglob("*.md"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if as_a_query.search(line) and not disclaimer.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []


# ---- results, counts and failures ----


def page(body: dict):
    return make_provider(Recorder(body=json.dumps(body).encode())).discover_content(DiscoveryQuery())


def video(n: int, **over) -> dict:
    base = {
        "videoId": f"D1V{n:08d}",
        "channelId": f"UCD1C{1:019d}",
        "title": "t",
        "views": 100,
        "likes": 5,
        "comments": 1,
        "vphLifetime": 1.5,
        "publishedAt": "2026-11-01T00:00:00Z",
    }
    return {**base, **over}


@pytest.mark.parametrize("matched", [None, "25", 2.5, [3]])
def test_an_unknown_or_malformed_total_stays_unknown(matched):
    body = {"results": [video(1)]}
    if matched is not None:
        body["matched"] = matched
    assert page(body).total is None


def test_a_boolean_total_is_not_a_count():  # D3-04: fixed; was a strict xfail
    assert page({"matched": True, "results": [video(1)]}).total is None


def test_a_known_total_is_passed_through_and_never_inferred_from_the_page():
    result = page({"matched": 25, "results": [video(1), video(2)]})
    assert result.total == 25 and len(result.items) == 2  # the limit did not change the reported total


def test_without_a_total_the_page_length_is_not_reported_as_the_total():
    assert page({"results": [video(1), video(2)]}).total is None


def test_an_empty_result_is_a_normal_page_with_the_foundations_hint():
    result = page({"matched": 0, "results": [], "hint": "filter X removed all 3 videos"})
    assert result.items == () and result.total == 0 and result.notes == ("filter X removed all 3 videos",)


def test_one_result_and_many_results_map_one_to_one():
    assert len(page({"matched": 1, "results": [video(1)]}).items) == 1
    many = page({"matched": 30, "results": [video(n) for n in range(1, 31)]})
    assert [c.content_id for c in many.items] == [f"D1V{n:08d}" for n in range(1, 31)]


@pytest.mark.parametrize("status", [500, 502, 503])
def test_a_foundation_failure_is_a_typed_error_with_its_status(status):
    with pytest.raises(ProviderError) as caught:
        make_provider(Recorder(status=status, body=b'{"detail": "boom"}')).discover_content(DiscoveryQuery())
    assert caught.value.status == status


def test_a_response_without_results_is_an_error_not_an_empty_page():
    with pytest.raises(ProviderError, match="no results"):
        page({"matched": 3})


def test_a_client_timeout_on_a_read_is_one_attempt_and_a_timeout_error():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        raise httpx.ReadTimeout("slow", request=request)

    from tests.test_ingestion import make

    with pytest.raises(ProviderTimeout):
        make(handler).discover_content(DiscoveryQuery())
    assert calls == ["/api/viral"]


def test_invalid_candidate_ids_are_rejected_loudly_for_real_data():
    from viraltrack.config import load_settings
    from viraltrack.providers.youtube import YouTubeProvider

    settings = load_settings(
        {"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test", "VT_YOUTUBE_DATA_ORIGIN": "real"}
    )
    body = json.dumps({"results": [video(1, videoId="not-a-real-id")]}).encode()
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body)))
    with pytest.raises(ProviderError, match="not a YouTube video id"):
        YouTubeProvider(settings.youtube, http_client=client).discover_content(DiscoveryQuery())


def test_a_candidate_without_ids_is_an_error():
    with pytest.raises(ProviderError, match="without videoId"):
        page({"results": [{"title": "no ids"}]})


def test_invalid_entries_are_not_silently_dropped():
    """D3-02: fixed; was a strict xfail. The contract is now stricter than a note: the response is refused."""
    with pytest.raises(ProviderError, match=r"results\[1\]"):
        page({"matched": 3, "results": [video(1), "garbage", None]})


def test_duplicate_video_ids_in_one_response_are_collapsed_or_flagged():  # D3-03: fixed; was a strict xfail
    result = page({"matched": 2, "results": [video(1), video(1)]})
    assert len({c.content_id for c in result.items}) == len(result.items) == 1 and result.notes


def test_the_foundations_funnel_reaches_the_caller():  # D3-01: fixed; was a strict xfail
    body = {
        "matched": 0,
        "results": [],
        "funnel": [
            {"step": "videos in window", "remaining": 3},
            {"step": "channel subs <= 10,000", "remaining": 0},
        ],
    }
    assert getattr(page(body), "funnel", None)
