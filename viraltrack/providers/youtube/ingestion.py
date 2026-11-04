"""Maps niche-finder collection answers to `IngestionResult` / `QuotaStatus`.

Every number is copied from the foundation's response. ViralTrack does not
compute quota usage: `quota_units_reported` is the foundation's own
`quota.units_from_shared_pool` for the call (None when it reports none), and
the authoritative meter remains `/api/health` (`unitQuota.unitsToday`).
"""
from __future__ import annotations

from datetime import datetime

from viraltrack.domain import ProviderError
from viraltrack.providers.base import IngestionResult, QuotaStatus
from viraltrack.providers.youtube.client import PROVIDER_ID


def _int(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _counts(body: dict, prefix: str = "") -> dict[str, int]:
    """Integer tallies, one level of nesting flattened; quota and ids left out."""
    out: dict[str, int] = {}
    for key, value in body.items():
        if key == "quota":
            continue
        if isinstance(value, dict):
            for sub, v in value.items():
                if _int(v) is not None:
                    out[f"{prefix}{key}_{sub}"] = v
        elif _int(value) is not None:
            out[f"{prefix}{key}"] = value
    return out


def _quota(*bodies: dict) -> tuple[int | None, int | None]:
    """Sum of the foundation's reported figures; None if no part reported one."""
    units = calls = None
    for body in bodies:
        quota = body.get("quota") if isinstance(body, dict) else None
        if not isinstance(quota, dict):
            continue
        if (u := _int(quota.get("units_from_shared_pool"))) is not None:
            units = (units or 0) + u
        if (c := _int(quota.get("search_calls"))) is not None:
            calls = (calls or 0) + c
    return units, calls


def collect_result(operation: str, body: dict, finished_at: datetime) -> IngestionResult:
    """POST /api/collect/channel or /api/collect/niche."""
    units, calls = _quota(body)
    creator = body.get("channelId")
    return IngestionResult(provider=PROVIDER_ID, operation=operation, finished_at=finished_at,
                           counts=_counts(body),
                           creator_id=creator if isinstance(creator, str) else None,
                           quota_units_reported=units, search_calls_reported=calls)


def refresh_result(body: dict, finished_at: datetime) -> IngestionResult:
    """POST /api/refresh: {"videos": {...}, "channels": {...}} (admin or own watchlist)."""
    parts = [body.get(k) for k in ("videos", "channels")]
    if not all(isinstance(p, dict) for p in parts):
        raise ProviderError(PROVIDER_ID, "refresh response has no videos/channels parts")
    counts = {**_counts(parts[0], "videos_"), **_counts(parts[1], "channels_")}
    units, calls = _quota(*parts)
    return IngestionResult(provider=PROVIDER_ID, operation="refresh_stats",
                           finished_at=finished_at, counts=counts,
                           quota_units_reported=units, search_calls_reported=calls)


def quota_status(body: dict, checked_at: datetime) -> QuotaStatus:
    """GET /api/health. Fails closed when the quota is not reported (for example a
    multi-user foundation answering an unauthenticated request with {"ok": true})."""
    units = body.get("unitQuota")
    search = body.get("searchQuota")
    values = None
    if isinstance(units, dict) and isinstance(search, dict):
        values = [_int(units.get("unitsLeft")), _int(units.get("dailyLimit")),
                  _int(search.get("callsLeft")), _int(search.get("dailyLimit"))]
    if values is None or None in values or not isinstance(body.get("hasApiKey"), bool):
        raise ProviderError(PROVIDER_ID, "the foundation did not report its quota "
                            "(multi-user mode needs VT_YOUTUBE_FOUNDATION_TOKEN); "
                            "refusing to collect without it")
    return QuotaStatus(has_credentials=body["hasApiKey"], units_left=values[0],
                       unit_limit=values[1], search_calls_left=values[2],
                       search_call_limit=values[3], checked_at=checked_at)
