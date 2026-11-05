"""D2: the optional publication `period` of keyword collection (offline; recorded transport, no network).

Approved contract (docs/phase-3/D2_IMPLEMENTATION_SPEC.md, owner decisions): `period` is the last argument and
defaults to None; accepted values are lowercase `all` or `N` + `h` or `d` with N from 1 to 9999; `all` sends
nothing; everything else raises ValueError before any request, the health check included; no niche
separation by period; `applied_since` is copied from the foundation's echoed `min_upload_date`,
never computed here.
"""

import inspect
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.test_ingestion import COLLECT_NICHE, ENABLED, Foundation, make
from viraltrack.domain import IngestionDisabled
from viraltrack.providers.base import IngestionResult, PlatformProvider
from viraltrack.providers.youtube.provider import YouTubeProvider, _check_collect_period

UTC = timezone.utc


def body_of(nf: Foundation, index: int = 0) -> dict:
    return json.loads(nf.posts()[index].content)


def collect(period="__unset__", **kwargs):
    nf = Foundation()
    provider = make(nf, ENABLED)
    if period == "__unset__":
        provider.collect_query("cooking", **kwargs)
    else:
        provider.collect_query("cooking", period=period, **kwargs)
    return nf


# ---- request payload: every period case ----


def test_omitted_period_sends_exactly_the_previous_request_body():
    nf = collect(region="US", language="en")
    previous = {"query": "cooking", "pages": 1, "region": "US", "language": "en"}
    assert body_of(nf) == previous
    assert "period" not in body_of(nf)
    # byte for byte: the same JSON an old client would have serialised
    assert nf.posts()[0].content == httpx.Request("POST", "http://x", json=previous).content


def test_an_explicit_none_is_the_same_as_omitted():
    assert collect(period=None).posts()[0].content == collect().posts()[0].content


def test_all_omits_the_period_upstream():
    nf = collect(period="all")
    assert "period" not in body_of(nf)
    assert nf.posts()[0].content == collect().posts()[0].content


@pytest.mark.parametrize("period", ["1h", "2h", "24h", "48h", "168h", "9999h"])
def test_valid_hour_periods_are_sent_verbatim(period):
    assert body_of(collect(period=period))["period"] == period


@pytest.mark.parametrize("period", ["1d", "7d", "30d", "90d", "365d", "9999d"])
def test_valid_day_periods_are_sent_verbatim(period):
    assert body_of(collect(period=period))["period"] == period


def test_the_minimum_and_maximum_accepted_values():
    assert _check_collect_period("1h") == "1h" and _check_collect_period("1d") == "1d"
    assert _check_collect_period("9999h") == "9999h" and _check_collect_period("9999d") == "9999d"


def test_the_body_carries_only_the_known_keys_in_every_case():
    for period in (None, "all", "24h", "7d"):
        assert set(body_of(collect(period=period))) <= {"query", "pages", "region", "language", "period"}


# ---- validation: rejected, never normalised ----

INVALID = [
    "0h",
    "0d",
    "00d",
    "000h",  # zero
    "",  # empty (upstream would read it as 'no limit')
    "7D",
    "24H",
    "ALL",
    "All",
    "aLL",  # upper case
    "day",
    "today",
    "week",
    "month",
    "quarter",
    "24hours",
    "2d ",
    "сутки",  # aliases and words
    "1w",
    "2w",
    "1m",
    "3m",
    "1y",
    "30s",
    "10min",  # units upstream knows or not
    "10000h",
    "10000d",
    "99999d",  # above the range
    "01d",
    "007d",
    "0024h",  # leading zeros are not canonical
    " 7d",
    "7d ",
    "7 d",
    "7d\n",
    "\t7d",
    "all ",  # whitespace
    "-1d",
    "+7d",
    "1.5d",
    "1,5d",
    "7.d",  # signs and decimals
    "h",
    "d",
    "24",
    "7",
    "d7",
    "1d1h",
    "1d,2d",
    "NaN",
    "inf",
    "None",
    "null",
]


