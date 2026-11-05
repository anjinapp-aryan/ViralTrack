"""D1-D: restricted-metric protection and metric honesty, end to end through the REAL upstream (offline).

Real upstream answers (which DO contain every restricted field) are replayed through the ViralTrack adapter.
Needs VT_TEST_DATABASE_URL and VT_TEST_UPSTREAM_PYTHON for the replay tests; structural tests run anywhere.
"""

import dataclasses
import json

import httpx
import pytest

from tests.conftest import pg_schema  # noqa: F401  (fixture)
from tests.support import synthetic_corpus as corpus
from tests.support.upstream import run_upstream
from tests.test_youtube_provider import Recorder, make_provider
from viraltrack.domain import RestrictedMetric
from viraltrack.domain import models as domain_models
from viraltrack.providers import DiscoveryQuery, SearchQuery
from viraltrack.providers.youtube.metric_policy import RULES

BIG = corpus.SENTINEL_MAX
QUERY = (
    f"period=all&min_views_per_subscriber=0&exclude_shorts=false&max_subscribers={BIG}&min_views=0&limit=100"
)

RESTRICTED_UPSTREAM_FIELDS = {
    "acceleration",
    "viewsPerSubscriber",
    "outlierScore",
    "outlierScoreAgeAdjusted",
    "outlierScoreNexlev",
    "outlierBand",
    "viralScore",
    "projected30dViews",
    "estimatedRpm",
    "baselineMedianViews",
    "semanticScore",
}
RESTRICTED_NAMES = {r.name for r in RULES if r.exposure.value != "allowed"}
APPROVED = {r.name for r in RULES if r.exposure.value == "allowed"}
assert len(RESTRICTED_NAMES) == 12 and len(APPROVED) == 4  # 10 restricted + 2 internal-only, 4 approved


@pytest.fixture
def replay(pg_schema):  # noqa: F811
    """(upstream body, ContentPage mapped by the adapter) for the whole synthetic corpus."""
    conn, schema = pg_schema
    corpus.seed(conn, schema)
    result = run_upstream(schema, [f"/api/viral?{QUERY}"])
    status, body = result["responses"][0]["status"], result["responses"][0]["body"]
    assert status == 200
    provider = make_provider(lambda request: httpx.Response(200, json=body))
    return body, provider.discover_content(DiscoveryQuery(limit=100)), schema


def by_id(page):
    return {c.content_id: c for c in page.items}


def names(content) -> set[str]:
    return {m.name for m in content.metrics + content.derived}


# ---- restricted metrics cannot reach the output ----


def test_the_real_upstream_answer_does_carry_the_restricted_fields(replay):
    """Precondition: the protection below is meaningful only if upstream really sends them."""
    body, _page, _ = replay
    assert RESTRICTED_UPSTREAM_FIELDS - {"semanticScore"} <= set(
        body["results"][0]
    )  # semanticScore: text search only


def test_no_restricted_or_internal_metric_survives_the_adapter(replay):
    _body, page, _ = replay
    assert len(page.items) == 13
    for content in page.items:
        assert not (names(content) & RESTRICTED_NAMES)
        assert names(content) <= APPROVED | {"views", "likes", "comments"}


def test_no_restricted_value_or_field_name_appears_in_any_serialised_form(replay):
    body, page, _ = replay
    text = json.dumps([dataclasses.asdict(c) for c in page.items], default=str).lower()
    for name in RESTRICTED_NAMES | {n.lower() for n in RESTRICTED_UPSTREAM_FIELDS}:
        assert name.lower() not in text, name
    sample = body["results"][0]  # and the actual restricted VALUES are absent
    for field in ("outlierScore", "viralScore", "viewsPerSubscriber", "projected30dViews"):
        if sample.get(field) not in (None, 0):
            assert f'"value": {sample[field]}' not in text


def test_the_page_object_has_no_score_or_rank_field(replay):
    fields = {
        f.name.lower()
        for cls in (
            domain_models.Content,
            domain_models.ContentPage,
            domain_models.Creator,
            domain_models.Metric,
            domain_models.Provenance,
        )
        for f in dataclasses.fields(cls)
    }
    assert not any(
        word in field for field in fields for word in ("score", "rank", "viral", "breakout", "outlier")
    )


@pytest.mark.parametrize("name", sorted(RESTRICTED_NAMES))
def test_every_restricted_or_internal_metric_is_refused_as_a_sort_before_any_request(name):
    rec = Recorder()
    provider = make_provider(rec)
    with pytest.raises((RestrictedMetric, ValueError)):
        provider.discover_content(DiscoveryQuery(sort=name))
    with pytest.raises((RestrictedMetric, ValueError)):
        provider.search_content(SearchQuery(sort=name))
    assert rec.requests == []


@pytest.mark.parametrize(
    "sort,upstream",
    [
        ("views", "views"),
        ("published_at", "published"),
        ("views_per_hour_lifetime", "vph_lifetime"),
        ("views_per_hour_24h", "vph"),
        ("views_gained_24h", "velocity"),
        ("engagement_rate", "engagement"),
    ],
)
def test_only_approved_metrics_and_raw_values_can_be_requested_as_the_order(sort, upstream):
    rec = Recorder()
    make_provider(rec).discover_content(DiscoveryQuery(sort=sort))
    assert rec.requests[0].url.params["sort_by"] == upstream
    assert upstream not in {"viral", "outlier", "outlier_adjusted", "vsr", "acceleration"}


