"""Database configuration and connection lifecycle (any PostgreSQL provider).

Unit tests use fake connections. Tests marked `postgres` use a real server
from VT_TEST_DATABASE_URL (CI: pgvector/pgvector:pg16). No managed provider
(Neon, Supabase, Aiven) is contacted by any test: their profiles are tested
as configuration only, with placeholder URLs.
"""
import os
import re
import threading
import time

import psycopg2
import pytest

from tests.conftest import ROOT, UPSTREAM_BACKEND
from viraltrack import database as db
from viraltrack.config import DATABASE_PROFILES, load_settings, mask_database_url
from viraltrack.domain import ConfigError

SECRET = "pw-S3cr3t"


def settings(**env):
    return load_settings({k.upper(): v for k, v in env.items()}).database


def url(host="db.example.invalid", port=5432, dbname="app", query="", user="app"):
    return f"postgresql://{user}:{SECRET}@{host}:{port}/{dbname}{query}"


# 1-5. provider profiles ---------------------------------------------------------

def test_local_profile_is_the_default_and_forces_no_tls():
    s = settings()
    assert (s.provider, s.url, s.ssl_mode, s.schema) == ("local", None, None, "public")
    s = settings(database_url="postgresql://niches:niches@localhost:5433/niches")
    assert s.ssl_mode is None and db.connection_kind(s) == "direct"
    assert "sslmode" not in db.connect_kwargs(s)


def test_local_profile_accepts_a_unix_socket_url():
    assert settings(database_url="postgresql:///niches").url == "postgresql:///niches"


@pytest.mark.parametrize("host,kind", [
    ("ep-quiet-sky-123456.us-east-2.aws.neon.tech", "direct"),
    ("ep-quiet-sky-123456-pooler.us-east-2.aws.neon.tech", "transaction_pooler"),
])
def test_neon_profile(host, kind):
    s = settings(database_provider="neon", database_url=url(host=host))
    assert s.ssl_mode == "require"                      # Neon rejects non-TLS
    assert db.connection_kind(s) == kind
    s = settings(database_provider="neon", database_url=url(host=host, query="?sslmode=verify-full"))
    assert s.ssl_mode == "verify-full"


@pytest.mark.parametrize("host,port,user,kind", [
    ("db.abcdefghijklmnop.supabase.co", 5432, "postgres", "direct"),
    ("aws-0-eu-central-1.pooler.supabase.com", 5432, "postgres.abcdefghijklmnop", "session_pooler"),
    ("aws-0-eu-central-1.pooler.supabase.com", 6543, "postgres.abcdefghijklmnop",
     "transaction_pooler"),
])
def test_supabase_profile(host, port, user, kind):
    s = settings(database_provider="supabase",
                 database_url=url(host=host, port=port, dbname="postgres", user=user))
    assert s.ssl_mode == "require"
    assert db.connection_kind(s) == kind


def test_aiven_profile_with_ca_verification():
    u = url(host="pg-example.aivencloud.com", port=12345, dbname="defaultdb",
            query="?sslmode=verify-full&sslrootcert=/run/secrets/aiven-ca.pem")
    s = settings(database_provider="aiven", database_url=u)
    assert s.ssl_mode == "verify-full"
    assert db.connection_kind(s) == "unknown"
    assert "aiven-ca.pem" not in s.masked_url            # only sslmode is shown


def test_generic_profile():
    s = settings(database_provider="postgres", database_url=url())
    assert s.ssl_mode is None and db.connection_kind(s) == "unknown"
    with pytest.raises(ConfigError, match="require or stronger in production"):
        load_settings({"VT_ENV": "production", "DATABASE_PROVIDER": "postgres",
                       "DATABASE_URL": url()})
    ok = load_settings({"VT_ENV": "production", "DATABASE_PROVIDER": "postgres",
                        "DATABASE_URL": url(), "DATABASE_SSL_MODE": "verify-full"})
    assert ok.database.ssl_mode == "verify-full"