@pytest.mark.parametrize("period", INVALID)
def test_invalid_periods_raise_value_error_before_any_request(period):
    nf = Foundation()
    with pytest.raises(ValueError, match="period"):
        make(nf, ENABLED).collect_query("cooking", period=period)
    assert nf.requests == []  # no health check, no collection POST


@pytest.mark.parametrize("period", [7, 24, 0, 1.5, True, False, b"7d", ["7d"], ("7d",), {"d": 7}, object()])
def test_non_string_periods_are_rejected_before_any_request(period):
    nf = Foundation()
    with pytest.raises(ValueError, match="period"):
        make(nf, ENABLED).collect_query("cooking", period=period)
    assert nf.requests == []


@pytest.mark.parametrize("period", ["7D", "week", "0d", ""])
def test_nothing_is_normalised_or_corrected_silently(period):
    """The validator never returns a changed value: it returns the input, None, or raises."""
    with pytest.raises(ValueError):
        _check_collect_period(period)


def test_an_invalid_period_does_not_hide_the_ingestion_switch():
    """Argument errors come after the off switch, like every other argument check."""
    nf = Foundation()
    with pytest.raises(IngestionDisabled):
        make(nf).collect_query("cooking", period="0d")
    assert nf.requests == []


def test_other_argument_errors_are_unchanged_and_still_raise_before_any_request():
    for kwargs in ({"pages": 99}, {"region": "usa"}, {"language": "English"}):
        nf = Foundation()
        with pytest.raises(ValueError):
            make(nf, ENABLED).collect_query("cooking", period="7d", **kwargs)
        assert nf.requests == []


def test_each_valid_call_makes_exactly_one_health_check_and_one_post():
    nf = collect(period="7d")
    assert [(r.method, r.url.path) for r in nf.requests] == [
        ("GET", "/api/health"),
        ("POST", "/api/collect/niche"),
    ]


# ---- applied_since: copied from the echoed `min_upload_date`, never computed ----


def result_with(echo) -> IngestionResult:
    answer = dict(COLLECT_NICHE)
    if echo != "__absent__":
        answer["min_upload_date"] = echo
    nf = Foundation({("POST", "/api/collect/niche"): (200, answer)})
    return make(nf, ENABLED).collect_query("cooking", period="7d")


def test_applied_since_is_exactly_the_echoed_value_as_utc():
    assert result_with("2026-10-29T10:15:30Z").applied_since == datetime(2026, 10, 29, 10, 15, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    "echo", ["2026-10-29T10:15:30+00:00", "2026-10-29T15:15:30+05:00", "2026-10-29T10:15:30.000000+00:00"]
)
def test_applied_since_accepts_any_offset_and_normalises_to_utc(echo):
    value = result_with(echo).applied_since
    assert value == datetime(2026, 10, 29, 10, 15, 30, tzinfo=UTC)
    assert value.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "echo",
    [
        "__absent__",
        None,
        "",
        "garbage",
        "2026-10-29",
        "2026-10-29T10:15:30",
        "2026-13-45T99:99:99Z",
        1730196930,
        17.5,
        True,
        [],
        {},
    ],
)
def test_a_missing_or_malformed_echo_leaves_applied_since_unavailable(echo):
    assert result_with(echo).applied_since is None


def test_applied_since_is_never_computed_locally():
    """No echo, no value: the provider's own clock and the period are not used to guess it."""
    result = result_with("__absent__")
    assert result.applied_since is None and result.finished_at is not None


def test_all_with_no_echo_leaves_applied_since_unavailable():
    nf = Foundation({("POST", "/api/collect/niche"): (200, {**COLLECT_NICHE, "min_upload_date": None})})
    assert make(nf, ENABLED).collect_query("cooking", period="all").applied_since is None


def test_the_existing_result_fields_are_unchanged():
    result = result_with("2026-10-29T10:15:30Z")
    assert result.counts == {"videos_found": 50, "videos_stored": 50, "channels_stored": 41}
    assert (result.quota_units_reported, result.search_calls_reported) == (3, 1)
    assert result.operation == "collect_query" and result.provider == "youtube"