def test_the_default_upstream_order_is_a_restricted_score_so_it_must_never_be_relied_on(replay):
    """Upstream's own default `sort_by` is `viral` (restricted). The adapter always names its sort."""
    from tests.test_discovery_d1_upstream import route_defaults

    assert route_defaults("viral")["sort_by"] == "viral"
    rec = Recorder()
    make_provider(rec).discover_content(DiscoveryQuery())
    assert rec.requests[0].url.params["sort_by"] == "views"


def test_ordering_by_lifetime_velocity_follows_the_approved_metric_not_a_hidden_score(pg_schema):  # noqa: F811
    conn, schema = pg_schema
    corpus.seed(conn, schema)
    body = run_upstream(schema, [f"/api/viral?{QUERY}&sort_by=vph_lifetime"])["responses"][0]["body"]
    values = [r["vphLifetime"] for r in body["results"]]
    assert values == sorted(values, reverse=True)


# ---- metric honesty ----


def test_hidden_likes_never_produce_an_engagement_rate(replay):
    body, page, _ = replay
    hidden = corpus.VIDEOS["s_hiddenlikes"].id
    raw = next(r for r in body["results"] if r["videoId"] == hidden)
    assert raw["likes"] is None and raw["engagementRate"] is not None  # upstream counts hidden likes as zero
    mapped = by_id(page)[hidden]
    assert "engagement_rate" not in names(mapped) and "likes" not in names(mapped)


def test_visible_likes_give_the_documented_rate(replay):
    body, page, _ = replay
    video = corpus.VIDEOS["s_recent_hi"]
    rate = by_id(page)[video.id].metric("engagement_rate").value
    assert rate == pytest.approx((video.likes + video.comments) / video.views * 100, abs=0.001)


def test_no_snapshots_means_no_24_hour_metrics_not_zero(replay):
    _body, page, _ = replay
    for key in ("s_recent_lo", "z_mid", "s_old"):
        assert not ({"views_per_hour_24h", "views_gained_24h"} & names(by_id(page)[corpus.VIDEOS[key].id]))


def test_one_snapshot_is_not_a_trend(replay):
    body, page, _ = replay
    one = corpus.VIDEOS["b_recent"].id  # a single snapshot
    assert next(r for r in body["results"] if r["videoId"] == one)["vph24h"] is None
    assert not ({"views_per_hour_24h", "views_gained_24h"} & names(by_id(page)[one]))


def test_two_snapshots_give_a_velocity_with_the_window_caveat_attached(replay):
    _body, page, _ = replay
    metric = by_id(page)[corpus.VIDEOS["s_recent_hi"].id].metric("views_per_hour_24h")
    assert metric is not None and "window varies" in metric.provenance.note
    assert metric.provenance.collected_at is None  # capture time stays unknown


def test_a_two_hour_history_is_reported_as_a_24_hour_rate_with_only_the_generic_caveat(replay):
    """KNOWN LIMIT (characterisation): the value is computed over 2 hours; the note says the window varies but
    not what it was. The label says 24h."""
    body, page, _ = replay
    thin = corpus.VIDEOS["e_recent"].id
    assert next(r for r in body["results"] if r["videoId"] == thin)["vph24h"] == pytest.approx(100.0, abs=0.5)
    metric = by_id(page)[thin].metric("views_per_hour_24h")
    assert metric.value == pytest.approx(100.0, abs=0.5) and "window varies" in metric.provenance.note


@pytest.mark.xfail(
    strict=True,
    reason="gap: velocity from snapshots that are weeks old is shown like a current one "
    "(no snapshot time reaches ViralTrack, so staleness cannot be judged)",
)
def test_velocity_from_stale_snapshots_is_withheld_or_flagged(replay):
    body, page, _ = replay
    stale = corpus.VIDEOS["a_recent"].id  # both snapshots about 20 days old
    assert next(r for r in body["results"] if r["videoId"] == stale)["vph24h"] is not None
    metric = by_id(page)[stale].metric("views_per_hour_24h")
    assert metric is None or "stale" in (metric.provenance.note or "").lower()


def test_lifetime_velocity_uses_the_stored_count_and_is_labelled_as_such(replay):
    _body, page, _ = replay
    metric = by_id(page)[corpus.VIDEOS["z_mid"].id].metric("views_per_hour_lifetime")
    assert (
        metric is not None
        and metric.provenance.kind.value == "derived"
        and "hours since publication" in metric.provenance.note
    )


def test_missing_view_counts_stay_missing(replay):
    _body, page, _ = replay
    assert "views" not in names(by_id(page)[corpus.VIDEOS["s_noviews"].id])


def test_no_approved_metric_is_ever_invented_for_undated_videos(replay):
    _body, page, _ = replay
    undated = by_id(page)[corpus.VIDEOS["s_nopub"].id]
    assert undated.published_at is None
    # upstream treats an undated video as age 0 and returns a lifetime rate from it; a missing date must not
    # produce a velocity (see known-gap test below)


@pytest.mark.xfail(
    strict=True,
    reason="gap: an undated video gets a lifetime velocity computed from age 0 h (floored to 1 h)",
)
def test_an_undated_video_has_no_lifetime_velocity(replay):
    _body, page, _ = replay
    assert by_id(page)[corpus.VIDEOS["s_nopub"].id].metric("views_per_hour_lifetime") is None
