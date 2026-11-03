"""Which derived values may become user-visible.

A provider declares one `MetricRule` per derived value it can produce. Only
values whose rule allows exposure (given the approvals this deployment holds)
are ever put into `Content`; `Content` itself rejects any metric whose
provenance is not ALLOWED, so a restricted value cannot reach a caller by
another path. Unknown names are denied.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from viraltrack.domain.errors import ViralTrackError


class Exposure(str, Enum):
    ALLOWED = "allowed"              # may be shown to users (labelled as not a platform metric)
    RESTRICTED = "restricted"        # shown only once the named approval is held
    INTERNAL_ONLY = "internal_only"  # intermediate value; never user-visible


@dataclass(frozen=True)
class MetricRule:
    name: str
    exposure: Exposure
    basis: str                       # formula / why it has this status
    requires: str | None = None      # approval id a RESTRICTED rule needs
    review: str | None = None        # open question for human/legal review


class RestrictedMetric(ViralTrackError):
    def __init__(self, name: str, reason: str):
        super().__init__(f"metric {name!r} is not exposable: {reason}")
        self.name = name


class MetricPolicy:
    def __init__(self, rules: list[MetricRule], approvals: frozenset[str] = frozenset()):
        self.rules = {r.name: r for r in rules}
        for r in rules:
            if r.exposure is Exposure.RESTRICTED and not r.requires:
                raise ValueError(f"restricted rule {r.name!r} must name the approval it requires")
        self.approvals = approvals

    def decision(self, name: str) -> tuple[bool, str]:
        rule = self.rules.get(name)
        if rule is None:
            return False, "no policy rule (denied by default)"
        if rule.exposure is Exposure.ALLOWED:
            return True, "allowed"
        if rule.exposure is Exposure.INTERNAL_ONLY:
            return False, "internal only"
        if rule.requires in self.approvals:
            return True, f"allowed by approval {rule.requires}"
        return False, f"requires approval {rule.requires}"

    def exposable(self, name: str) -> bool:
        return self.decision(name)[0]

    def require(self, name: str) -> None:
        ok, reason = self.decision(name)
        if not ok:
            raise RestrictedMetric(name, reason)
