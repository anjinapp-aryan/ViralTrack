"""Phase 3 D3: regression tests for the seven discovery defect fixes (offline; no network, no database).

Every test feeds a synthetic foundation response to the real adapter through an `httpx` mock transport.
Clock: the provider's clock is fixed at 2026-11-03 12:00 UTC (`tests.test_youtube_provider.NOW`).
"""

import json
import re
from pathlib import Path

import pytest

from tests.test_youtube_provider import NOW, Recorder, make_provider
from viraltrack.domain import FunnelStage, ProviderError, RestrictedMetric
from viraltrack.providers import DiscoveryQuery, SearchQuery
from viraltrack.providers.youtube import mapping
from viraltrack.providers.youtube.provider import _SORTS, _SORTS_NEEDING_APPROVAL, MAX_CREATOR_FOLLOWERS

ROOT = Path(__file__).resolve().parent.parent
STAGE = {"step": "videos in window", "remaining": 3}


def video(n: int = 1, **over) -> dict:
    base = {
        "videoId": f"D3V{n:08d}",
        "channelId": f"UCD3C{1:019d}",
        "title": "t",
        "views": 100,
        "likes": 5,
        "comments": 1,
        "vphLifetime": 1.5,
        "vph24h": 2.5,
        "viewsGained24h": 60.0,
        "publishedAt": "2026-11-01T00:00:00Z",
    }
    return {**base, **over}


def run(body: dict, recorder: Recorder | None = None):
    recorder = recorder or Recorder(body=json.dumps(body).encode())
    return make_provider(recorder).discover_content(DiscoveryQuery())


def item(**over):
    return run({"results": [video(**over)]}).items[0]


def names(content) -> set[str]:
    return {m.name for m in content.metrics + content.derived}


# ---- D3-01: the funnel ----


def test_a_complete_funnel_is_preserved_in_order_with_its_counts():
    steps = [
        {"step": "videos in window", "remaining": 9},
        {"step": "channel subs <= 10,000", "remaining": 4},
        {"step": "video views >= 10,000", "remaining": 0},
    ]
    page = run({"matched": 0, "results": [], "funnel": steps})
    assert page.funnel == tuple(FunnelStage(s["step"], s["remaining"]) for s in steps)
    assert [s.remaining for s in page.funnel] == [9, 4, 0]


def test_a_partial_funnel_is_passed_on_as_it_is_and_nothing_is_added():
    page = run({"results": [video()], "funnel": [STAGE]})
    assert page.funnel == (FunnelStage("videos in window", 3),) and page.notes == ()


def test_a_missing_funnel_is_unknown_not_empty():
    page = run({"results": [video()]})
    assert page.funnel is None and page.notes == ()


def test_an_empty_funnel_is_reported_empty_which_is_not_the_same_as_unknown():
    page = run({"results": [], "funnel": []})
    assert page.funnel == () and page.funnel is not None


def test_a_null_funnel_is_unknown():
    assert run({"results": [], "funnel": None}).funnel is None


def test_a_stage_with_zero_remaining_is_kept_as_a_real_zero():
    page = run({"results": [], "funnel": [{"step": "videos in window", "remaining": 0}]})
    assert page.funnel == (FunnelStage("videos in window", 0),)


@pytest.mark.parametrize("funnel", ["rows", 5, {"step": "x", "remaining": 1}, True])
def test_a_funnel_that_is_not_a_list_is_unusable_and_says_so(funnel):
    page = run({"results": [video()], "funnel": funnel})
    assert page.funnel is None and any("malformed" in n for n in page.notes)


@pytest.mark.parametrize(
    "stage",
    [
        "garbage",
        None,
        {"step": "x"},
        {"remaining": 1},
        {"step": 7, "remaining": 1},
        {"step": "x", "remaining": "3"},
        {"step": "x", "remaining": 3.0},
        {"step": "x", "remaining": -1},
        {"step": "x", "remaining": None},
        {"step": "x", "remaining": True},
        {"step": "x", "remaining": False},
        {"step": "x", "remaining": [1]},
    ],
)
def test_one_invalid_stage_makes_the_whole_funnel_unusable_instead_of_dropping_the_stage(stage):
    page = run({"results": [video()], "funnel": [STAGE, stage]})
    assert page.funnel is None and any("invalid stage" in n for n in page.notes)
    assert len(page.items) == 1  # the videos themselves are unaffected


@pytest.mark.parametrize(
    "step", ["views per subscriber >= 1.0", "outlier score >= 3", "Viral score", "acceleration"]
)
def test_a_funnel_stage_naming_a_restricted_metric_is_withheld(step):
    page = run({"results": [video()], "funnel": [STAGE, {"step": step, "remaining": 1}]})
    assert page.funnel is None and any("restricted" in n for n in page.notes)
    assert not any(step in n for n in page.notes)


