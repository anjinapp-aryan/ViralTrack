"""D1-B/C/E: the REAL pinned upstream discovery code, run offline over a synthetic corpus.

Needs VT_TEST_DATABASE_URL (PostgreSQL) and VT_TEST_UPSTREAM_PYTHON (a Python with the upstream requirements,
for example the interpreter of a venv that ran `pip install -r upstream/.../backend/requirements.txt`).
Otherwise the database tests skip. No YouTube request is possible: the runner removes YOUTUBE_API_KEY and
replaces `requests`, and every test asserts zero network attempts (see tests/support/upstream.py).
"""

import ast
import json
from pathlib import Path

import httpx
import pytest

from tests.conftest import UPSTREAM_BACKEND, pg_schema  # noqa: F401  (fixture)
from tests.support import synthetic_corpus as corpus
from tests.support.upstream import run_upstream
from tests.test_youtube_provider import make_provider
from viraltrack.providers import DiscoveryQuery

ALL = "period=all&min_views_per_subscriber=0&exclude_shorts=false"  # what the adapter sends besides filters
BIG = corpus.SENTINEL_MAX


# ---- upstream defaults, read from source (needs no database) ----


def route_defaults(function: str) -> dict:
    tree = ast.parse(Path(UPSTREAM_BACKEND / "interfaces" / "http" / "api.py").read_text(encoding="utf-8"))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function)
    names = [a.arg for a in node.args.args]
    defaults = [ast.literal_eval(d) for d in node.args.defaults]
    return dict(zip(names[len(names) - len(defaults) :], defaults))


def test_upstream_viral_route_defaults_are_the_ones_the_audit_names():
    d = route_defaults("viral")
    assert d["max_subscribers"] == 10000 and d["min_views"] == 10000
    assert d["min_views_per_subscriber"] == 1.0 and d["exclude_shorts"] is True
    assert d["period"] == "7d" and d["period_by"] == "published" and d["limit"] == 24
    assert d["sort_by"] == "viral" and d["min_outlier_score"] is None and d["preset"] is None


def test_upstream_search_route_has_no_subscriber_or_view_default():
    d = route_defaults("search")
    assert d["max_subscribers"] is None and d["period"] == "all" and d["min_outlier_score"] == 0.0


def upstream_filter_source() -> str:
    return (UPSTREAM_BACKEND / "application" / "discovery.py").read_text(encoding="utf-8")


def test_upstream_uses_is_not_none_for_subscribers_and_truthiness_for_views():
    """Why 0 behaves differently for the two filters."""
    source = upstream_filter_source()
    assert "if max_subscribers is not None:" in source
    assert "if min_views:" in source


# ---- helpers ----


@pytest.fixture
def seeded(pg_schema):  # noqa: F811
    conn, schema = pg_schema
    corpus.seed(conn, schema)
    return conn, schema


def get(schema: str, *paths: str):
    result = run_upstream(schema, list(paths))
    return [(r["status"], r["body"]) for r in result["responses"]]


def viral(schema: str, query: str):
    ((status, body),) = get(schema, f"/api/viral?{query}")
    assert status == 200, body
    return body


def ids(body) -> list[str]:
    return [r["videoId"] for r in body["results"]]


def keys(*names: str) -> set[str]:
    return {corpus.VIDEOS[n].id for n in names}


def steps(body) -> list[tuple[str, int]]:
    return [(f["step"], f["remaining"]) for f in body["funnel"]]


def remaining(body) -> list[int]:
    return [n for _, n in steps(body)]


# ---- D1-A (upstream half): the defaults really are applied to omitted parameters ----


def test_omitted_thresholds_become_restrictive_defaults_and_the_response_says_so(seeded):
    body = viral(seeded[1], "period=30d")
    assert body["filters"]["maxSubscribers"] == 10000 and body["filters"]["minViews"] == 10000
    assert body["filters"]["minViewsPerSubscriber"] == 1.0 and body["filters"]["excludeShorts"] is True


def test_the_production_response_exposes_a_funnel_and_the_filters_actually_applied(seeded):
    """Verified: the foundation reports `funnel`, `filters` and `hint` (the adapter drops the funnel)."""
    body = viral(seeded[1], "period=30d")
    assert set(body) >= {"matched", "funnel", "filters", "hint", "results", "quotaUsed"}
    assert body["quotaUsed"] == 0


# ---- unbounded semantics: what the upstream supports ----

SUBS_ZERO = keys("z_mid", "h_recent")  # subscribers 0, and hidden (NULL)
HIDDEN_ONLY = keys("h_recent")


