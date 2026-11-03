"""ViralTrack configuration, read from environment variables only.

Secrets are never given defaults and never printed: `Settings.describe()`
masks them. `python -m viraltrack.config` checks the current environment and
exits non-zero on an invalid value.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Mapping

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
class YouTubeProviderSettings:
    enabled: bool
    base_url: str              # the niche-finder HTTP API
    api_token: str | None      # niche-finder personal token (multi-user mode only)
    timeout_seconds: int
    data_origin: str           # real | demo | test: what the foundation's corpus contains
    approvals: frozenset[str]  # policy approvals this deployment holds


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


@dataclass(frozen=True)
class DatabaseSettings:
    url: str | None            # the niche-finder Postgres database
    schema: str


@dataclass(frozen=True)
class Settings:
    environment: str
    log_level: str
    youtube: YouTubeProviderSettings
    database: DatabaseSettings
    retention: RetentionSettings

    def describe(self) -> dict:
        db = self.database.url
        return {
            "environment": self.environment,
            "log_level": self.log_level,
            "youtube.enabled": self.youtube.enabled,
            "youtube.base_url": self.youtube.base_url,
            "youtube.api_token": "set" if self.youtube.api_token else "unset",
            "youtube.data_origin": self.youtube.data_origin,
            "youtube.approvals": sorted(self.youtube.approvals),
            "database.url": _mask_dsn(db) if db else "unset",
            "database.schema": self.database.schema,
            "retention.youtube_amendment_accepted": self.retention.youtube_amendment_accepted,
            "retention.youtube_stats_days": self.retention.youtube_stats_days,
            "retention.youtube_text_days": self.retention.youtube_text_days,
            "retention.apply": self.retention.apply,
            "retention.transcripts_approved": self.retention.transcripts_approved,
        }


def _mask_dsn(dsn: str) -> str:
    if "@" not in dsn or "://" not in dsn:
        return "set"
    scheme, rest = dsn.split("://", 1)
    return f"{scheme}://***@{rest.rsplit('@', 1)[1]}"


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
        ),
        database=DatabaseSettings(
            url=env.get("VT_DATABASE_URL") or None,
            schema=(env.get("VT_DATABASE_SCHEMA") or "public").strip(),
        ),
        retention=RetentionSettings(
            youtube_amendment_accepted=amendment,
            youtube_stats_days=stats_days,
            youtube_text_days=text_days,
            apply=_bool(env, "VT_RETENTION_APPLY", False),
            transcripts_approved=_bool(env, "VT_TRANSCRIPTS_APPROVED", False),
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