def test_profiles_hold_no_urls_or_credentials():
    for profile in DATABASE_PROFILES.values():
        assert not any("://" in str(v) or "@" in str(v) for v in profile.__dict__.values())
    assert set(DATABASE_PROFILES) == {"local", "neon", "supabase", "aiven", "postgres"}


# 6-8. missing, invalid, unsupported -------------------------------------------------

@pytest.mark.parametrize("provider", ["neon", "supabase", "aiven", "postgres"])
def test_managed_or_generic_provider_without_url_fails_fast(provider):
    with pytest.raises(ConfigError, match="DATABASE_URL is not set"):
        settings(database_provider=provider)


def test_require_url_when_a_component_needs_the_database():
    with pytest.raises(ConfigError, match="DATABASE_URL is not set"):
        settings().require_url()


@pytest.mark.parametrize("bad,match", [
    (f"mysql://app:{SECRET}@h/app", "postgresql://"),
    (f"host=h user=app password={SECRET} dbname=app", "postgresql://"),
    (f"postgresql://app:{SECRET}@h:99999/app", "port"),
    (f"postgresql://app:{SECRET}@h:abc/app", "valid URL"),
    (f"postgresql://app:{SECRET}@h:5432/", "database name"),
    (f"postgresql://app:{SECRET}@h/app?sslmode=sometimes", "sslmode"),
])
def test_invalid_connection_string_never_echoed(bad, match):
    with pytest.raises(ConfigError, match=match) as err:
        settings(database_provider="postgres", database_url=bad)
    assert SECRET not in str(err.value)


def test_managed_url_without_host_rejected():
    with pytest.raises(ConfigError, match="no host"):
        settings(database_provider="neon", database_url="postgresql:///app")


@pytest.mark.parametrize("provider", ["mysql", "sqlite", "neondb", ""])
def test_unsupported_provider(provider):
    if provider == "":
        assert settings(database_provider="").provider == "local"
        return
    with pytest.raises(ConfigError, match="DATABASE_PROVIDER"):
        settings(database_provider=provider, database_url=url())


def test_legacy_variable_names_still_work_but_must_not_conflict():
    s = load_settings({"VT_DATABASE_URL": url(), "VT_DATABASE_SCHEMA": "demo"}).database
    assert (s.url, s.schema) == (url(), "demo")
    with pytest.raises(ConfigError, match="differ"):
        load_settings({"VT_DATABASE_URL": url(), "DATABASE_URL": url(dbname="other")})
    with pytest.raises(ConfigError, match="identifier"):
        load_settings({"DATABASE_SCHEMA": "public; DROP TABLE videos"})


# 9. TLS -------------------------------------------------------------------------

@pytest.mark.parametrize("provider", ["neon", "supabase", "aiven"])
@pytest.mark.parametrize("weak", ["disable", "allow", "prefer"])
def test_managed_profiles_refuse_weak_tls(provider, weak):
    with pytest.raises(ConfigError, match="require or stronger"):
        settings(database_provider=provider, database_url=url(), database_ssl_mode=weak)
    with pytest.raises(ConfigError, match="require or stronger"):
        settings(database_provider=provider, database_url=url(query=f"?sslmode={weak}"))


def test_ssl_mode_conflict_and_validation():
    with pytest.raises(ConfigError, match="conflicts"):
        settings(database_provider="neon", database_url=url(query="?sslmode=require"),
                 database_ssl_mode="verify-full")
    with pytest.raises(ConfigError, match="DATABASE_SSL_MODE must be one of"):
        settings(database_url=url(), database_ssl_mode="on")
    s = settings(database_provider="aiven", database_url=url(), database_ssl_mode="verify-ca")
    assert db.connect_kwargs(s)["sslmode"] == "verify-ca"


# 10. pool configuration and lifecycle (fake pool) -----------------------------------