def test_a_hint_that_names_a_restricted_metric_is_dropped():
    leaked = "filter 'views per subscriber >= 1' removed all 3 videos"
    assert run({"results": [], "hint": leaked}).notes == ()
    assert run({"results": [], "hint": "filter X removed all 3 videos"}).notes == (
        "filter X removed all 3 videos",
    )


def test_the_recorded_foundation_responses_still_map_and_have_no_funnel_stage_with_a_restricted_name():
    page = make_provider(Recorder()).discover_content(DiscoveryQuery())
    assert page.items and (
        page.funnel is None or not any(mapping.mentions_restricted_metric(s.step) for s in page.funnel)
    )


@pytest.mark.parametrize("remaining", [True, -1, 1.5, "1", None])
def test_the_funnel_stage_type_rejects_what_is_not_a_count(remaining):
    with pytest.raises(ValueError):
        FunnelStage("x", remaining)


# ---- D3-02: malformed result entries ----


@pytest.mark.parametrize(
    "entry,fragment",
    [
        (None, "must be an object"),
        ("a string", "must be an object"),
        (7, "must be an object"),
        ([], "must be an object"),
        ({"channelId": "UC" + "a" * 22}, "without videoId"),
        ({"videoId": "D3V00000001"}, "without videoId"),
        ({"videoId": "", "channelId": "UCx"}, "without videoId"),
        ({"videoId": 12345678901, "channelId": "UCx"}, "must be text"),
        ({"videoId": "D3V00000001", "channelId": ["UCx"]}, "must be text"),
    ],
)
def test_a_malformed_entry_refuses_the_whole_response_and_names_its_position(entry, fragment):
    with pytest.raises(ProviderError, match=r"results\[1\] is invalid") as caught:
        run({"results": [video(1), entry, video(2)]})
    assert fragment in str(caught.value)


def test_the_diagnostic_names_the_field_and_type_but_never_the_value():
    secret = "SECRET-TOKEN-VALUE"
    with pytest.raises(ProviderError) as caught:
        run({"results": [video(1, title=[secret])]})
    assert "'title'" in str(caught.value) and "list" in str(caught.value) and secret not in str(caught.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", 5),
        ("title", ["x"]),
        ("channelTitle", {"a": 1}),
        ("thumbnail", 3.5),
        ("language", True),
        ("views", "100"),
        ("views", True),
        ("likes", [5]),
        ("comments", {"n": 1}),
        ("channelSubscribers", "9"),
        ("vphLifetime", "1.5"),
        ("vphLifetime", float("inf")),
        ("engagementRate", float("nan")),
    ],
)
def test_a_present_field_of_the_wrong_type_is_malformed_not_silently_missing(field, value):
    with pytest.raises(ProviderError, match=field):
        run({"results": [video(1, **{field: value})]})


@pytest.mark.parametrize(
    "field",
    [
        "title",
        "views",
        "likes",
        "comments",
        "vphLifetime",
        "channelSubscribers",
        "thumbnail",
        "language",
        "lengthSeconds",
    ],
)
def test_an_absent_or_null_optional_field_is_not_malformed_and_stays_missing(field):
    base = video(1)
    for body in ({k: v for k, v in base.items() if k != field}, {**base, field: None}):
        content = run({"results": [body]}).items[0]
        assert content.content_id == base["videoId"]


def test_missing_optional_fields_stay_missing_never_defaulted():
    only_ids = {"videoId": "D3V00000001", "channelId": "UCD3C" + "1".zfill(19)}
    content = run({"results": [only_ids]}).items[0]
    assert content.title is None and content.published_at is None and content.duration_seconds is None
    assert content.metrics == () and content.derived == () and content.creator.followers is None


def test_an_invalid_real_video_id_is_refused_with_its_position():
    import httpx

    from viraltrack.config import load_settings
    from viraltrack.providers.youtube import YouTubeProvider

    settings = load_settings(
        {"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test", "VT_YOUTUBE_DATA_ORIGIN": "real"}
    )
    ok = video(1, videoId="abcdefghijk", channelId="UC" + "a" * 22)
    bad = video(2, videoId="abcdefghijk\n", channelId="UC" + "a" * 22)  # a trailing newline is not an id
    body = json.dumps({"results": [ok, bad]}).encode()
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body)))
    with pytest.raises(ProviderError, match=r"results\[1\] is invalid"):
        YouTubeProvider(settings.youtube, http_client=client).discover_content(DiscoveryQuery())


def test_a_results_value_that_is_not_a_list_is_still_an_error():
    with pytest.raises(ProviderError, match="no results"):
        run({"results": {"a": 1}})


def test_a_mixed_response_is_refused_whole_and_no_partial_page_is_returned():
    with pytest.raises(ProviderError):
        run({"results": [video(1), None, video(2)]})


