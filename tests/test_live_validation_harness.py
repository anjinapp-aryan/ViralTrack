"""D7 offline harness: every limit is proven against a fake foundation ledger. No network, no quota.

The fake foundation answers /api/health from counters that /api/collect/niche moves, like the real ledger
(a search is one search call plus one pool unit). Nothing here can reach YouTube or a real foundation.
"""

import json
from datetime import datetime, timezone

import httpx
import pytest

from viraltrack.config import load_settings
from viraltrack.providers.youtube.live_validation import (
    ARM_ENV,
    ESTIMATED_OTHER_UNITS,
    MAX_OTHER_UNITS,
    MAX_SEARCH_CALLS,
    LiveBudget,
    LiveBudgetExceeded,
    LivePlan,
    LiveValidation,
    LiveValidationDisabled,
    LiveValidationRefused,
)
from viraltrack.providers.youtube.provider import YouTubeProvider

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
PLAN = LivePlan(query="home cooking")
ARMED = {ARM_ENV: PLAN.fingerprint()}


class Ledger:
    """search calls and pool units used today; one POST moves them by the configured amounts."""

    def __init__(self, searches=1, pool=3, calls_used=4, units_used=40, post_status=200, timeout=False):
        self.step = (searches, pool)
        self.calls, self.units = calls_used, units_used
        self.post_status, self.timeout = post_status, timeout
        self.requests: list[httpx.Request] = []
        self.health_fails_from = None

    def posts(self):
        return [r for r in self.requests if r.method == "POST"]

    def __call__(self, request):
        self.requests.append(request)
        if request.method == "GET" and request.url.path == "/api/health":
            if self.health_fails_from is not None and len(self.posts()) >= self.health_fails_from:
                return httpx.Response(500, json={"detail": "down"})
            return httpx.Response(200, json={
                "ok": True, "hasApiKey": True,
                "searchQuota": {"callsToday": self.calls, "dailyLimit": 100,
                                "callsLeft": 100 - self.calls},
                "unitQuota": {"unitsToday": self.units, "dailyLimit": 10000,
                              "unitsLeft": 10000 - self.units}})
        if request.method == "POST" and request.url.path == "/api/collect/niche":
            if self.timeout:
                raise httpx.ReadTimeout("slow", request=request)
            self.calls += self.step[0]
            self.units += self.step[1]
            if self.post_status != 200:
                return httpx.Response(self.post_status, json={"detail": "boom"})
            return httpx.Response(200, json={
                "niche": "home cooking", "videos_found": 50, "videos_stored": 50, "channels_stored": 41,
                "quota": {"search_calls": self.step[0], "units_from_shared_pool": self.step[1]}})
        return httpx.Response(404, json={"detail": "no route"})


def provider(ledger, token="secret-token-value"):
    settings = load_settings({"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test", "VT_YOUTUBE_DATA_ORIGIN": "test",
                              "VT_YOUTUBE_INGESTION_ENABLED": "true", "VT_YOUTUBE_FOUNDATION_TOKEN": token})
    client = httpx.Client(transport=httpx.MockTransport(ledger))
    return YouTubeProvider(settings.youtube, http_client=client, clock=lambda: NOW)


def harness(ledger, env=ARMED, budget=None, plan=PLAN):
    return LiveValidation(provider(ledger), plan, budget, env=env, clock=lambda: NOW)


# disabled by default ----------------------------------------------------------------------------

@pytest.mark.parametrize("env", [{}, {ARM_ENV: ""}, {ARM_ENV: "true"}, {ARM_ENV: "1"},
                                 {ARM_ENV: LivePlan(query="other").fingerprint()}])
def test_not_armed_for_this_exact_plan_sends_nothing(env):
    ledger = Ledger()
    with pytest.raises(LiveValidationDisabled):
        harness(ledger, env=env).run()
    assert ledger.requests == []


def test_every_part_of_the_plan_changes_the_fingerprint():
    base = PLAN.fingerprint()
    others = [LivePlan(query="x"), LivePlan(query="home cooking", region="US"),
              LivePlan(query="home cooking", language="en"), LivePlan(query="home cooking", period="30d")]
    assert len({base, *(p.fingerprint() for p in others)}) == 5


# the limits cannot be raised --------------------------------------------------------------------

def test_the_ceilings_are_one_search_and_fifteen_other_units():
    assert (MAX_SEARCH_CALLS, MAX_OTHER_UNITS) == (1, 15)
    assert LiveBudget() == LiveBudget(1, 15)


@pytest.mark.parametrize("kwargs", [
    {"max_search_calls": 2}, {"max_other_units": 16}, {"max_search_calls": -1},
    {"max_other_units": True}, {"max_search_calls": 1.0}, {"max_other_units": "15"}])
def test_a_budget_above_the_ceiling_or_malformed_is_rejected(kwargs):
    with pytest.raises(ValueError):
        LiveBudget(**kwargs)


# happy path: exactly one request, ledger checked -----------------------------------------------------