def test_pool_settings_defaults_and_bounds():
    s = settings()
    assert (s.pool_size, s.max_overflow, s.pool_timeout, s.connect_timeout) == (2, 0, 30, 10)
    assert s.statement_timeout_ms == 600_000 and s.application_name == "viraltrack"
    assert settings(database_pool_size="5", database_max_overflow="3").max_connections == 8
    for key, value in [("database_pool_size", "0"), ("database_pool_size", "21"),
                       ("database_max_overflow", "-1"), ("database_pool_timeout", "0"),
                       ("database_connect_timeout", "121"), ("database_statement_timeout", "x"),
                       ("database_application_name", "has space")]:
        with pytest.raises(ConfigError):
            settings(**{key: value})


class FakeConn:
    def __init__(self, alive=True):
        self.closed = 0
        self.alive = alive
        self.rollbacks = 0
        self.executed = []

    def cursor(self):
        conn = self

        class Cur:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=None):
                if not conn.alive:
                    raise psycopg2.OperationalError("server closed the connection unexpectedly")
                conn.executed.append((sql, params))

            def fetchone(self):
                return (1,)
        return Cur()

    def rollback(self):
        if not self.alive:
            raise psycopg2.InterfaceError("connection already closed")
        self.rollbacks += 1


class FakePool:
    def __init__(self, minconn, maxconn, dsn, **kwargs):
        self.args = (minconn, maxconn, dsn, kwargs)
        self.queue = []
        self.made = []
        self.returned = []

    def getconn(self):
        conn = self.queue.pop(0) if self.queue else FakeConn()
        self.made.append(conn)
        return conn

    def putconn(self, conn, close=False):
        self.returned.append((conn, close))

    def closeall(self):
        self.closed_all = True


def make_pool(**env):
    s = settings(database_url=url(), **env)
    holder = {}

    def factory(*a, **k):
        holder["pool"] = FakePool(*a, **k)
        return holder["pool"]
    return db.ConnectionPool(s, _pool_factory=factory), holder["pool"], s


def test_pool_is_sized_from_settings_and_passes_client_side_options():
    pool, fake, s = make_pool(database_pool_size="3", database_max_overflow="2",
                              database_ssl_mode="require")
    minconn, maxconn, dsn, kwargs = fake.args
    assert (minconn, maxconn, dsn) == (3, 5, s.url)
    assert kwargs["sslmode"] == "require" and kwargs["connect_timeout"] == 10
    assert kwargs["keepalives"] == 1
    assert "options" not in kwargs        # poolers may reject startup options


def test_pool_replaces_a_stale_connection_and_rolls_back_on_return():
    pool, fake, _ = make_pool()
    stale = FakeConn(alive=False)
    fake.queue = [stale]
    with pool.connection() as conn:
        assert conn is not stale and conn.alive
    assert fake.returned[0] == (stale, True)            # discarded
    assert fake.returned[1] == (conn, False) and conn.rollbacks >= 1


def test_pool_closes_a_connection_that_broke_during_use():
    pool, fake, _ = make_pool()
    with pool.connection() as conn:
        conn.alive = False
    assert fake.returned[-1] == (conn, True)


def test_pool_waits_at_most_pool_timeout_then_fails_without_the_url():
    pool, fake, _ = make_pool(database_pool_size="1", database_pool_timeout="1")
    entered = threading.Event()
    release = threading.Event()

    def hold():
        with pool.connection():
            entered.set()
            release.wait(5)
    t = threading.Thread(target=hold)
    t.start()
    entered.wait(5)
    start = time.monotonic()
    with pytest.raises(db.DatabaseUnavailable, match="no free database connection") as err:
        with pool.connection():
            pass
    assert 0.9 <= time.monotonic() - start < 3
    assert SECRET not in str(err.value)
    release.set()
    t.join()
    with pool.connection():                              # slot came back
        pass


# 11. masking ----------------------------------------------------------------------

def test_password_and_parameters_masked_everywhere():
    u = url(query=f"?sslmode=require&password={SECRET}&sslpassword={SECRET}")
    s = settings(database_provider="neon", database_url=u)
    assert SECRET not in s.masked_url and "app:" not in s.masked_url
    assert s.masked_url == "postgresql://***@db.example.invalid:5432/app?sslmode=require"
    described = str(load_settings({"DATABASE_PROVIDER": "neon", "DATABASE_URL": u}).describe())
    assert SECRET not in described
    assert mask_database_url("not a url") == "set"
    assert mask_database_url("postgresql://u:p@[bad/x") == "set (unparseable)"