def test_a_channel_collection_has_no_applied_since():
    """The channel route never echoes a publication window, so there is nothing to copy."""
    nf = Foundation()
    assert make(nf, ENABLED).collect_creator("@synthetic").applied_since is None


# ---- compatibility ----


def test_period_is_the_last_parameter_with_a_none_default():
    for cls in (YouTubeProvider, PlatformProvider):
        params = list(inspect.signature(cls.collect_query).parameters)
        assert params == ["self", "text", "pages", "region", "language", "period"], cls
        assert inspect.signature(cls.collect_query).parameters["period"].default is None


def test_existing_positional_and_keyword_callers_still_work():
    nf = Foundation()
    provider = make(nf, ENABLED)
    provider.collect_query("cooking", 1, "US", "en")
    provider.collect_query("cooking", pages=1, region="US")
    provider.collect_query("cooking")
    bodies = [body_of(nf, i) for i in range(3)]
    assert bodies[0] == {"query": "cooking", "pages": 1, "region": "US", "language": "en"}
    assert bodies[1] == {"query": "cooking", "pages": 1, "region": "US"}
    assert bodies[2] == {"query": "cooking", "pages": 1}


def test_ingestion_result_keeps_its_positional_field_order():
    fields = list(IngestionResult.__dataclass_fields__)
    assert fields[:7] == [
        "provider",
        "operation",
        "finished_at",
        "counts",
        "creator_id",
        "quota_units_reported",
        "search_calls_reported",
    ]
    assert fields[7:] == ["applied_since"]
    old = IngestionResult("youtube", "collect_query", datetime(2026, 11, 5, tzinfo=UTC), {}, None, 3, 1)
    assert old.applied_since is None


def test_the_unsupported_default_of_the_interface_accepts_the_new_argument():
    from viraltrack.domain import UnsupportedCapability

    class Bare(PlatformProvider):
        provider_id = "bare"
        platform = None

        def capabilities(self):
            from viraltrack.domain import Capability, CapabilityInfo, PlatformCapabilities

            return PlatformCapabilities({Capability.COLLECT_QUERY: CapabilityInfo(False, "none")})

    with pytest.raises(UnsupportedCapability):
        Bare().collect_query("x", period="7d")


# ---- niche identity: no separation by period ----


def test_different_periods_send_the_same_niche_identity():
    nf = Foundation()
    provider = make(nf, ENABLED)
    for period in (None, "all", "24h", "30d"):
        provider.collect_query("home espresso", period=period)
    bodies = [body_of(nf, i) for i in range(4)]
    assert all(b["query"] == "home espresso" for b in bodies)
    assert all("label" not in b and "niche" not in b for b in bodies)  # nothing that could split the niche
    assert [b.get("period") for b in bodies] == [None, None, "24h", "30d"]
    assert {k: v for b in bodies for k, v in b.items() if k != "period"} == {
        "query": "home espresso",
        "pages": 1,
    }


# ---- failures: one attempt, typed errors, quota unchanged ----


@pytest.mark.parametrize(
    "error",
    [httpx.ReadTimeout, httpx.WriteTimeout, httpx.ConnectTimeout, httpx.PoolTimeout, httpx.ConnectError],
)
def test_no_retry_of_a_collection_with_a_period(error):
    posts = []

    def handler(request):
        if request.method == "POST":
            posts.append(request)
            raise error("down", request=request)
        return Foundation()(request)

    with pytest.raises(Exception):
        make(handler, ENABLED).collect_query("cooking", period="7d")
    assert len(posts) == 1


def test_quota_figures_are_copied_unchanged_whatever_the_period():
    for period in (None, "all", "1h", "9999d"):
        result = make(Foundation(), ENABLED).collect_query("cooking", period=period)
        assert (result.quota_units_reported, result.search_calls_reported) == (3, 1)