def test_zero_does_not_disable_the_subscriber_filter(seeded):
    body = viral(seeded[1], f"{ALL}&max_subscribers=0&min_views=0")
    assert set(ids(body)) == keys("z_mid", "h_recent")  # only 0-subscriber and hidden-subscriber channels
    assert body["matched"] == 2 < 13  # 13 videos exist; every other channel is gone
    assert steps(body)[-1] == ("channel subs <= 0", 2)


def test_a_negative_bound_keeps_only_hidden_subscriber_channels(seeded):
    body = viral(seeded[1], f"{ALL}&max_subscribers=-1&min_views=0")
    assert set(ids(body)) == HIDDEN_ONLY


@pytest.mark.parametrize("raw", ["", "null", "None", "none", "unlimited", "1.5"])
def test_there_is_no_null_or_empty_spelling_over_http(seeded, raw):
    ((status, body),) = get(seeded[1], f"/api/viral?{ALL}&max_subscribers={raw}")
    assert status == 422 and "max_subscribers" in json.dumps(body)


@pytest.mark.parametrize("bound", [BIG, 1_000_000_000_000])
def test_a_very_large_bound_passes_every_channel_in_the_corpus(seeded, bound):
    body = viral(seeded[1], f"{ALL}&max_subscribers={bound}&min_views=0")
    assert body["matched"] == 13 and remaining(body) == [13, 13]


def test_zero_does_disable_the_minimum_views_filter(seeded):
    body = viral(seeded[1], f"{ALL}&max_subscribers={BIG}&min_views=0")
    assert "video views" not in json.dumps(steps(body)) and body["matched"] == 13


def test_a_negative_minimum_views_filters_nothing_but_is_applied(seeded):
    body = viral(seeded[1], f"{ALL}&max_subscribers={BIG}&min_views=-5")
    assert body["matched"] == 13 and steps(body)[-1][0].startswith("video views >=")


def test_the_niche_all_preset_is_the_upstream_unbounded_form_but_needs_a_niche(seeded):
    ((status, body),) = get(seeded[1], "/api/viral?period=all&preset=niche_all")
    assert status == 200 and body["matched"] == 0 and "requires 'niche'" in body["error"]


# ---- D1-B: each filter on its own and combined, against an independent oracle ----

SCENARIOS = {
    "route defaults": dict(q="period=30d", window=30, shorts=True, subs=10000, views=10000),
    "window only": dict(
        q=f"{ALL}&period=30d&max_subscribers={BIG}&min_views=0", window=30, shorts=False, subs=BIG, views=0
    ),
    "no window": dict(
        q=f"{ALL}&max_subscribers={BIG}&min_views=0", window=None, shorts=False, subs=BIG, views=0
    ),
    "subscribers only": dict(
        q=f"{ALL}&max_subscribers=10000&min_views=0", window=None, shorts=False, subs=10000, views=0
    ),
    "views only": dict(
        q=f"{ALL}&max_subscribers={BIG}&min_views=10000", window=None, shorts=False, subs=BIG, views=10000
    ),
    "all three": dict(
        q="period=30d&exclude_shorts=false&min_views_per_subscriber=0&max_subscribers=10000&min_views=10000",
        window=30,
        shorts=False,
        subs=10000,
        views=10000,
    ),
    "7 days": dict(
        q=f"{ALL}&period=7d&max_subscribers={BIG}&min_views=0", window=7, shorts=False, subs=BIG, views=0
    ),
    "subscribers 600": dict(
        q=f"{ALL}&max_subscribers=600&min_views=0", window=None, shorts=False, subs=600, views=0
    ),
}


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_stage_count_matches_the_independent_oracle(seeded, name):
    s = SCENARIOS[name]
    body = viral(seeded[1], s["q"] + "&limit=100")
    expected = corpus.oracle(
        corpus.VIDEOS,
        corpus.CHANNELS,
        window_days=s["window"],
        exclude_shorts=s["shorts"],
        max_subscribers=s["subs"],
        min_views=s["views"],
    )
    assert set(ids(body)) == {corpus.VIDEOS[k].id for k in expected["final"]}
    assert body["matched"] == len(expected["final"])
    wanted = [len(expected["window"])]
    wanted += [len(expected[k]) for k in ("subscribers", "views") if k in expected]
    assert remaining(body)[: len(wanted)] == wanted


def test_the_batch_5_defaults_on_the_synthetic_corpus_leave_five_candidates(seeded):
    """Hand-checked: 9 in the 30-day window (the Short is removed before the first count), 7 within 10,000
    subscribers (the hidden-subscriber channel stays), 5 with at least 10,000 views."""
    body = viral(seeded[1], "period=30d")
    assert remaining(body)[:3] == [9, 7, 5] and body["matched"] == 5
    assert set(ids(body)) == keys("s_recent_hi", "z_mid", "h_recent", "e_recent", "s_hiddenlikes")