# 12. health check (fake cursor) and 13. reconnection --------------------------------

class ScriptedConn:
    """Answers health_check's queries from a script."""

    def __init__(self, ext=None, available=("0.8.0",), version=("16.4", 160004), ssl=True,
                 schema_exists=True):
        self.answers = {
            "server_version": (version[0], version[1], 100),
            "pg_stat_ssl": (ssl,),
            "pg_extension": ext,
            "pg_available_extensions": available,
            "pg_namespace WHERE": (1,) if schema_exists else None,
        }
        self.closed = 0

    def cursor(self):
        conn = self

        class Cur:
            last = None

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=None):
                self.last = next(k for k in conn.answers if k in sql)

            def fetchone(self):
                return conn.answers[self.last]
        return Cur()

    def rollback(self):
        pass


def test_health_check_reports_a_compatible_server():
    r = db.health_check(ScriptedConn(ext=("0.8.0", "public")))
    assert r.ok and r.pgvector_hnsw and r.pgvector_visible and r.ssl is True
    assert r.problems == () and r.warnings == ()


@pytest.mark.parametrize("conn,problem", [
    (ScriptedConn(ext=None, available=None), "not available on this server: unsupported"),
    (ScriptedConn(ext=None, available=("0.8.0",)), "run CREATE EXTENSION vector"),
    (ScriptedConn(ext=("0.4.4", "public")), "older than 0.5.0"),
    (ScriptedConn(ext=("0.8.0", "extensions")), "silently fall back"),
])
def test_health_check_reports_pgvector_problems_instead_of_hiding_them(conn, problem):
    r = db.health_check(conn)
    assert not r.ok and any(problem in p for p in r.problems)


def test_health_check_warns_on_untested_postgres_versions():
    r = db.health_check(ScriptedConn(ext=("0.8.0", "public"), version=("15.8", 150008)))
    assert r.ok and r.warnings and "only 16" in r.warnings[0]


def test_connect_retries_connection_failures_then_succeeds():
    calls, sleeps = [], []

    def flaky(dsn, **kwargs):
        calls.append(kwargs)
        if len(calls) < 3:
            raise psycopg2.OperationalError("could not connect: compute is starting")
        return "conn"
    s = settings(database_provider="neon", database_url=url())
    assert db.connect(s, sleep=sleeps.append, _connect=flaky) == "conn"
    assert sleeps == [1.0, 2.0] and calls[0]["sslmode"] == "require"


def test_connect_gives_up_without_leaking_the_url():
    def down(dsn, **kwargs):
        raise psycopg2.OperationalError(
            f'connection to server at "db.example.invalid" failed: password {SECRET} rejected')
    s = settings(database_provider="neon", database_url=url())
    with pytest.raises(db.DatabaseUnavailable) as err:
        db.connect(s, sleep=lambda _: None, _connect=down)
    assert SECRET not in str(err.value) and "db.example.invalid:5432/app" in str(err.value)
    assert "after 3 attempts" in str(err.value)


def test_connect_does_not_retry_other_errors():
    calls = []

    def broken(dsn, **kwargs):
        calls.append(1)
        raise psycopg2.ProgrammingError("invalid dsn")
    with pytest.raises(psycopg2.ProgrammingError):
        db.connect(settings(database_url=url()), sleep=lambda _: None, _connect=broken)
    assert calls == [1]


def test_prepare_transaction_uses_only_transaction_scoped_settings():
    conn = FakeConn()
    db.prepare_transaction(conn, settings(database_statement_timeout="1234"))
    sql = [s for s, _ in conn.executed]
    assert all("LOCAL" in s or "set_config" in s and ", true)" in s for s in sql)
    assert ("SET LOCAL statement_timeout = %s", (1234,)) in conn.executed


# 15. upstream isolation ---------------------------------------------------------------

