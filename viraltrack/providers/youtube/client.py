"""HTTP client for the adopted YouTube foundation (youtube-niche-finder).

ViralTrack talks to niche-finder only through its documented HTTP API
(upstream docs/http-api.md, generated from the code and checked in its CI).
It never imports niche-finder modules, so the foundation can be upgraded or
replaced without touching ViralTrack's domain.

Only read endpoints marked "free" (no YouTube quota) are used here.
"""
from __future__ import annotations

import httpx

from viraltrack.domain import NotFound, ProviderError, ProviderUnavailable

PROVIDER_ID = "youtube"


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
        try:
            resp = self._http.get(f"{self._base_url}{path}", params=clean, headers=self._headers)
        except httpx.TransportError as exc:
            raise ProviderUnavailable(PROVIDER_ID,
                                      f"foundation unreachable at {self._base_url}: {exc}") from exc
        if resp.status_code == 404:
            raise NotFound(PROVIDER_ID, _detail(resp) or f"{path} not found", 404)
        if resp.status_code in (401, 403):
            raise ProviderError(PROVIDER_ID, "foundation refused the request "
                                "(set VT_YOUTUBE_FOUNDATION_TOKEN in multi-user mode)",
                                resp.status_code)
        if resp.status_code >= 400:
            raise ProviderError(PROVIDER_ID, _detail(resp) or f"HTTP {resp.status_code}",
                                resp.status_code)
        try:
            body = resp.json()
        except ValueError as exc:
            raise ProviderError(PROVIDER_ID, f"{path} returned non-JSON",
                                resp.status_code) from exc
        if not isinstance(body, dict):
            raise ProviderError(PROVIDER_ID, f"{path} returned unexpected JSON", resp.status_code)
        return body


def _detail(resp: httpx.Response) -> str | None:
    try:
        body = resp.json()
    except ValueError:
        return None
    if isinstance(body, dict):
        detail = body.get("detail")
        return detail if isinstance(detail, str) else None
    return None