def test_an_armed_run_sends_one_post_and_proves_both_limits_from_the_ledger():
    ledger = Ledger(searches=1, pool=3)
    report = harness(ledger).run()
    assert len(ledger.posts()) == 1
    assert json.loads(ledger.posts()[0].content)["pages"] == 1
    assert (report.search_calls_used, report.pool_units_used, report.other_units_used) == (1, 3, 2)
    assert report.outcome == "completed" and report.breaches == ()
    assert report.other_units_used <= ESTIMATED_OTHER_UNITS


# independent enforcement: ledger overruns -------------------------------------------------------------

def test_two_search_calls_in_the_ledger_are_a_breach():
    with pytest.raises(LiveBudgetExceeded) as caught:
        harness(Ledger(searches=2, pool=4)).run()
    assert any(b.startswith("search_calls 2") for b in caught.value.report.breaches)


def test_more_than_fifteen_other_units_in_the_ledger_are_a_breach():
    with pytest.raises(LiveBudgetExceeded) as caught:
        harness(Ledger(searches=1, pool=17)).run()          # 17 pool - 1 search = 16 other
    assert caught.value.report.other_units_used == 16
    assert any(b.startswith("other_units 16") for b in caught.value.report.breaches)


def test_exactly_fifteen_other_units_is_allowed():
    report = harness(Ledger(searches=1, pool=16)).run()
    assert report.other_units_used == 15 and report.breaches == ()


def test_the_foundation_reporting_more_search_calls_than_the_ledger_is_a_breach():
    ledger = Ledger(searches=1, pool=3)
    original = ledger.__call__

    def lying(request):
        response = original(request)
        if request.method == "POST":
            body = json.loads(response.content)
            body["quota"]["search_calls"] = 2
            return httpx.Response(200, json=body)
        return response
    p = YouTubeProvider(load_settings({"VT_YOUTUBE_FOUNDATION_URL": "http://nf.test",
                                       "VT_YOUTUBE_DATA_ORIGIN": "test",
                                       "VT_YOUTUBE_INGESTION_ENABLED": "true"}).youtube,
                        http_client=httpx.Client(transport=httpx.MockTransport(lying)), clock=lambda: NOW)
    with pytest.raises(LiveBudgetExceeded):
        LiveValidation(p, PLAN, env=ARMED, clock=lambda: NOW).run()


def test_a_lowered_budget_is_enforced():
    with pytest.raises(LiveBudgetExceeded):
        harness(Ledger(searches=1, pool=5), budget=LiveBudget(1, 3)).run()    # 4 other > 3


def test_a_budget_below_the_estimate_prevents_execution():
    ledger = Ledger()
    with pytest.raises(LiveValidationRefused):
        harness(ledger, budget=LiveBudget(1, ESTIMATED_OTHER_UNITS - 1)).run()
    assert ledger.requests == []


def test_a_budget_of_no_search_calls_prevents_execution():
    ledger = Ledger()
    with pytest.raises(LiveValidationRefused):
        harness(ledger, budget=LiveBudget(0, 15)).run()
    assert ledger.requests == []


def test_no_search_call_left_in_the_ledger_prevents_the_post():
    ledger = Ledger(calls_used=100)
    with pytest.raises(LiveValidationRefused):
        harness(ledger).run()
    assert ledger.posts() == []


# single use, no retry --------------------------------------------------------------------------

def test_a_second_run_is_refused_and_sends_nothing():
    ledger = Ledger()
    h = harness(ledger)
    h.run()
    seen = len(ledger.requests)
    with pytest.raises(LiveValidationRefused):
        h.run()
    assert len(ledger.requests) == seen and len(ledger.posts()) == 1


@pytest.mark.parametrize("ledger", [Ledger(post_status=500, searches=0, pool=0),
                                    Ledger(post_status=502, searches=1, pool=1),
                                    Ledger(timeout=True, searches=0, pool=0)])
def test_a_failed_or_timed_out_post_is_never_retried(ledger):
    h = harness(ledger)
    report = h.run()
    assert len(ledger.posts()) == 1
    assert report.outcome == "error" and report.error_type
    with pytest.raises(LiveValidationRefused):
        h.run()
    assert len(ledger.posts()) == 1


def test_a_failed_post_that_still_spent_quota_is_measured_from_the_ledger():
    report = harness(Ledger(post_status=500, searches=1, pool=2)).run()
    assert report.outcome == "error" and (report.search_calls_used, report.other_units_used) == (1, 1)


def test_an_unreadable_ledger_after_the_call_is_reported_unverified():
    ledger = Ledger()
    ledger.health_fails_from = 1
    with pytest.raises(LiveBudgetExceeded) as caught:
        harness(ledger).run()
    assert caught.value.report.outcome == "unverified" and len(ledger.posts()) == 1


# sanitized evidence ----------------------------------------------------------------------------

def test_the_report_holds_no_credentials_and_no_response_body():
    report = harness(Ledger(), ).run()
    text = json.dumps(report.as_dict())
    assert "secret-token-value" not in text and "Bearer" not in text
    assert set(report.as_dict()) == {
        "plan_fingerprint", "started_at", "finished_at", "outcome", "error_type", "search_calls_used",
        "other_units_used", "pool_units_used", "reported_search_calls", "reported_pool_units", "counts",
        "breaches"}