# ---- D3-03: duplicate video ids ----


def ids(page) -> list[str]:
    return [c.content_id for c in page.items]


def test_no_duplicates_means_no_change_and_no_note():
    page = run({"results": [video(1), video(2), video(3)]})
    assert ids(page) == ["D3V00000001", "D3V00000002", "D3V00000003"] and page.notes == ()


def test_exact_duplicates_are_collapsed_and_counted():
    page = run({"results": [video(1), video(2), video(1)]})
    assert ids(page) == ["D3V00000001", "D3V00000002"]
    assert page.notes == (
        "1 duplicate video id entry dropped (0 with different data); "
        "the first occurrence of each id was kept",
    )


def test_the_first_occurrence_wins_and_conflicting_metadata_is_never_merged():
    page = run(
        {"results": [video(1, title="first", views=10), video(1, title="second", views=999, likes=77)]}
    )
    kept = page.items[0]
    assert kept.title == "first" and kept.metric("views").value == 10 and kept.metric("likes").value == 5
    assert "1 with different data" in page.notes[0]


def test_three_or_more_occurrences_are_all_accounted_for():
    page = run({"results": [video(1), video(1, title="b"), video(1), video(1, title="d")]})
    assert ids(page) == ["D3V00000001"]
    assert page.notes == (
        "3 duplicate video id entries dropped (2 with different data); "
        "the first occurrence of each id was kept",
    )


def test_a_duplicate_with_missing_optional_metadata_does_not_complete_the_first_one():
    sparse = {"videoId": video(1)["videoId"], "channelId": video(1)["channelId"]}
    page = run({"results": [sparse, video(1)]})
    assert page.items[0].title is None and page.items[0].metrics == ()
    page = run({"results": [video(1), sparse]})
    assert page.items[0].title == "t" and "1 with different data" in page.notes[0]


def test_ordering_of_the_survivors_is_the_foundations_order():
    page = run({"results": [video(3), video(1), video(3), video(2), video(1)]})
    assert ids(page) == ["D3V00000003", "D3V00000001", "D3V00000002"]


def test_the_same_title_or_channel_under_different_ids_is_not_a_duplicate():
    page = run({"results": [video(1, title="same"), video(2, title="same")]})
    assert len(page.items) == 2 and page.notes == ()


def test_deduplication_is_idempotent():
    first = run({"results": [video(1), video(2), video(1)]})
    again = run({"results": [json.loads(json.dumps(video(n))) for n in (1, 2)]})
    assert ids(first) == ids(again) and again.notes == ()


def test_the_total_is_the_foundations_figure_and_is_not_recomputed_after_deduplication():
    assert run({"matched": 5, "results": [video(1), video(1)]}).total == 5


# ---- D3-04: boolean (and other non-count) totals ----


@pytest.mark.parametrize(
    "matched,expected",
    [
        (True, None),
        (False, None),
        (0, 0),
        (7, 7),
        (-1, None),
        (2.5, None),
        (3.0, None),
        ("7", None),
        ("", None),
        (None, None),
        ([7], None),
        ({"n": 7}, None),
    ],
)
def test_a_total_is_a_non_negative_integer_or_unknown(matched, expected):
    assert run({"matched": matched, "results": [video(1)]}).total == expected


def test_a_missing_total_is_unknown():
    assert run({"results": [video(1)]}).total is None


@pytest.mark.parametrize(
    "value,expected",
    [(True, None), (False, None), (0, 0), (5, 5), (-5, None), (1.0, None), ("5", None), (None, None)],
)
def test_the_count_helper_used_for_totals_and_funnel_counts(value, expected):
    assert mapping.count(value) == expected


# ---- D3-05: no 24-hour velocity while the snapshot recency is unknown ----


def test_a_24_hour_rate_from_the_foundation_is_not_exposed():
    content = item()
    assert content.metric("views_per_hour_24h") is None and content.metric("views_gained_24h") is None
    assert "24h" not in repr(content)  # nothing in the serialised object carries the label either


def test_no_snapshot_time_means_no_rate_even_when_the_foundation_supplies_one():
    # the only time fields upstream sends are the video's own dates and when the foundation first stored it
    content = item(firstSeenAt="2026-11-02T00:00:00Z")
    assert "views_per_hour_24h" not in names(content)


@pytest.mark.parametrize("clock_difference_hours", [0, 1, 24, 400])
def test_neither_the_response_time_nor_the_collection_time_stands_in_for_a_snapshot_time(
    clock_difference_hours,
):
    from datetime import timedelta

    recorder = Recorder(body=json.dumps({"results": [video()]}).encode())
    provider = make_provider(recorder)
    provider._clock = lambda: NOW + timedelta(hours=clock_difference_hours)
    assert "views_per_hour_24h" not in names(provider.discover_content(DiscoveryQuery()).items[0])


