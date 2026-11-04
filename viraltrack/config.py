"""ViralTrack configuration, read from environment variables only.

Secrets are never given defaults and never printed: `Settings.describe()`
masks them. `python -m viraltrack.config` checks the current environment and
exits non-zero on an invalid value.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import parse_qs, unquote, urlsplit

from viraltrack.domain.errors import ConfigError

ENVIRONMENTS = ("development", "test", "production")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

# YouTube API Services Developer Policies III.E.4: non-authorized statistics may
# be stored for at most 30 days. Accepted "Analytics & Reporting" use cases may
# keep statistics for up to 36 calendar months; text metadata stays at 30 days.
YOUTUBE_DEFAULT_DAYS = 30
YOUTUBE_AMENDMENT_STATS_DAYS = 1095

# Approval id held once Google accepts the project's "Analytics & Reporting"
# derived-metrics amendment. Gates RESTRICTED metrics (docs/phase-1/DERIVED_METRIC_POLICY.md).
YOUTUBE_ANALYTICS_AMENDMENT = "youtube_analytics_amendment"
DATA_ORIGINS = ("real", "demo", "test")


def _bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ConfigError(f"{key} must be true or false, got {raw!r}")


def _int(env: Mapping[str, str], key: str, default: int, lo: int, hi: int) -> int:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{key} must be an integer, got {raw!r}") from None
    if not lo <= value <= hi:
        raise ConfigError(f"{key} must be between {lo} and {hi}, got {value}")
    return value


def _choice(env: Mapping[str, str], key: str, default: str, choices) -> str:
    value = (env.get(key) or default).strip()
    if value not in choices:
        raise ConfigError(f"{key} must be one of {', '.join(choices)}, got {value!r}")
    return value


@dataclass(frozen=True)
class IngestionSettings:
    """On-demand collection through the foundation (spends YouTube quota).

    Off by default: while disabled, every ingestion method raises
    IngestionDisabled before any request. The foundation enforces the quota
    itself; these are ViralTrack's own, stricter limits.
    """
    enabled: bool
    max_search_pages: int      # search.list pages per keyword collection
    max_items: int             # videos per creator collection / refresh
    min_units_left: int        # refuse when the foundation reports fewer units left today
    min_search_calls_left: int  # ... or fewer search calls left than this plus the pages asked for


@dataclass(frozen=True)
class YouTubeProviderSettings:
    enabled: bool
    base_url: str              # the niche-finder HTTP API
    api_token: str | None      # niche-finder personal token (multi-user mode only)
    timeout_seconds: int
    data_origin: str           # real | demo | test: what the foundation's corpus contains
    approvals: frozenset[str]  # policy approvals this deployment holds
    ingestion: IngestionSettings


@dataclass(frozen=True)
class RetentionSettings:
    # True only after Google accepted the project's "Analytics & Reporting"
    # derived-metrics amendment. Lifts the statistics limit to 36 months.
    youtube_amendment_accepted: bool
    youtube_stats_days: int
    youtube_text_days: int
    apply: bool                # False = report only, nothing is deleted
    # False until the transcript legal/platform review approves storing them:
    # every retention run then deletes all transcripts the foundation holds.
    transcripts_approved: bool
    # False until the owner approves archiving thumbnail images: every retention run
    # then deletes the foundation's thumbnail_archive (Phase 2 Batch 3).
    thumbnails_approved: bool


# --- database -------------------------------------------------------------
# libpq sslmode values, weakest first.
SSL_MODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")


@dataclass(frozen=True)
class DatabaseProfile:
    """What a provider requires of a connection. No URLs, hosts or credentials."""
    name: str
    managed: bool                 # a hosted service reached over the internet
    min_ssl_mode: str | None      # weakest sslmode accepted (None = any)
    default_ssl_mode: str | None  # used when neither DATABASE_SSL_MODE nor the URL sets one


DATABASE_PROFILES = {
    # Docker / local Postgres: no forced TLS (the compose network is private).
    "local": DatabaseProfile("local", False, None, None),
    # Neon rejects non-TLS connections; Supabase and Aiven offer TLS and ViralTrack requires it.
    "neon": DatabaseProfile("neon", True, "require", "require"),
    "supabase": DatabaseProfile("supabase", True, "require", "require"),
    "aiven": DatabaseProfile("aiven", True, "require", "require"),
    # Any other PostgreSQL: TLS as configured; production needs at least `require`.
    "postgres": DatabaseProfile("postgres", False, None, None),
}

_SCHEMA_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_APP_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,63}$")


@dataclass(frozen=True)
class DatabaseSettings:
    """The niche-finder Postgres database the retention job works on.

    The URL is a secret: it never appears in describe(), errors or logs
    (`masked_url` is the printable form).
    """
    provider: str
    url: str | None
    schema: str
    ssl_mode: str | None       # effective sslmode: explicit, from the URL, or the profile default
    pool_size: int             # connections a pool keeps open
    max_overflow: int          # extra connections a pool may open under load (closed when returned)
    pool_timeout: int          # seconds to wait for a free pooled connection
    connect_timeout: int       # seconds per connection attempt (libpq connect_timeout)
    statement_timeout_ms: int  # per statement, 0 = no limit (SET LOCAL, works through poolers)
    application_name: str

    @property
    def profile(self) -> DatabaseProfile:
        return DATABASE_PROFILES[self.provider]

    @property
    def max_connections(self) -> int:
        return self.pool_size + self.max_overflow

    @property
    def masked_url(self) -> str:
        return mask_database_url(self.url) if self.url else "unset"

    def require_url(self) -> str:
        if not self.url:
            raise ConfigError("DATABASE_URL is not set")
        return self.url


def mask_database_url(url: str) -> str:
    """scheme://***@host:port/db?sslmode=... -- no user, password or other parameters."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return "set (unparseable)"
    if not parts.scheme:
        return "set"
    ssl = parse_qs(parts.query).get("sslmode", [None])[-1]
    query = f"?sslmode={ssl}" if ssl in SSL_MODES else ""
    return f"{parts.scheme}://***@{host}{port}{parts.path}{query}"