_ENV_READ = re.compile(r"""environ(?:\.get)?\(\s*["']([A-Z_][A-Z0-9_]*)|environ\[\s*["']([A-Z_][A-Z0-9_]*)""")


def _env_names(paths):
    names = set()
    for path in paths:
        for a, b in _ENV_READ.findall(path.read_text(encoding="utf-8", errors="replace")):
            names.add(a or b)
    return names


def test_foundation_does_not_read_viraltrack_database_settings():
    upstream = _env_names(p for p in UPSTREAM_BACKEND.rglob("*.py") if "tests" not in p.parts)
    assert {"NICHE_DATABASE_URL", "POSTGRES_HOST", "NICHE_DB_SCHEMA"} <= upstream
    assert not {n for n in upstream if n.startswith("DATABASE_")}
    assert "VT_DATABASE_URL" not in upstream


def test_viraltrack_does_not_read_foundation_database_settings():
    ours = _env_names((ROOT / "viraltrack").rglob("*.py"))
    assert not {n for n in ours if n.startswith(("POSTGRES_", "NICHE_", "PG"))}
    config = (ROOT / "viraltrack" / "config.py").read_text(encoding="utf-8")
    assert not re.search(r"\b(POSTGRES_[A-Z]+|NICHE_DATABASE_URL)\b", config)


def test_compose_gives_database_url_only_to_the_retention_service():
    base = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    services = base.split("\nservices:\n")[1]
    assert services.lstrip().startswith("retention:")    # the only service ViralTrack defines
    assert 'VT_DATABASE_URL: ""' in services            # a stale legacy value cannot conflict
    override = (ROOT / "deploy" / "compose.managed-db.yml").read_text(encoding="utf-8")
    foundation = override.split("  retention:")[0]
    assert "DATABASE_URL" not in foundation.split("services:")[1]
    assert "PGSSLMODE" in foundation and "!reset" in foundation


def test_env_example_has_placeholders_only():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    for line in text.splitlines():
        m = re.search(r"postgres(?:ql)?://([^\s@]+)@", line)
        if m and not line.lstrip().startswith("#"):
            pytest.fail(f"active connection string in .env.example: {line}")
        if m:
            assert m.group(1).startswith("<") or m.group(1) == "<user>:<password>", line


# 12-14, 16. real PostgreSQL ----------------------------------------------------------

def _real():
    url_ = os.environ.get("VT_TEST_DATABASE_URL")
    if not url_:
        pytest.skip("VT_TEST_DATABASE_URL not set")
    return load_settings({"DATABASE_PROVIDER": "postgres", "DATABASE_URL": url_}).database