def test_the_lifetime_rate_is_not_substituted_for_the_missing_24_hour_rate():
    content = item()
    assert content.metric("views_per_hour_lifetime").value == 1.5
    assert content.metric("views_per_hour_lifetime").provenance.note  # still labelled as what it is


def test_no_value_is_invented_when_only_the_24_hour_rate_is_present():
    content = item(vphLifetime=None)
    assert "views_per_hour_lifetime" not in names(content) and "views_per_hour_24h" not in names(content)


@pytest.mark.parametrize("sort", ["views_per_hour_24h", "views_gained_24h"])
def test_ordering_by_a_withheld_24_hour_value_is_refused_before_any_request(sort):
    recorder = Recorder()
    for call in (
        lambda p: p.discover_content(DiscoveryQuery(sort=sort)),
        lambda p: p.search_content(SearchQuery(text="x", sort=sort)),
    ):
        with pytest.raises(ValueError, match="snapshot"):
            call(make_provider(recorder))
    assert recorder.requests == []


def test_restricted_velocity_neither_appears_nor_orders_results():
    content = item(acceleration=3.0)
    assert "acceleration" not in names(content)
    recorder = Recorder()
    with pytest.raises(RestrictedMetric):
        make_provider(recorder).discover_content(DiscoveryQuery(sort="acceleration"))
    assert recorder.requests == []


# ---- D3-06: no lifetime velocity without a usable publication date ----


@pytest.mark.parametrize(
    "published",
    [
        None,
        "",
        "not a date",
        "2026-13-45T00:00:00Z",
        "yesterday",
        20261101,
        ["2026-11-01T00:00:00Z"],
        "2026-11-01T00:00:00",
        "2026-11-01",
    ],
)
def test_an_unknown_or_unusable_publication_date_gives_no_lifetime_rate(published):
    content = item(publishedAt=published)
    assert content.published_at is None
    assert "views_per_hour_lifetime" not in names(content)
    assert content.metric("views").value == 100  # raw data is untouched


def test_an_absent_publication_date_gives_no_lifetime_rate():
    body = {k: v for k, v in video().items() if k != "publishedAt"}
    content = run({"results": [body]}).items[0]
    assert content.published_at is None and "views_per_hour_lifetime" not in names(content)


@pytest.mark.parametrize(
    "published,expected_utc",
    [
        ("2026-11-01T00:00:00Z", "2026-11-01T00:00:00+00:00"),
        ("2026-11-01T05:30:00+05:30", "2026-11-01T00:00:00+00:00"),
        ("2026-10-31T19:00:00-05:00", "2026-11-01T00:00:00+00:00"),
    ],
)
def test_a_dated_video_keeps_its_lifetime_rate_and_the_date_is_aware_utc(published, expected_utc):
    content = item(publishedAt=published)
    assert content.published_at.isoformat() == expected_utc
    assert content.metric("views_per_hour_lifetime").value == 1.5


def test_a_publication_date_in_the_future_gives_no_lifetime_rate():
    content = item(publishedAt="2999-01-01T00:00:00Z")
    assert content.published_at is not None and "views_per_hour_lifetime" not in names(content)


def test_a_publication_date_equal_to_the_response_time_is_not_in_the_future():
    assert "views_per_hour_lifetime" in names(item(publishedAt=NOW.isoformat()))


def test_zero_views_on_a_dated_video_is_a_real_zero_rate():
    content = item(views=0, vphLifetime=0.0)
    assert content.metric("views").value == 0 and content.metric("views_per_hour_lifetime").value == 0.0


def test_positive_views_on_a_dated_video_have_their_rate():
    assert item(views=5000, vphLifetime=104.2).metric("views_per_hour_lifetime").value == 104.2


def test_missing_views_give_no_lifetime_rate_even_for_a_dated_video():
    content = item(views=None, vphLifetime=0.0)
    assert "views" not in names(content) and "views_per_hour_lifetime" not in names(content)


def test_an_undated_video_is_not_given_the_current_or_ingestion_time():
    content = item(publishedAt=None, firstSeenAt="2026-11-02T00:00:00Z")
    assert content.published_at is None
    assert content.derived == () or "views_per_hour_lifetime" not in names(content)


def test_the_publication_time_helper():
    assert mapping.published_time("2026-11-01T00:00:00Z").isoformat() == "2026-11-01T00:00:00+00:00"
    for bad in (None, "", 5, "2026-11-01T00:00:00", "x"):
        assert mapping.published_time(bad) is None


# ---- D3-07A: sorting ----


