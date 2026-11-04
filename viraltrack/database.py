"""Connections to the niche-finder Postgres database, for any PostgreSQL provider.

One place builds every ViralTrack connection from `DatabaseSettings`
(DATABASE_PROVIDER, DATABASE_URL, DATABASE_* in .env.example), on the
driver the foundation already uses (psycopg2). Nothing here is
provider-specific beyond the profile checks in `viraltrack.config`.

Rules that keep it portable across direct connections and poolers:

* Session state is set with SET LOCAL inside the caller's transaction
  (`prepare_transaction`): statement_timeout, application_name, TimeZone.
  Transaction-mode poolers (Neon's PgBouncer, Supabase's transaction port)
  do not keep session settings, and some reject startup `options`.
* Connection-level options are client-side libpq ones only: sslmode,
  connect_timeout, TCP keepalives.
* Errors never contain the URL; `DatabaseSettings.masked_url` is the
  printable form.

`python -m viraltrack.database` checks the configured database read-only
and prints a masked JSON report (see docs/architecture/DATABASE_CONFIGURATION.md).
"""
from __future__ import annotations

import json
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit

import psycopg2
import psycopg2.pool

from viraltrack.config import DatabaseSettings, load_settings
from viraltrack.domain.errors import ConfigError

# HNSW indexes, which the foundation creates, need pgvector 0.5.0 or later.
PGVECTOR_MIN_HNSW = (0, 5, 0)
CONNECT_ATTEMPTS = 3          # first try plus two retries (e.g. a compute waking from scale-to-zero)
RETRY_BASE_SECONDS = 1.0      # 1 s, then 2 s


class DatabaseUnavailable(ConnectionError):
    """No connection could be made. The message never includes the URL."""


def connect_kwargs(settings: DatabaseSettings) -> dict:
    """libpq parameters added to DATABASE_URL. Parameters given here override the URL's."""
    kwargs = {
        "connect_timeout": settings.connect_timeout,
        # detect connections a provider or NAT dropped silently
        "keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 3,
    }
    if settings.ssl_mode:
        kwargs["sslmode"] = settings.ssl_mode
    return kwargs


def connect(settings: DatabaseSettings, *, attempts: int = CONNECT_ATTEMPTS,
            sleep: Callable[[float], None] = time.sleep, _connect=None):
    """One connection, retried on connection failures only, never on query errors."""
    url = settings.require_url()
    open_ = _connect or psycopg2.connect
    last = None
    for attempt in range(attempts):
        try:
            return open_(url, **connect_kwargs(settings))
        except psycopg2.OperationalError as exc:
            last = exc
            if attempt + 1 < attempts:
                sleep(RETRY_BASE_SECONDS * 2 ** attempt)
    raise DatabaseUnavailable(
        f"could not connect to {settings.masked_url} after {attempts} attempts "
        f"({_reason(last)})") from None


def _reason(exc: Exception | None) -> str:
    """The first line of libpq's message minus anything URL-like (libpq does not echo
    passwords, but a host or user can be in it, so keep only the generic part)."""
    text = (str(exc) if exc else "").strip().splitlines()
    first = text[0] if text else "unknown error"
    for marker in ("connection to server at", "could not translate host name"):
        if first.lower().startswith(marker):
            return marker + " ... failed"
    return first[:200]


def prepare_transaction(conn, settings: DatabaseSettings) -> None:
    """Session settings for the transaction that is starting, valid through any pooler."""
    with conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = %s", (int(settings.statement_timeout_ms),))
        cur.execute("SELECT set_config('application_name', %s, true)",
                    (settings.application_name,))
        # A fixed offset, not 'UTC': some server builds ship without the time zone database
        # (found on a Windows PostgreSQL 16.2), where 'UTC' is an invalid value.
        cur.execute("SET LOCAL TIME ZONE INTERVAL '+00:00' HOUR TO MINUTE")


def is_alive(conn) -> bool:
    """Cheap liveness probe; leaves no transaction open."""
    if getattr(conn, "closed", 1):
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        conn.rollback()
        return True
    except psycopg2.Error:
        return False


class ConnectionPool:
    """A bounded pool over psycopg2's ThreadedConnectionPool.

    pool_size connections are kept when idle; up to max_overflow more are
    opened under load and closed when returned. `connection()` waits up to
    pool_timeout seconds for a free slot, replaces a connection that fails
    its liveness probe, and always returns it (rolled back) to the pool.
    The total is capped at settings.max_connections, so a pool can never
    exceed what the deployment budgeted for ViralTrack.
    """

    def __init__(self, settings: DatabaseSettings, *, _pool_factory=None):
        self._settings = settings
        factory = _pool_factory or psycopg2.pool.ThreadedConnectionPool
        self._slots = threading.BoundedSemaphore(settings.max_connections)
        try:
            self._pool = factory(settings.pool_size, settings.max_connections,
                                 settings.require_url(), **connect_kwargs(settings))
        except psycopg2.OperationalError as exc:
            raise DatabaseUnavailable(f"could not open a pool to {settings.masked_url} "
                                      f"({_reason(exc)})") from None

    @contextmanager
    def connection(self) -> Iterator:
        if not self._slots.acquire(timeout=self._settings.pool_timeout):
            raise DatabaseUnavailable(f"no free database connection within "
                                      f"{self._settings.pool_timeout} s "
                                      f"(DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW = "
                                      f"{self._settings.max_connections})")
        conn = None
        try:
            conn = self._pool.getconn()
            if not is_alive(conn):
                self._pool.putconn(conn, close=True)
                conn = self._pool.getconn()
            yield conn
        finally:
            if conn is not None:
                broken = bool(getattr(conn, "closed", 1))
                if not broken:
                    try:
                        conn.rollback()
                    except psycopg2.Error:
                        broken = True
                self._pool.putconn(conn, close=broken)
            self._slots.release()

    def close(self) -> None:
        self._pool.closeall()


