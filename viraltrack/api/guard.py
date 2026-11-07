"""Last line of the metric policy: every JSON body the API sends is inspected before it leaves.

The schemas already forbid unknown fields, and `Content` refuses restricted metrics. This guard is the
independent check: it walks the whole body, nested objects and lists included, and refuses to send it if any
key is the name of a non-ALLOWED metric or a foundation field that carries one, or if any text mentions a
restricted metric. A refusal is a 500 with no data (fail closed), and it is logged.
"""

from __future__ import annotations

import re

from viraltrack.domain import Exposure
from viraltrack.providers.youtube.mapping import DERIVED_VIDEO_METRICS
from viraltrack.providers.youtube.metric_policy import RULES

# ViralTrack names of every metric that is not ALLOWED without an approval.
RESTRICTED_NAMES = frozenset(r.name for r in RULES if r.exposure is not Exposure.ALLOWED)
# ViralTrack names that are ALLOWED but withheld by the D3 policy (no snapshot time).
WITHHELD_NAMES = frozenset({"views_per_hour_24h", "views_gained_24h"})
# Foundation field names that carry those values, plus other foundation scores and labels never mapped.
FOUNDATION_FIELDS = frozenset(
    k for k, v in DERIVED_VIDEO_METRICS.items() if v in RESTRICTED_NAMES | WITHHELD_NAMES
) | frozenset(
    {
        "outlierScoreRolling",
        "outlierScorePeriod",
        "outlierBand",
        "viralScore",
        "projected30dViews",
        "estimatedRpm",
        "estimatedRpmRange",
        "isShort",
        "semanticScore",
        "baselineMedianViews",
        "baselineMedianViewsPeriod",
        "vsr",
        "scoreBand",
        "viewVelocity",
        "breakoutScore",
        "discoveryScore",
    }
)


def _norm(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


_FORBIDDEN = frozenset(_norm(k) for k in RESTRICTED_NAMES | WITHHELD_NAMES | FOUNDATION_FIELDS)


# Restricted metrics named in explanatory text. Word boundaries keep "ViralTrack" itself from matching.
_RESTRICTED_TEXT = re.compile(
    r"per subscriber|outlier|\bviral\b|viral[ _]score|acceleration|\brpm\b|\bvsr\b", re.I
)


def mentions_restricted_metric(text: str) -> bool:
    return bool(_RESTRICTED_TEXT.search(text))


class PolicyViolation(RuntimeError):
    """A response would have carried a restricted value. Never shown to clients in detail."""


# Text written by the provider or the API about the data. Titles, names and other platform text are not
# scanned: a video may legitimately be called "Going viral".
_EXPLANATORY = frozenset({"notes", "note"})


def check(body, path: str = "$", explanatory: bool = False) -> None:
    if isinstance(body, dict):
        for key, value in body.items():
            if isinstance(key, str) and _norm(key) in _FORBIDDEN:
                raise PolicyViolation(f"restricted key {key!r} at {path}")
            check(value, f"{path}.{key}", isinstance(key, str) and key in _EXPLANATORY)
    elif isinstance(body, list | tuple):
        for i, value in enumerate(body):
            check(value, f"{path}[{i}]", explanatory)
    elif explanatory and isinstance(body, str) and mentions_restricted_metric(body):
        raise PolicyViolation(f"text mentioning a restricted metric at {path}")
