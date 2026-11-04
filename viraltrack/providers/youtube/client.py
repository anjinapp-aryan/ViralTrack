"""HTTP client for the adopted YouTube foundation (youtube-niche-finder).

ViralTrack talks to niche-finder only through its documented HTTP API
(upstream docs/http-api.md, generated from the code and checked in its CI).
It never imports niche-finder modules, so the foundation can be upgraded or
replaced without touching ViralTrack's domain.

Reads use only routes marked "free" (no YouTube quota). Writes are limited to
the documented collection routes in WRITE_ROUTES; any other POST is refused
before a request is made. ViralTrack never calls YouTube itself: the
foundation does, under its own quota enforcement.
"""
from __future__ import annotations

import httpx

from viraltrack.domain import (
    NotFound,
    ProviderAuthFailed,
    ProviderCredentialsMissing,
    ProviderError,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
)

PROVIDER_ID = "youtube"

# The only routes ViralTrack may POST to (upstream docs/http-api.md,
# "Collection (spends YouTube quota)").
WRITE_ROUTES = frozenset({"/api/collect/channel", "/api/collect/niche", "/api/refresh"})

# niche-finder refuses a write without a JSON body or this header (CSRF guard).
CLIENT_HEADER = {"X-NF-Client": "viraltrack"}

# 403 answers that are a plan or mode refusal, not a credentials problem.
_REFUSALS = {"PlanLimit", "FeatureOff", "ReadOnlyView"}


class FoundationClient:
    def __init__(self, base_url: str, api_token: str | None = None,
                 timeout_seconds: float = 20, http_client: httpx.Client | None = None):
        # niche-finder defaults to Russian (NF_DEFAULT_LOCALE=ru) for hints and errors.
        headers = {"Accept": "application/json", "X-NF-Locale": "en"}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout_seconds)
        self._base_url = base_url.rstrip("/")
        self._headers = headers

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def get(self, path: str, params: dict | None = None) -> dict:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        return self._send("GET", path, params=clean)

    def post(self, path: str, body: dict) -> dict:
        if path not in WRITE_ROUTES:
            raise ValueError(f"{path} is not a documented collection route")
        clean = {k: v for k, v in body.items() if v is not None}
        return self._send("POST", path, json=clean, headers=CLIENT_HEADER)

    def _send(self, method: str, path: str, params: dict | None = None,
              json: dict | None = None, headers: dict | None = None) -> dict:
        try:
            resp = self._http.request(method, f"{self._base_url}{path}", params=params, json=json,
                                      headers={**self._headers, **(headers or {})})
        except httpx.TransportError as exc:
            raise ProviderUnavailable(PROVIDER_ID,
                                      f"foundation unreachable at {self._base_url}: {exc}") from exc
        if resp.status_code >= 400:
            raise _error(resp, path)
        try:
            body = resp.json()
        except ValueError as exc:
            raise ProviderError(PROVIDER_ID, f"{path} returned non-JSON",
                                resp.status_code) from exc
        if not isinstance(body, dict):
            raise ProviderError(PROVIDER_ID, f"{path} returned unexpected JSON", resp.status_code)
        return body


def _error(resp: httpx.Response, path: str) -> ProviderError:
    status = resp.status_code
    body = _body(resp)
    kind = body.get("error") if isinstance(body.get("error"), str) else None
    detail = body.get("detail") if isinstance(body.get("detail"), str) else None
    if status == 404:
        return NotFound(PROVIDER_ID, detail or f"{path} not found", 404)
    if status == 428:
        return ProviderCredentialsMissing(
            PROVIDER_ID, "the foundation has no YOUTUBE_API_KEY configured", 428)
    if status == 429:
        if kind == "QuotaExceeded":
            return QuotaExhausted(PROVIDER_ID, detail or "YouTube quota exhausted", 429)
        return RateLimited(PROVIDER_ID, detail or "the foundation asked to wait", 429,
                           retry_after=_retry_after(resp, body))
    if status in (401, 403) and kind not in _REFUSALS:
        return ProviderAuthFailed(PROVIDER_ID, "foundation refused the request "
                                  "(set VT_YOUTUBE_FOUNDATION_TOKEN in multi-user mode)", status)
    return ProviderError(PROVIDER_ID, detail or f"HTTP {status}", status)


def _body(resp: httpx.Response) -> dict:
    try:
        body = resp.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _retry_after(resp: httpx.Response, body: dict) -> int | None:
    for value in (resp.headers.get("Retry-After"), body.get("retryAfter")):
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            continue
        if seconds >= 0:
            return seconds
    return None