def test_the_subscriber_limit_is_inclusive_and_one_over_is_excluded(seeded):
    body = viral(seeded[1], f"{ALL}&max_subscribers=10000&min_views=0&limit=100")
    assert keys("e_recent") <= set(ids(body)) and keys("a_recent") & set(ids(body)) == set()


def test_hidden_subscribers_pass_a_subscriber_limit(seeded):
    body = viral(seeded[1], f"{ALL}&max_subscribers=1&min_views=0&limit=100")
    assert keys("h_recent") <= set(ids(body))  # NULL subscribers are kept, not excluded


def test_zero_subscriber_channels_are_valid_candidates(seeded):
    body = viral(seeded[1], f"{ALL}&max_subscribers=0&min_views=0&limit=100")
    assert keys("z_mid") <= set(ids(body))


def test_missing_publication_date_is_in_the_all_period_but_not_in_a_dated_window(seeded):
    undated = corpus.VIDEOS["s_nopub"].id
    assert undated in ids(viral(seeded[1], f"{ALL}&max_subscribers={BIG}&min_views=0&limit=100"))
    assert undated not in ids(
        viral(seeded[1], f"{ALL}&period=365d&max_subscribers={BIG}&min_views=0&limit=100")
    )


def test_missing_view_count_counts_as_zero_views(seeded):
    no_views = corpus.VIDEOS["s_noviews"].id
    assert no_views in ids(viral(seeded[1], f"{ALL}&max_subscribers={BIG}&min_views=0&limit=100"))
    assert no_views not in ids(viral(seeded[1], f"{ALL}&max_subscribers={BIG}&min_views=1&limit=100"))


def test_old_videos_leave_a_dated_window(seeded):
    body = viral(seeded[1], f"{ALL}&period=30d&max_subscribers={BIG}&min_views=0&limit=100")
    assert keys("b_old", "s_old", "s_nopub").isdisjoint(ids(body))


def test_shorts_are_removed_before_the_first_funnel_count(seeded):
    """The funnel's first number is NOT the raw candidate count: Shorts exclusion (a default) already ran."""
    default = viral(seeded[1], "period=all&min_views=0&max_subscribers=" + str(BIG))
    explicit = viral(seeded[1], f"{ALL}&min_views=0&max_subscribers={BIG}")
    assert remaining(default)[0] == 12 and remaining(explicit)[0] == 13


# ---- D1-C: the funnel ----


def test_the_funnel_never_increases(seeded):
    for q in (s["q"] for s in SCENARIOS.values()):
        counts = remaining(viral(seeded[1], q + "&limit=100"))
        assert counts == sorted(counts, reverse=True)


def test_zero_results_name_the_stage_that_emptied_the_list(seeded):
    body = viral(seeded[1], f"{ALL}&max_subscribers=0&min_views=1000000000")
    assert body["matched"] == 0 and body["results"] == []
    assert steps(body) == [
        ("videos in window", 13),
        ("channel subs <= 0", 2),
        ("video views >= 1,000,000,000", 0),
    ]
    assert "video views" in body["hint"]  # the hint (Russian by default) names the stage


def test_an_empty_window_is_reported_as_such(seeded):
    body = viral(seeded[1], f"{ALL}&period=24h&max_subscribers={BIG}&min_views=0")
    assert remaining(body)[0] == 1  # only s_noviews (12 hours old) is that recent
    empty = viral(seeded[1], f"{ALL}&period=24h&niche=nothing&max_subscribers={BIG}&min_views=0")
    assert empty["matched"] == 0 and remaining(empty) == [0, 0]  # nothing to filter either


def test_one_result(seeded):
    body = viral(seeded[1], f"{ALL}&max_subscribers=0&min_views=20000")
    assert body["matched"] == 1 and ids(body) == [corpus.VIDEOS["z_mid"].id]


def test_many_results_are_limited_but_the_total_is_not(seeded):
    body = viral(seeded[1], f"{ALL}&max_subscribers={BIG}&min_views=0&limit=2")
    assert len(body["results"]) == 2 and body["matched"] == 13


@pytest.mark.parametrize("limit,expected", [(1, 1), (5, 5), (13, 13), (50, 13)])
def test_the_limit_never_hides_candidates_it_only_truncates_the_page(seeded, limit, expected):
    body = viral(seeded[1], f"{ALL}&max_subscribers={BIG}&min_views=0&limit={limit}")
    assert len(body["results"]) == expected and body["matched"] == 13