@pytest.mark.parametrize(
    "sort,upstream",
    [
        ("views", "views"),
        ("published_at", "published"),
    ],
)
def test_every_approved_sort_is_sent_as_its_explicit_upstream_name(sort, upstream):
    for call in (
        lambda p: p.discover_content(DiscoveryQuery(sort=sort)),
        lambda p: p.search_content(SearchQuery(text="x", sort=sort)),
    ):
        recorder = Recorder()
        call(make_provider(recorder))
        assert recorder.requests[-1].url.params["sort_by"] == upstream


def test_the_approved_list_is_exactly_the_two_raw_sorts():
    assert set(_SORTS) == {"views", "published_at"}


@pytest.mark.parametrize("sort", ["views_per_hour_lifetime", "vph_lifetime", "VIEWS_PER_HOUR_LIFETIME"])
def test_lifetime_velocity_is_not_a_sort_and_nothing_restores_it(sort):
    """Owner decision: upstream puts an undated video first on an invented rate; refused up front."""
    for call in (
        lambda p: p.discover_content(DiscoveryQuery(sort=sort)),
        lambda p: p.search_content(SearchQuery(text="x", sort=sort)),
    ):
        recorder = Recorder()
        with pytest.raises(ValueError) as caught:
            call(make_provider(recorder))
        assert recorder.requests == []
        expected = "undated" if sort == "views_per_hour_lifetime" else "unknown sort"
        assert expected in str(caught.value)  # the named metric says why; other spellings are just unknown


@pytest.mark.parametrize(
    "sort",
    [
        "viral",
        "viralScore",
        "viral_score",
        "outlier",
        "outlier_score",
        "outlierScore",
        "views_per_subscriber",
        "views_per_follower",
        "vsr",
        "acceleration",
        "outlier_score_age_adjusted",
        "outlier_adjusted",
        "vph",
        "velocity",
        "momentum",
        "relevance",
        "semantic_score",
        "random",
        "",
        " ",
        "VIEWS",
        "views ",
        "views;viral",
        "None",
    ],
)
def test_an_unknown_or_restricted_sort_is_refused_before_any_request(sort):
    for call in (
        lambda p: p.discover_content(DiscoveryQuery(sort=sort)),
        lambda p: p.search_content(SearchQuery(text="x", sort=sort)),
    ):
        recorder = Recorder()
        with pytest.raises((ValueError, RestrictedMetric)):
            call(make_provider(recorder))
        assert recorder.requests == []


@pytest.mark.parametrize("sort", [None, 5, 1.5, ["views"], {"views": 1}, True])
def test_a_sort_that_is_not_text_is_refused_not_looked_up(sort):
    recorder = Recorder()
    with pytest.raises(ValueError, match="must be text"):
        make_provider(recorder).discover_content(DiscoveryQuery(sort=sort))
    assert recorder.requests == []


@pytest.mark.parametrize("sort", sorted(_SORTS_NEEDING_APPROVAL))
def test_a_restricted_sort_stays_refused_without_its_approval(sort):
    recorder = Recorder()
    with pytest.raises(RestrictedMetric):
        make_provider(recorder).discover_content(DiscoveryQuery(sort=sort))
    assert recorder.requests == []


def test_no_sort_value_the_adapter_can_send_is_a_restricted_upstream_default():
    sent = set(_SORTS.values())
    assert sent == {"views", "published"}
    assert not sent & {"viral", "outlier", "outlier_adjusted", "vsr", "acceleration"}


def test_the_default_query_names_its_sort_so_the_foundations_viral_default_is_never_used():
    recorder = Recorder()
    make_provider(recorder).discover_content(DiscoveryQuery())
    assert recorder.requests[0].url.params["sort_by"] == "views"


def test_text_search_does_not_claim_a_popularity_order():
    """The foundation orders a text search by relevance and ignores `sort_by`; ViralTrack still sends and
    validates an explicit one, and documents the order as query relevance only (docs/phase-3/D3 report)."""
    assert SearchQuery().sort == "views"
    recorder = Recorder()
    make_provider(recorder).search_content(SearchQuery(text="cooking"))
    assert recorder.requests[0].url.params["sort_by"] == "views"


# ---- D3-07B: the subscriber bound ----


def test_the_bound_is_one_million():
    assert MAX_CREATOR_FOLLOWERS == 1_000_000


@pytest.mark.parametrize("value", [0, 1, 10_000, 1_000_000])
def test_a_bound_up_to_one_million_is_sent_verbatim(value):
    recorder = Recorder()
    make_provider(recorder).discover_content(DiscoveryQuery(max_creator_followers=value))
    assert recorder.requests[0].url.params["max_subscribers"] == str(value)


@pytest.mark.parametrize("value", [1_000_001, 2_147_483_647, 10**12, -1, True, False, 1.5, "5000", [5]])
def test_a_bound_above_one_million_or_not_a_whole_number_is_refused_before_any_request(value):
    recorder = Recorder()
    with pytest.raises(ValueError, match="bounded limit"):
        make_provider(recorder).discover_content(DiscoveryQuery(max_creator_followers=value))
    assert recorder.requests == []