@pytest.mark.postgres
def test_real_health_check_and_pgvector():
    s = _real()
    conn = db.connect(s)
    try:
        report = db.health_check(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM pg_available_extensions WHERE name = 'vector'")
            available = cur.fetchone()[0] == 1
        conn.rollback()
    finally:
        conn.close()
    assert report.server_version_num and report.max_connections
    if os.environ.get("VT_TEST_REQUIRE_PGVECTOR") == "1":
        assert available, "this server must ship pgvector"
    if not report.pgvector_installed:
        assert any("pgvector is not installed" in p for p in report.problems)
        assert ("run CREATE EXTENSION" in report.problems[0]) == available


@pytest.mark.postgres
def test_real_pgvector_hnsw_index_can_be_created():
    s = _real()
    conn = db.connect(s)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM pg_available_extensions WHERE name = 'vector'")
            if cur.fetchone()[0] == 0:
                conn.rollback()
                if os.environ.get("VT_TEST_REQUIRE_PGVECTOR") == "1":
                    pytest.fail("pgvector required but not available")
                pytest.skip("pgvector not available on this server")
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute("CREATE TEMP TABLE vt_vec (v vector(3))")
            cur.execute("CREATE INDEX ON vt_vec USING hnsw (v vector_cosine_ops)")
            cur.execute("INSERT INTO vt_vec VALUES ('[1,0,0]'), ('[0,1,0]')")
            cur.execute("SELECT v <=> '[1,0,0]' FROM vt_vec ORDER BY 1 LIMIT 1")
            assert cur.fetchone()[0] == pytest.approx(0.0)
        conn.commit()
        report = db.health_check(conn)
        assert report.pgvector_installed and report.pgvector_hnsw, report.problems
    finally:
        conn.close()


@pytest.mark.postgres
def test_real_session_settings_apply_inside_the_transaction_only():
    s = _real()
    s = load_settings({"DATABASE_PROVIDER": "postgres", "DATABASE_URL": s.url,
                       "DATABASE_STATEMENT_TIMEOUT": "4321",
                       "DATABASE_APPLICATION_NAME": "vt-test"}).database
    conn = db.connect(s)
    try:
        db.prepare_transaction(conn, s)
        with conn.cursor() as cur:
            cur.execute("SHOW statement_timeout")
            assert cur.fetchone()[0] == "4321ms"
            cur.execute("SHOW application_name")
            assert cur.fetchone()[0] == "vt-test"
            cur.execute("SELECT EXTRACT(TIMEZONE FROM now())")
            assert cur.fetchone()[0] == 0
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("SHOW statement_timeout")
            assert cur.fetchone()[0] != "4321ms"        # nothing leaks into the session
        conn.rollback()
    finally:
        conn.close()


@pytest.mark.postgres
def test_real_pool_reconnects_after_the_server_drops_a_connection():
    s = _real()
    pool = db.ConnectionPool(load_settings({"DATABASE_PROVIDER": "postgres", "DATABASE_URL": s.url,
                                            "DATABASE_POOL_SIZE": "1"}).database)
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_backend_pid()")
                pid = cur.fetchone()[0]
        killer = db.connect(s)
        killer.autocommit = True
        with killer.cursor() as cur:
            cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
        killer.close()
        time.sleep(0.2)
        with pool.connection() as conn:                  # stale one replaced
            with conn.cursor() as cur:
                cur.execute("SELECT pg_backend_pid()")
                assert cur.fetchone()[0] != pid
    finally:
        pool.close()


@pytest.mark.postgres
def test_retention_cli_connects_through_the_shared_settings(pg_schema, monkeypatch, capsys):
    from viraltrack.retention.__main__ import main
    _, schema = pg_schema
    monkeypatch.setenv("DATABASE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", os.environ["VT_TEST_DATABASE_URL"])
    monkeypatch.setenv("DATABASE_SCHEMA", schema)
    for legacy in ("VT_DATABASE_URL", "VT_DATABASE_SCHEMA"):
        monkeypatch.delenv(legacy, raising=False)
    assert main([]) == 0
    assert '"applied": false' in capsys.readouterr().out


def test_retention_cli_unreachable_database_exits_4(monkeypatch, capsys):
    from viraltrack.retention import __main__ as cli
    monkeypatch.setenv("DATABASE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", f"postgresql://app:{SECRET}@127.0.0.1:1/app")
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT", "1")
    monkeypatch.setattr(db.time, "sleep", lambda _: None)
    assert cli.main([]) == 4
    err = capsys.readouterr().err
    assert "after 3 attempts" in err and SECRET not in err


def test_retention_cli_missing_url_exits_2(monkeypatch, capsys):
    from viraltrack.retention.__main__ import main
    for key in ("DATABASE_URL", "VT_DATABASE_URL", "DATABASE_PROVIDER"):
        monkeypatch.delenv(key, raising=False)
    assert main([]) == 2
    assert "DATABASE_URL is not set" in capsys.readouterr().err


def test_check_command_exit_codes(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_PROVIDER", "neon")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("VT_DATABASE_URL", raising=False)
    assert db.main([]) == 2
    monkeypatch.setenv("DATABASE_URL", f"postgresql://app:{SECRET}@127.0.0.1:1/app")
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT", "1")
    monkeypatch.setattr(db.time, "sleep", lambda _: None)
    assert db.main([]) == 4
    assert SECRET not in capsys.readouterr().err