# ------------------------------------------------------------------ health check

@dataclass(frozen=True)
class HealthReport:
    ok: bool
    server_version: str | None
    server_version_num: int | None
    ssl: bool | None
    max_connections: int | None
    pgvector_installed: bool
    pgvector_version: str | None
    pgvector_schema: str | None
    pgvector_hnsw: bool
    pgvector_visible: bool       # in the target schema or public, which is upstream's search_path
    schema_exists: bool
    problems: tuple[str, ...]    # a required feature is missing: incompatible
    warnings: tuple[str, ...]    # works, but untested or degraded

    def as_dict(self) -> dict:
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.__dict__.items()}


def _version_tuple(text: str | None) -> tuple[int, ...]:
    parts = []
    for piece in (text or "").split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def health_check(conn, schema: str = "public") -> HealthReport:
    """Read-only compatibility check. Changes nothing (rolls back)."""
    problems, warnings = [], []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('server_version'), "
                        "current_setting('server_version_num')::int, "
                        "current_setting('max_connections')::int")
            version, version_num, max_conn = cur.fetchone()
            ssl = None
            try:
                cur.execute("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
                row = cur.fetchone()
                ssl = bool(row[0]) if row else None
            except psycopg2.Error:
                conn.rollback()
            with conn.cursor() as cur2:
                cur2.execute("SELECT e.extversion, n.nspname FROM pg_extension e "
                             "JOIN pg_namespace n ON n.oid = e.extnamespace "
                             "WHERE e.extname = 'vector'")
                ext = cur2.fetchone()
                if ext is None:
                    cur2.execute("SELECT default_version FROM pg_available_extensions "
                                 "WHERE name = 'vector'")
                    available = cur2.fetchone()
                else:
                    available = None
                cur2.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (schema,))
                schema_exists = cur2.fetchone() is not None
    finally:
        conn.rollback()

    installed = ext is not None
    pv_version, pv_schema = (ext if ext else (None, None))
    hnsw = installed and _version_tuple(pv_version) >= PGVECTOR_MIN_HNSW
    visible = installed and pv_schema in (schema, "public")
    if version_num < 160000:
        warnings.append(f"PostgreSQL {version}: only 16 has been tested with the foundation")
    if not installed:
        problems.append("pgvector is not installed" + (
            f" (available: {available[0]}; run CREATE EXTENSION vector as an admin)"
            if available else " and not available on this server: unsupported"))
    elif not hnsw:
        problems.append(f"pgvector {pv_version} is older than 0.5.0: no HNSW indexes")
    elif not visible:
        problems.append(f"pgvector is installed in schema {pv_schema!r}, which the foundation's "
                        f"search_path ({schema}, public) does not include; its vector columns "
                        "would silently fall back to BLOBs")
    return HealthReport(
        ok=not problems,
        server_version=version, server_version_num=version_num, ssl=ssl,
        max_connections=max_conn, pgvector_installed=installed, pgvector_version=pv_version,
        pgvector_schema=pv_schema, pgvector_hnsw=hnsw, pgvector_visible=visible,
        schema_exists=schema_exists, problems=tuple(problems), warnings=tuple(warnings))


def connection_kind(settings: DatabaseSettings) -> str:
    """direct | session_pooler | transaction_pooler | unknown, from documented URL shapes:
    Neon pooled hosts carry '-pooler'; Supabase's shared pooler is *.pooler.supabase.com,
    port 6543 = transaction mode, 5432 = session mode."""
    try:
        parts = urlsplit(settings.url or "")
        host, port = (parts.hostname or ""), parts.port
    except ValueError:
        return "unknown"
    if settings.provider == "neon":
        return "transaction_pooler" if "-pooler" in host.split(".")[0] else "direct"
    if settings.provider == "supabase":
        if port == 6543:
            return "transaction_pooler"
        return "session_pooler" if host.endswith(".pooler.supabase.com") else "direct"
    if settings.provider == "local":
        return "direct"
    return "unknown"


def main(argv=None) -> int:
    """Exit codes: 0 compatible, 2 configuration error, 4 unreachable, 5 incompatible."""
    try:
        settings = load_settings().database
        settings.require_url()
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    try:
        conn = connect(settings)
    except DatabaseUnavailable as exc:
        print(f"database error: {exc}", file=sys.stderr)
        return 4
    try:
        report = health_check(conn, settings.schema)
    finally:
        conn.close()
    out = {"provider": settings.provider, "url": settings.masked_url,
           "connection": connection_kind(settings), "sslmode": settings.ssl_mode,
           **report.as_dict()}
    print(json.dumps(out, indent=2))
    return 0 if report.ok else 5


if __name__ == "__main__":
    raise SystemExit(main())