def test_no_document_calls_the_integer_maximum_or_any_subscriber_bound_unlimited():
    big = re.compile(r"2,?147,?483,?647")
    negation = re.compile(
        r"(?<!\w)(not|never|no|isn't|is not|rather than|instead of|bounded|historic)(?!\w)", re.I
    )
    unbounded = re.compile(r"unbounded|unlimited|no limit|without a limit", re.I)
    offenders = []
    for path in (ROOT / "docs").rglob("*.md"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if big.search(line) and unbounded.search(line) and not negation.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []


# ---- F-1/F-2: explicit thresholds, never the foundation's 10,000 defaults ----


def viral_params(**fields) -> dict:
    recorder = Recorder()
    make_provider(recorder).discover_content(DiscoveryQuery(**fields))
    return dict(next(r for r in recorder.requests if r.url.path == "/api/viral").url.params)


def test_the_exact_request_for_an_unset_query_names_every_threshold():
    sent = viral_params()
    assert sent == {
        "period": "7d",
        "sort_by": "views",
        "limit": "24",
        "max_subscribers": "1000000",
        "min_views": "0",
        "min_views_per_subscriber": "0",
        "only_shorts": "false",
        "exclude_shorts": "false",
    }


def test_the_batch_5_shaped_query_sends_every_threshold_explicitly():
    sent = viral_params(period="30d", limit=100, sort="views")
    assert (sent["max_subscribers"], sent["min_views"], sent["min_views_per_subscriber"]) == (
        "1000000",
        "0",
        "0",
    )


def test_no_implicit_ten_thousand_default_and_no_unlimited_sentinel_is_sent():
    sent = viral_params()
    assert "10000" not in sent.values()
    assert sent["max_subscribers"] != "2147483647" and int(sent["max_subscribers"]) == MAX_CREATOR_FOLLOWERS


@pytest.mark.parametrize("value", [0, 1, 10_000, 999_999, 1_000_000])
def test_a_supplied_subscriber_ceiling_is_sent_verbatim(value):
    assert viral_params(max_creator_followers=value)["max_subscribers"] == str(value)


@pytest.mark.parametrize("value", [0, 1, 10_000, 5_000_000, 10**9])
def test_a_supplied_minimum_views_is_sent_verbatim(value):
    assert viral_params(min_views=value)["min_views"] == str(value)


def test_an_explicit_zero_minimum_views_and_an_unset_one_send_the_same_thing():
    assert viral_params(min_views=0)["min_views"] == viral_params()["min_views"] == "0"


@pytest.mark.parametrize("value", [-1, True, False, 1.5, "100", [1], 10.0])
def test_an_invalid_minimum_views_is_refused_before_any_request(value):
    recorder = Recorder()
    with pytest.raises(ValueError, match="min_views"):
        make_provider(recorder).discover_content(DiscoveryQuery(min_views=value))
    assert recorder.requests == []


def test_an_invalid_filter_is_refused_before_the_health_or_any_other_request_even_with_a_valid_sort():
    recorder = Recorder()
    with pytest.raises(ValueError):
        make_provider(recorder).discover_content(
            DiscoveryQuery(sort="views", max_creator_followers=1_000_001)
        )
    assert recorder.requests == []


def test_no_threshold_is_ever_a_restricted_metric_filter():
    sent = viral_params(max_creator_followers=500, min_views=7)
    assert (
        sent["min_views_per_subscriber"] == "0" and "min_outlier_score" not in sent and "preset" not in sent
    )


# ---- F-6: short_form is a duration filter (<= 180 s inclusive; zero, missing, null, invalid: not short) ----


def by_duration(durations: dict, **fields):
    """Run the adapter over videos with the given durations (an absent key means the field is missing)."""
    results = []
    for n, value in durations.items():
        entry = video(n)
        if value != "absent":
            entry["lengthSeconds"] = value
        results.append(entry)
    recorder = Recorder(body=json.dumps({"matched": len(results), "results": results}).encode())
    page = make_provider(recorder).discover_content(DiscoveryQuery(**fields))
    return page, recorder


DURATIONS = {1: 0, 2: 1, 3: 179, 4: 180, 5: 181, 6: None, 7: "absent", 8: "90", 9: True, 10: -5, 11: 600}


def kept(page) -> list[int]:
    return [int(c.content_id[3:]) for c in page.items]


def test_short_form_true_keeps_only_videos_of_more_than_zero_and_at_most_180_seconds():
    assert kept(by_duration(DURATIONS, short_form=True)[0]) == [2, 3, 4]


def test_short_form_false_keeps_everything_else_including_unknown_and_invalid_durations():
    assert kept(by_duration(DURATIONS, short_form=False)[0]) == [1, 5, 6, 7, 8, 9, 10, 11]


def test_short_form_none_keeps_every_video():
    assert kept(by_duration(DURATIONS)[0]) == list(DURATIONS)


@pytest.mark.parametrize(
    "seconds,short",
    [
        (0, False),
        (1, True),
        (179, True),
        (180, True),
        (181, False),
        (180.0, True),
        (180.5, False),
        (0.5, True),
    ],
)
def test_the_boundary_is_inclusive_at_180_and_zero_is_not_short(seconds, short):
    page, _ = by_duration({1: seconds}, short_form=True)
    assert (len(page.items) == 1) is short
    page, _ = by_duration({1: seconds}, short_form=False)
    assert (len(page.items) == 1) is (not short)


@pytest.mark.parametrize(
    "bad", [None, "absent", "180", "short", True, False, -1, [180], {"s": 1}, float("inf")]
)
def test_an_unknown_null_or_invalid_duration_is_never_short_and_never_malformed(bad):
    # json cannot carry inf; it is checked through the mapper below
    if isinstance(bad, float):
        assert mapping.duration_seconds(bad) is None
        return
    assert by_duration({1: bad}, short_form=True)[0].items == ()
    page, _ = by_duration({1: bad}, short_form=False)
    assert len(page.items) == 1 and page.items[0].duration_seconds is None


def test_the_foundations_is_short_flag_never_decides():
    results = [
        {**video(1), "lengthSeconds": 600, "isShort": True},  # flagged short upstream, but 10 minutes long
        {**video(2), "lengthSeconds": 60, "isShort": False},  # not flagged, but 60 seconds long
        {**video(3), "lengthSeconds": 600, "isShort": False},
    ]
    recorder = Recorder(body=json.dumps({"results": results}).encode())
    assert kept(make_provider(recorder).discover_content(DiscoveryQuery(short_form=True))) == [2]
    recorder = Recorder(body=json.dumps({"results": results}).encode())
    assert kept(make_provider(recorder).discover_content(DiscoveryQuery(short_form=False))) == [1, 3]


@pytest.mark.parametrize("state", [True, False, None])
def test_the_foundations_shorts_filters_are_never_requested(state):
    _, recorder = by_duration(DURATIONS, short_form=state)
    sent = recorder.requests[0].url.params
    assert sent["only_shorts"] == "false" and sent["exclude_shorts"] == "false"


def test_search_applies_the_same_duration_filter_and_sends_no_upstream_filter():
    results = [
        {**video(1), "lengthSeconds": 100},
        {**video(2), "lengthSeconds": 181},
        {**video(3), "lengthSeconds": 0},
    ]
    recorder = Recorder(body=json.dumps({"results": results}).encode())
    page = make_provider(recorder).search_content(SearchQuery(text="x", short_form=True))
    assert kept(page) == [1]
    assert recorder.requests[0].url.params["only_shorts"] == "false"


def test_with_a_filter_the_foundation_is_asked_for_more_candidates_and_the_caller_gets_at_most_limit():
    results = [{**video(n), "lengthSeconds": 60} for n in range(1, 31)]
    recorder = Recorder(body=json.dumps({"results": results}).encode())
    page = make_provider(recorder).discover_content(DiscoveryQuery(short_form=True, limit=5))
    assert recorder.requests[0].url.params["limit"] == "1000" and len(page.items) == 5
    recorder = Recorder(body=json.dumps({"results": results}).encode())
    make_provider(recorder).discover_content(DiscoveryQuery(limit=5))  # no filter: limit unchanged
    assert recorder.requests[0].url.params["limit"] == "5"


def test_a_filtered_page_has_no_total_and_says_how_the_filter_was_applied():
    page, _ = by_duration(DURATIONS, short_form=True)
    assert page.total is None and any("duration filter" in n and "<= 180" in n for n in page.notes)
    assert by_duration(DURATIONS)[0].total == len(DURATIONS)


def test_the_funnel_has_no_shorts_stage_and_no_stage_is_added_for_the_filter():
    funnel = [
        {"step": "videos in window", "remaining": 11},
        {"step": "channel subs <= 1,000,000", "remaining": 11},
    ]
    results = [{**video(1), "lengthSeconds": 60}]
    recorder = Recorder(body=json.dumps({"results": results, "funnel": funnel}).encode())
    page = make_provider(recorder).discover_content(DiscoveryQuery(short_form=True))
    assert [s.step for s in page.funnel] == ["videos in window", "channel subs <= 1,000,000"]
    assert not any("short" in s.step.lower() for s in page.funnel)


@pytest.mark.parametrize("bad", [1, "yes", 0, [True]])
def test_an_invalid_short_form_or_limit_is_refused_before_any_request(bad):
    recorder = Recorder()
    with pytest.raises(ValueError):
        make_provider(recorder).discover_content(DiscoveryQuery(short_form=bad))
    assert recorder.requests == []


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "5"])
def test_an_invalid_limit_with_a_filter_is_refused_before_any_request(limit):
    recorder = Recorder()
    with pytest.raises(ValueError, match="limit"):
        make_provider(recorder).discover_content(DiscoveryQuery(short_form=True, limit=limit))
    assert recorder.requests == []