def _alias(env: Mapping[str, str], key: str, legacy: str) -> str | None:
    """DATABASE_* or its earlier VT_DATABASE_* spelling; both set and different is an error."""
    new = (env.get(key) or "").strip() or None
    old = (env.get(legacy) or "").strip() or None
    if new and old and new != old:
        raise ConfigError(f"{key} and {legacy} are both set and differ; keep only {key}")
    return new or old


def _check_url(url: str, provider: str) -> str | None:
    """Validates DATABASE_URL without ever echoing it. Returns its sslmode, if any."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise ConfigError("DATABASE_URL is not a valid URL (bad port or brackets)") from None
    if parts.scheme not in ("postgresql", "postgres"):
        raise ConfigError("DATABASE_URL must start with postgresql:// or postgres://")
    if not parts.hostname and provider != "local":
        raise ConfigError(f"DATABASE_URL has no host (required for DATABASE_PROVIDER={provider})")
    if port is not None and not 1 <= port <= 65535:
        raise ConfigError("DATABASE_URL port must be between 1 and 65535")
    if not unquote(parts.path.lstrip("/")):
        raise ConfigError("DATABASE_URL has no database name")
    ssl = parse_qs(parts.query, keep_blank_values=True).get("sslmode", [None])[-1]
    if ssl is not None and ssl not in SSL_MODES:
        raise ConfigError(f"sslmode in DATABASE_URL must be one of {', '.join(SSL_MODES)}")
    return ssl


def _database(env: Mapping[str, str], environment: str) -> DatabaseSettings:
    explicit_provider = (env.get("DATABASE_PROVIDER") or "").strip()
    provider = _choice(env, "DATABASE_PROVIDER", "local", DATABASE_PROFILES)
    profile = DATABASE_PROFILES[provider]
    url = _alias(env, "DATABASE_URL", "VT_DATABASE_URL")
    schema = _alias(env, "DATABASE_SCHEMA", "VT_DATABASE_SCHEMA") or "public"
    if not _SCHEMA_NAME.match(schema):
        raise ConfigError("DATABASE_SCHEMA must be a plain identifier (letters, digits, _)")
    if explicit_provider and provider != "local" and not url:
        raise ConfigError(f"DATABASE_PROVIDER={provider} but DATABASE_URL is not set")

    url_ssl = _check_url(url, provider) if url else None
    explicit_ssl = (env.get("DATABASE_SSL_MODE") or "").strip() or None
    if explicit_ssl is not None and explicit_ssl not in SSL_MODES:
        raise ConfigError(f"DATABASE_SSL_MODE must be one of {', '.join(SSL_MODES)}, "
                          f"got {explicit_ssl!r}")
    if explicit_ssl and url_ssl and explicit_ssl != url_ssl:
        raise ConfigError(f"DATABASE_SSL_MODE={explicit_ssl} conflicts with sslmode={url_ssl} "
                          "in DATABASE_URL; set it in one place")
    ssl = explicit_ssl or url_ssl or profile.default_ssl_mode
    floor, reason = profile.min_ssl_mode, ""
    if floor is None and environment == "production" and provider == "postgres":
        floor, reason = "require", " in production"
    if url and floor and (ssl is None or SSL_MODES.index(ssl) < SSL_MODES.index(floor)):
        raise ConfigError(f"DATABASE_PROVIDER={provider} needs sslmode {floor} or stronger"
                          f"{reason}, got {ssl or 'unset'}")

    app = (env.get("DATABASE_APPLICATION_NAME") or "viraltrack").strip()
    if not _APP_NAME.match(app):
        raise ConfigError("DATABASE_APPLICATION_NAME must be 1-63 letters, digits, '.', '_' or '-'")
    return DatabaseSettings(
        provider=provider,
        url=url,
        schema=schema,
        ssl_mode=ssl,
        pool_size=_int(env, "DATABASE_POOL_SIZE", 2, 1, 20),
        max_overflow=_int(env, "DATABASE_MAX_OVERFLOW", 0, 0, 20),
        pool_timeout=_int(env, "DATABASE_POOL_TIMEOUT", 30, 1, 300),
        connect_timeout=_int(env, "DATABASE_CONNECT_TIMEOUT", 10, 1, 120),
        statement_timeout_ms=_int(env, "DATABASE_STATEMENT_TIMEOUT", 600_000, 0, 86_400_000),
        application_name=app,
    )


@dataclass(frozen=True)
class Settings:
    environment: str
    log_level: str
    youtube: YouTubeProviderSettings
    database: DatabaseSettings
    retention: RetentionSettings

    def describe(self) -> dict:
        db = self.database
        return {
            "environment": self.environment,
            "log_level": self.log_level,
            "youtube.enabled": self.youtube.enabled,
            "youtube.base_url": self.youtube.base_url,
            "youtube.api_token": "set" if self.youtube.api_token else "unset",
            "youtube.data_origin": self.youtube.data_origin,
            "youtube.approvals": sorted(self.youtube.approvals),
            "youtube.ingestion.enabled": self.youtube.ingestion.enabled,
            "youtube.ingestion.max_search_pages": self.youtube.ingestion.max_search_pages,
            "youtube.ingestion.max_items": self.youtube.ingestion.max_items,
            "youtube.ingestion.min_units_left": self.youtube.ingestion.min_units_left,
            "youtube.ingestion.min_search_calls_left": self.youtube.ingestion.min_search_calls_left,
            "database.provider": db.provider,
            "database.url": db.masked_url,
            "database.schema": db.schema,
            "database.ssl_mode": db.ssl_mode or "libpq default (prefer)",
            "database.pool_size": db.pool_size,
            "database.max_overflow": db.max_overflow,
            "database.pool_timeout": db.pool_timeout,
            "database.connect_timeout": db.connect_timeout,
            "database.statement_timeout_ms": db.statement_timeout_ms,
            "database.application_name": db.application_name,
            "retention.youtube_amendment_accepted": self.retention.youtube_amendment_accepted,
            "retention.youtube_stats_days": self.retention.youtube_stats_days,
            "retention.youtube_text_days": self.retention.youtube_text_days,
            "retention.apply": self.retention.apply,
            "retention.transcripts_approved": self.retention.transcripts_approved,
            "retention.thumbnails_approved": self.retention.thumbnails_approved,
        }


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env

    amendment = _bool(env, "VT_YOUTUBE_ANALYTICS_AMENDMENT_ACCEPTED", False)
    stats_cap = YOUTUBE_AMENDMENT_STATS_DAYS if amendment else YOUTUBE_DEFAULT_DAYS
    stats_days = _int(env, "VT_RETENTION_YOUTUBE_STATS_DAYS", stats_cap, 1, stats_cap)
    text_days = _int(env, "VT_RETENTION_YOUTUBE_TEXT_DAYS", YOUTUBE_DEFAULT_DAYS, 1,
                     YOUTUBE_DEFAULT_DAYS)

    base_url = (env.get("VT_YOUTUBE_FOUNDATION_URL") or "http://localhost:8080").rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise ConfigError(f"VT_YOUTUBE_FOUNDATION_URL must be an http(s) URL, got {base_url!r}")

    environment = _choice(env, "VT_ENV", "development", ENVIRONMENTS)
    data_origin = _choice(env, "VT_YOUTUBE_DATA_ORIGIN", "real", DATA_ORIGINS)
    if environment == "production" and data_origin != "real":
        raise ConfigError("VT_YOUTUBE_DATA_ORIGIN must be 'real' when VT_ENV=production")

    return Settings(
        environment=environment,
        log_level=_choice(env, "VT_LOG_LEVEL", "INFO", LOG_LEVELS),
        youtube=YouTubeProviderSettings(
            enabled=_bool(env, "VT_YOUTUBE_ENABLED", True),
            base_url=base_url,
            api_token=env.get("VT_YOUTUBE_FOUNDATION_TOKEN") or None,
            timeout_seconds=_int(env, "VT_YOUTUBE_TIMEOUT_SECONDS", 20, 1, 300),
            data_origin=data_origin,
            approvals=frozenset({YOUTUBE_ANALYTICS_AMENDMENT} if amendment else ()),
            ingestion=IngestionSettings(
                enabled=_bool(env, "VT_YOUTUBE_INGESTION_ENABLED", False),
                max_search_pages=_int(env, "VT_YOUTUBE_MAX_SEARCH_PAGES", 1, 1, 5),
                max_items=_int(env, "VT_YOUTUBE_MAX_VIDEOS_PER_COLLECT", 200, 1, 500),
                min_units_left=_int(env, "VT_YOUTUBE_QUOTA_FLOOR_UNITS", 1000, 0, 1_000_000),
                min_search_calls_left=_int(env, "VT_YOUTUBE_QUOTA_FLOOR_SEARCH_CALLS", 10, 0, 100),
            ),
        ),
        database=_database(env, environment),
        retention=RetentionSettings(
            youtube_amendment_accepted=amendment,
            youtube_stats_days=stats_days,
            youtube_text_days=text_days,
            apply=_bool(env, "VT_RETENTION_APPLY", False),
            transcripts_approved=_bool(env, "VT_TRANSCRIPTS_APPROVED", False),
            thumbnails_approved=_bool(env, "VT_THUMBNAILS_APPROVED", False),
        ),
    )


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 1
    for key, value in settings.describe().items():
        print(f"{key} = {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