def test_there_is_no_offset_parameter_so_a_second_page_cannot_be_requested(seeded):
    first = viral(seeded[1], f"{ALL}&max_subscribers={BIG}&min_views=0&limit=3")
    again = viral(seeded[1], f"{ALL}&max_subscribers={BIG}&min_views=0&limit=3&offset=3&page=2")
    assert ids(first) == ids(again)  # unknown parameters are ignored


def test_the_funnel_does_not_report_the_raw_corpus_size(seeded):
    """UNKNOWN stays UNKNOWN: with defaults the first count (9) is not the 13 stored videos."""
    assert remaining(viral(seeded[1], "period=30d"))[0] != 13


def test_there_is_no_metric_eligibility_stage_upstream(seeded):
    """Missing approved metrics (no snapshots, hidden likes) remove no candidate and add no funnel step."""
    body = viral(seeded[1], f"{ALL}&max_subscribers={BIG}&min_views=0&sort_by=vph&limit=100")
    assert body["matched"] == 13 and len(body["results"]) == 13
    assert [s for s, _ in steps(body)] == ["videos in window", "channel subs <= 2,147,483,647"]


def test_candidates_without_the_sort_metric_are_listed_last_not_dropped(seeded):
    body = viral(seeded[1], f"{ALL}&max_subscribers={BIG}&min_views=0&sort_by=vph&limit=100")
    values = [r["vph24h"] for r in body["results"]]
    present = [v for v in values if v is not None]
    assert present and values[: len(present)] == present and all(v is None for v in values[len(present) :])


# ---- D1-E: data problems ----


def test_duplicate_video_ids_cannot_exist_in_the_foundation(seeded):
    import psycopg2

    conn, schema = seeded
    with conn.cursor() as cur:
        cur.execute(f"SET search_path TO {schema}")
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO videos (video_id, channel_id) VALUES (%s, %s)",
                (corpus.VIDEOS["s_old"].id, corpus.CHANNELS["SMALL"].id),
            )
    conn.rollback()


def test_stored_view_counts_are_used_as_they_are_however_old(seeded):
    """Nothing in upstream discovery checks freshness: this is why ViralTrack must label it."""
    row = viral(seeded[1], f"{ALL}&max_subscribers={BIG}&min_views=0&limit=100")["results"]
    assert {r["videoId"]: r["views"] for r in row}[corpus.VIDEOS["a_recent"].id] == 20_000


def test_the_search_route_has_no_default_thresholds(seeded):
    ((status, body),) = get(seeded[1], "/api/search?period=all&limit=100&sort_by=views")
    assert status == 200 and len(body["results"]) == 13


def test_batch_5_replay_old_adapter_query_returns_zero_with_the_recorded_funnel(pg_schema):  # noqa: F811
    """Batch 5 shape: 70 videos, 3 in 30 days, all on channels above 10,000 subscribers."""
    conn, schema = pg_schema
    corpus.seed(conn, schema, channels=corpus.B5_CHANNELS, videos=corpus.b5_videos())
    recorded = []
    transport = httpx.MockTransport(lambda r: recorded.append(r) or httpx.Response(200, json={"results": []}))
    from viraltrack.config import load_settings
    from viraltrack.providers.youtube import YouTubeProvider

    settings = load_settings(
        {"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test", "VT_YOUTUBE_DATA_ORIGIN": "test"}
    )
    YouTubeProvider(settings.youtube, http_client=httpx.Client(transport=transport)).discover_content(
        DiscoveryQuery(period="30d", limit=100, sort="views")
    )
    sent = recorded[0].url
    body = viral(schema, str(sent.query, "ascii"))
    assert steps(body) == [
        ("videos in window", 3),
        ("channel subs <= 10,000", 0),
        ("video views >= 10,000", 0),
    ]
    assert body["matched"] == 0
    fixed = viral(schema, f"{sent.query.decode()}&max_subscribers={BIG}&min_views=0")
    assert fixed["matched"] == 3  # what an explicit request would have returned


def test_the_discovery_responses_were_produced_without_any_network_attempt(seeded):
    run_upstream(seeded[1], ["/api/viral?period=30d", "/api/search?period=all"])  # asserts attempts == 0


def test_the_adapter_page_matches_what_the_foundation_returned(seeded):
    """Replay a real upstream answer through the adapter: counts and ids agree."""
    body = viral(seeded[1], f"{ALL}&max_subscribers={BIG}&min_views=0&limit=100")
    provider = make_provider(lambda request: httpx.Response(200, json=body))
    page = provider.discover_content(DiscoveryQuery(limit=100))
    assert page.total == 13 and [c.content_id for c in page.items] == ids(body)