def test_the_label_stays_restricted_whatever_the_filter_says():
    page, _ = by_duration({1: 60}, short_form=True)
    assert {c.content_type.value for c in page.items} == {"video"}


def test_the_duration_helpers():
    assert mapping.SHORT_FORM_MAX_SECONDS == 180
    assert [mapping.is_short_form(x) for x in (None, 0, 1, 180, 181)] == [False, False, True, True, False]
    assert [mapping.duration_seconds(x) for x in (None, True, "5", -1, 0, 7, 7.5)] == [
        None,
        None,
        None,
        None,
        0,
        7,
        7.5,
    ]


# ---- engagement-rate sort removed (hidden likes counted as zero when the foundation orders) ----


def test_engagement_rate_is_not_a_sort_and_the_reason_is_stated():
    recorder = Recorder()
    for call in (
        lambda p: p.discover_content(DiscoveryQuery(sort="engagement_rate")),
        lambda p: p.search_content(SearchQuery(text="x", sort="engagement_rate")),
    ):
        with pytest.raises(ValueError, match="hidden like count as zero"):
            call(make_provider(recorder))
    assert recorder.requests == []
    for spelling in ("engagement", "engagementRate", "likeRate"):
        with pytest.raises(ValueError, match="unknown sort"):
            make_provider(recorder).discover_content(DiscoveryQuery(sort=spelling))
    assert recorder.requests == []


