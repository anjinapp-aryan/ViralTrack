"""Guard for the one controlled live validation run (D7). Disabled by default; makes no request on its own.

REUSE audit (docs/phase-4-7/D7_HARNESS_REUSE_AUDIT.md): the foundation already owns the quota ledger
(`GET /api/health`: `searchQuota.callsToday`, `unitQuota.unitsToday`), the collection route and its cost
accounting, and ViralTrack's `YouTubeProvider` already owns the client, the single-attempt POST, the
cooldown and the quota-floor preflight. This module adds only what is specific to ViralTrack's approval:

* a hard ceiling of one `search.list` call and 15 other quota units that no caller can raise;
* an arming switch bound to the exact approved request, so nothing runs by accident;
* an independent check of both limits against the foundation's ledger, read before and after the call;
* a single-use object: no second run, no retry.

The ledger counts a search as one search call and one pool unit (foundation `client.py`, `_charges`), so
"other units" is the pool difference minus the search difference.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from viraltrack.domain import ProviderError
from viraltrack.providers.youtube.provider import YouTubeProvider

# Ceilings approved for D7. A budget may be lowered, never raised.
MAX_SEARCH_CALLS = 1
MAX_OTHER_UNITS = 15
# Upper bound of the follow-up reads for one search page: the foundation documents about one unit per 50
# videos and per 50 channels (backend/application/collecting.py), and one page returns at most 50 results.
ESTIMATED_OTHER_UNITS = 2
ARM_ENV = "VT_LIVE_VALIDATION_ARM"


class LiveValidationRefused(Exception):
    """Nothing was sent."""


class LiveValidationDisabled(LiveValidationRefused):
    """Not armed for this exact plan."""


class LiveBudgetExceeded(Exception):
    """The ledger shows more than the approved budget; the call cannot be undone. Carries the report."""

    def __init__(self, report: "LiveReport"):
        super().__init__("the foundation ledger shows the approved live budget was exceeded: "
                         + ", ".join(report.breaches))
        self.report = report


@dataclass(frozen=True)
class LiveBudget:
    max_search_calls: int = MAX_SEARCH_CALLS
    max_other_units: int = MAX_OTHER_UNITS

    def __post_init__(self):
        for name, ceiling in (("max_search_calls", MAX_SEARCH_CALLS), ("max_other_units", MAX_OTHER_UNITS)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= ceiling:
                raise ValueError(f"{name} must be an integer from 0 to {ceiling}, got {value!r}")


@dataclass(frozen=True)
class LivePlan:
    """The exact approved request. One search page, always."""

    query: str
    region: str | None = None
    language: str | None = None
    period: str | None = None

    def fingerprint(self) -> str:
        text = json.dumps({"op": "collect_query", "pages": 1, "query": self.query, "region": self.region,
                           "language": self.language, "period": self.period}, sort_keys=True)
        return hashlib.sha256(text.encode()).hexdigest()[:16]


@dataclass
class LiveReport:
    """Sanitized evidence: counts and ledger differences only. No response body, no credentials."""

    plan_fingerprint: str
    started_at: datetime
    finished_at: datetime | None = None
    outcome: str = "not_run"          # completed | error | unverified
    error_type: str | None = None
    search_calls_used: int | None = None
    other_units_used: int | None = None
    pool_units_used: int | None = None
    reported_search_calls: int | None = None
    reported_pool_units: int | None = None
    counts: dict = field(default_factory=dict)
    breaches: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "plan_fingerprint": self.plan_fingerprint,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "outcome": self.outcome, "error_type": self.error_type,
            "search_calls_used": self.search_calls_used, "other_units_used": self.other_units_used,
            "pool_units_used": self.pool_units_used,
            "reported_search_calls": self.reported_search_calls,
            "reported_pool_units": self.reported_pool_units,
            "counts": dict(self.counts), "breaches": list(self.breaches),
        }


class LiveValidation:
    """One run, one search page, never retried."""

    def __init__(self, provider: YouTubeProvider, plan: LivePlan, budget: LiveBudget | None = None,
                 env=None, clock=None):
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._provider = provider
        self._plan = plan
        self._budget = budget or LiveBudget()
        self._env = os.environ if env is None else env
        self._used = False

    def run(self) -> LiveReport:
        if self._used:
            raise LiveValidationRefused("this object already ran once; a live run is never repeated")
        if self._env.get(ARM_ENV) != self._plan.fingerprint():
            raise LiveValidationDisabled(
                f"live validation is disabled: {ARM_ENV} must equal the approved plan fingerprint "
                f"({self._plan.fingerprint()})")
        if ESTIMATED_OTHER_UNITS > self._budget.max_other_units:
            raise LiveValidationRefused(f"one search page needs about {ESTIMATED_OTHER_UNITS} other units, "
                                        f"above the budget of {self._budget.max_other_units}")
        if self._budget.max_search_calls < 1:
            raise LiveValidationRefused("the budget allows no search call")
        started = self._clock()
        before = self._provider.ingestion_status()      # reads /api/health; spends nothing
        if before.search_calls_left < 1:
            raise LiveValidationRefused("the foundation ledger shows no search call left today")
        report = LiveReport(plan_fingerprint=self._plan.fingerprint(), started_at=started)
        self._used = True                                # from here on, never again, even after an error
        failure = None
        try:
            result = self._provider.collect_query(self._plan.query, pages=1, region=self._plan.region,
                                                  language=self._plan.language, period=self._plan.period)
            report.counts = dict(result.counts)
            report.reported_search_calls = result.search_calls_reported
            report.reported_pool_units = result.quota_units_reported
        except Exception as exc:                          # recorded, never retried
            failure = exc
            report.error_type = type(exc).__name__
        report.finished_at = self._clock()
        try:
            after = self._provider.ingestion_status()
        except ProviderError:
            after = None
        if after is None:
            report.outcome = "unverified"
            report.breaches = ("ledger could not be read after the call",)
            raise LiveBudgetExceeded(report)
        searches = before.search_calls_left - after.search_calls_left
        pool = before.units_left - after.units_left
        report.search_calls_used, report.pool_units_used = searches, pool
        report.other_units_used = pool - searches
        breaches = []
        if searches > self._budget.max_search_calls:
            breaches.append(f"search_calls {searches} > {self._budget.max_search_calls}")
        if report.other_units_used > self._budget.max_other_units:
            breaches.append(f"other_units {report.other_units_used} > {self._budget.max_other_units}")
        if (report.reported_search_calls or 0) > self._budget.max_search_calls:
            breaches.append("the foundation reported more search calls than approved")
        report.breaches = tuple(breaches)
        report.outcome = "error" if failure is not None else "completed"
        if breaches:
            raise LiveBudgetExceeded(report)
        return report
