"""Settings of the HTTP API (D5), validated like the rest of `viraltrack.config`.

Kept apart from `viraltrack.config.Settings` so that the library, the retention job and the ingestion code
are unchanged by the API. Every value has a safe default: no CORS origin is allowed unless one is listed.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

from viraltrack.domain import ConfigError

LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")
_ORIGIN = re.compile(r"https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?")


@dataclass(frozen=True)
class ApiSettings:
    cors_origins: tuple[str, ...]  # exact browser origins allowed to call the API; empty = none
    host: str  # bind address for `python -m viraltrack.api`
    port: int


def load_api_settings(env: Mapping[str, str] | None = None, environment: str = "development") -> ApiSettings:
    env = os.environ if env is None else env
    origins = tuple(
        o.strip().rstrip("/") for o in (env.get("VT_API_CORS_ORIGINS") or "").split(",") if o.strip()
    )
    for origin in origins:
        if not _ORIGIN.fullmatch(origin):
            raise ConfigError(f"VT_API_CORS_ORIGINS entries must be http(s)://host[:port], got {origin!r}")
        if environment == "production" and origin.startswith("http://"):
            raise ConfigError(f"VT_API_CORS_ORIGINS must use https in production, got {origin!r}")
    host = (env.get("VT_API_HOST") or "127.0.0.1").strip()
    if host not in LOOPBACK_HOSTS:
        # D5 has no authentication: until an authentication boundary is approved, the API is local only
        raise ConfigError(
            f"VT_API_HOST must be a loopback address ({', '.join(LOOPBACK_HOSTS)}) while the "
            f"API has no authentication, got {host!r}"
        )
    raw_port = (env.get("VT_API_PORT") or "8000").strip()
    if not raw_port.isdigit() or not 1 <= int(raw_port) <= 65535:
        raise ConfigError(f"VT_API_PORT must be a port number, got {raw_port!r}")
    return ApiSettings(cors_origins=origins, host=host, port=int(raw_port))