def test_the_engagement_rate_value_is_still_shown_only_when_likes_are_visible():
    visible = item(likes=5, comments=1, engagementRate=0.6)
    hidden = item(likes=None, comments=1, engagementRate=0.01)
    assert visible.metric("engagement_rate").value == 0.6
    assert hidden.metric("engagement_rate") is None and hidden.metric("likes") is None


# ---- period, limit and region are validated before any request ----


@pytest.mark.parametrize("period", ["all", "1h", "24h", "7d", "30d", "9999d", "1d"])
def test_a_valid_period_is_sent_verbatim(period):
    assert viral_params(period=period)["period"] == period


@pytest.mark.parametrize(
    "period",
    [
        "",
        "0h",
        "0d",
        "07d",
        "7D",
        "24H",
        "7d\n",
        " 7d",
        "7d ",
        "ALL",
        "All",
        "7",
        "d",
        "10000d",
        "1m",
        "1w",
        "7days",
        None,
        7,
        ["7d"],
        True,
    ],
)
def test_an_invalid_period_is_refused_before_any_request(period):
    recorder = Recorder()
    with pytest.raises(ValueError, match="period"):
        make_provider(recorder).discover_content(DiscoveryQuery(period=period))
    with pytest.raises(ValueError, match="period"):
        make_provider(recorder).search_content(SearchQuery(text="x", period=period))
    assert recorder.requests == []


@pytest.mark.parametrize("limit", [1, 24, 100, 1000])
def test_a_valid_limit_is_accepted(limit):
    recorder = Recorder()
    make_provider(recorder).discover_content(DiscoveryQuery(limit=limit))
    assert recorder.requests[0].url.params["limit"] == str(limit)


@pytest.mark.parametrize("limit", [0, -1, 1001, 10**6, True, False, 1.5, "5", None, [5]])
def test_an_invalid_limit_is_refused_before_any_request(limit):
    recorder = Recorder()
    with pytest.raises(ValueError, match="limit"):
        make_provider(recorder).discover_content(DiscoveryQuery(limit=limit))
    with pytest.raises(ValueError, match="limit"):
        make_provider(recorder).search_content(SearchQuery(text="x", limit=limit))
    assert recorder.requests == []


@pytest.mark.parametrize("region", ["US", "DE", "BR"])
def test_a_valid_region_is_sent(region):
    assert viral_params(region=region)["region"] == region


@pytest.mark.parametrize("region", ["", "us", "USA", "U", "U1", "US\n", 5, ["US"], True])
def test_an_invalid_region_is_refused_before_any_request(region):
    recorder = Recorder()
    with pytest.raises(ValueError, match="region"):
        make_provider(recorder).discover_content(DiscoveryQuery(region=region))
    assert recorder.requests == []


def test_there_is_no_pagination_parameter_and_the_period_is_always_explicit():
    sent = viral_params()
    assert not {"offset", "page", "cursor"} & set(sent) and sent["period"] == "7d"
