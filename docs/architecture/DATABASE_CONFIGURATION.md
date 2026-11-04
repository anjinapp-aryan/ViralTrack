# Database configuration

Status (2026-11-04): implemented.

| Item | Where |
|---|---|
| Settings | `viraltrack/config.py` (`DatabaseSettings`, `DATABASE_PROFILES`) |
| Runtime | `viraltrack/database.py` |
| Compose | `docker-compose.yml`, `deploy/compose.managed-db.yml` |
| Tests | `tests/test_database.py` |

Provider facts and the compatibility matrix are in
[../deployment/DATABASE_PROVIDER_COMPATIBILITY.md](../deployment/DATABASE_PROVIDER_COMPATIBILITY.md).

## 1. Current topology

```text
                        one PostgreSQL database (16 + pgvector)
                        schema: public (or NICHE_DB_SCHEMA)
                        tables, migrations, extension, RLS role: OWNED BY THE FOUNDATION
                                  ^                                   ^
   niche-finder web/worker/mcp    |                                   |  ViralTrack retention job
   POSTGRES_HOST/PORT/DB/USER/    |                                   |  DATABASE_URL (+ DATABASE_*)
   PASSWORD (+ PGSSLMODE)         |                                   |  1 connection, 1 transaction,
   psycopg2 ThreadedConnectionPool(1, 20) per process                 |  daily
   + 1 dedicated connection per advisory lock (worker singleton)      |
```

- **One database, foundation-owned.** niche-finder creates and migrates every table, the `vector` extension and
  its row-level-security role at start (`init_db`, upstream `infrastructure/postgres/schema.py`). ViralTrack
  owns **no tables**.
- **The retention job** (`python -m viraltrack.retention`) is ViralTrack's only database client. It reads and
  deletes foundation rows under the retention policy, so it must point at the foundation's database and schema.
- **Separate configuration, separate connections.**
  - The foundation reads `NICHE_DATABASE_URL`, or `POSTGRES_*` (its compose file blanks `NICHE_DATABASE_URL`
    inside containers), plus `NICHE_DB_SCHEMA`.
  - ViralTrack reads `DATABASE_*` only.

  Neither reads the other's variables; `test_foundation_does_not_read_viraltrack_database_settings` and
  `test_viraltrack_does_not_read_foundation_database_settings` enforce this. They never share a pool or a
  connection lifecycle.
- **Driver:** psycopg2 (`psycopg2-binary`), the same driver the foundation uses. No ORM, SQLAlchemy, asyncpg or
  psycopg 3 is involved anywhere; no dependency was added.

## 2. Configuration variables

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_PROVIDER` | `local` | Profile: `local`, `neon`, `supabase`, `aiven` or `postgres` (any other PostgreSQL). Anything else is an error |
| `DATABASE_URL` | unset | `postgresql://` or `postgres://` URL. **Secret.** Required for any provider other than `local`; required by the retention job always. Under compose, empty means the compose `postgres` service |
| `DATABASE_SCHEMA` | `public` | The foundation's schema (`NICHE_DB_SCHEMA` on its side). Plain identifier only |
| `DATABASE_SSL_MODE` | profile default | libpq `sslmode`. May also be in the URL. **Both set and different is an error** |
| `DATABASE_POOL_SIZE` | 2 (1–20) | Connections a pool keeps |
| `DATABASE_MAX_OVERFLOW` | 0 (0–20) | Extra connections under load, closed on return |
| `DATABASE_POOL_TIMEOUT` | 30 s (1–300) | Wait for a free pooled connection |
| `DATABASE_CONNECT_TIMEOUT` | 10 s (1–120) | libpq `connect_timeout`, per attempt |
| `DATABASE_STATEMENT_TIMEOUT` | 600000 ms (0 = off) | `SET LOCAL statement_timeout` per transaction |
| `DATABASE_APPLICATION_NAME` | `viraltrack` | Shown in `pg_stat_activity` (set per transaction) |

Earlier names `VT_DATABASE_URL` and `VT_DATABASE_SCHEMA` are still accepted. If an earlier name and its new
name are both set to different values, the configuration is refused. The retention container blanks the
earlier names, so a stale `.env` cannot conflict.

Validation happens at startup (`load_settings`) and fails fast with a `ConfigError` that names the variable.
The URL never appears in an error, in `describe()` or in a log. `DatabaseSettings.masked_url` is the printable
form, `postgresql://***@host:port/db?sslmode=…`, with the user, the password and every other parameter removed.

Environments: `VT_ENV=development|test|production`.
- Production with `DATABASE_PROVIDER=postgres` requires sslmode `require` or stronger.
- Managed profiles require it in every environment.
- Tests use `VT_TEST_DATABASE_URL`.

## 3. Profiles

Profiles hold requirements only, never URLs, hosts or credentials (tested).

| Profile | TLS minimum | TLS default | Notes |
|---|---|---|---|
| `local` | none | libpq default (`prefer`) | Docker compose network; a Unix-socket URL is allowed |
| `neon` | `require` | `require` | Neon rejects non-TLS; it recommends `verify-full` |
| `supabase` | `require` | `require` | TLS enforcement is optional on Supabase; ViralTrack requires it anyway |
| `aiven` | `require` | `require` | Aiven's URI uses `require`, which does not verify the CA; `verify-full` + CA file recommended |
| `postgres` | none (production: `require`) | libpq default | Explicit `DATABASE_SSL_MODE` recommended |

`connection_kind()` classifies the URL from documented shapes:
- Neon: a `-pooler` host is PgBouncer in transaction mode.
- Supabase: port 6543 is transaction mode; `*.pooler.supabase.com:5432` is session mode; otherwise direct.
- Aiven and generic: unknown.

The classification is reported by the check command and has no effect on business logic.

## 4. Connection management (`viraltrack/database.py`)

- **`connect(settings)`:** one connection.
  - Client-side libpq options only: `sslmode`, `connect_timeout`, TCP keepalives (idle 30 s, interval 10 s,
    3 probes).
  - Retries **connection** failures (`OperationalError`) 3 times with 1 s and 2 s backoff, which covers a Neon
    compute waking from scale-to-zero. It does not retry query errors.
  - It then raises `DatabaseUnavailable` with the masked URL.
- **`prepare_transaction(conn, settings)`:** `SET LOCAL statement_timeout`, `set_config('application_name', …, true)`
  and a fixed UTC offset (`SET LOCAL TIME ZONE INTERVAL '+00:00' HOUR TO MINUTE`). All are transaction-scoped,
  so they behave the same on a direct connection, a session pooler and a transaction pooler. ViralTrack never
  sends startup `options`, which some poolers reject.

  `'UTC'` is not used: a Windows PostgreSQL 16.2 build without the time-zone database rejected it during
  testing.
- **`ConnectionPool(settings)`:** psycopg2's `ThreadedConnectionPool`.
  - It keeps `pool_size` connections; up to `max_overflow` more are opened under load and closed on return.
  - A bounded semaphore enforces `pool_size + max_overflow` and waits at most `pool_timeout`.
  - On checkout, a connection that fails a `SELECT 1` probe is discarded and replaced (stale-connection
    handling; tested against a backend killed with `pg_terminate_backend`).
  - On return, the connection is rolled back; it is closed if broken. `close()` closes all.
- **`health_check(conn, schema)`:** read-only. Reports server version, whether TLS is in use (`pg_stat_ssl`),
  `max_connections`, pgvector (installed, version, schema, HNSW-capable ≥ 0.5.0, visible to the foundation's
  `search_path`) and whether the schema exists. Missing or unusable pgvector is a **problem** (not compatible),
  never hidden. A PostgreSQL other than 16 is a **warning** (untested).
- **`python -m viraltrack.database`:** runs the check and prints masked JSON. Exit codes: 0 compatible,
  2 configuration error, 4 unreachable, 5 incompatible.

**Connection budget:**

| Client | Connections |
|---|---|
| Retention job | **1**, for a few seconds a day (no pool: a daily single-transaction job gains nothing from one) |
| `ConnectionPool` | For any future long-running ViralTrack process. **No current ViralTrack component uses it** (the internal API, Batch 4, is deferred) |
| Foundation | Up to 20 per process (`ThreadedConnectionPool(1, 20)`), for `web`, `worker`, `mcp`, `mcp-http`, plus one per held advisory lock |

The foundation's 20 per process is upstream code. It is the figure to compare with a provider's limit; see the
compatibility document.

## 5. Foundation on a managed database (no upstream change)

```text
docker compose -f docker-compose.yml -f deploy/compose.managed-db.yml up -d web worker retention
```

1. Put the provider's **direct or session-mode** connection details in the root `.env` as
   `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD`. Upstream's compose
   interpolates them.
   - niche-finder builds `postgresql://user:password@host:port/db` itself, so percent-encode a password that
     contains `@ : / # ?`.
   - A transaction-mode pooler **must not** be used. niche-finder relies on session state: `SET search_path`
     and `SET ROLE` for row-level security per connection, and session advisory locks held on a dedicated
     connection. Neon and Supabase both list these features as unsupported in transaction mode.
2. `deploy/compose.managed-db.yml`:
   - sets `PGSSLMODE` (default `require`, from `FOUNDATION_DB_SSL_MODE`) and `PGAPPNAME` for `web`, `worker`,
     `mcp` and `mcp-http`. libpq reads them from the environment, so TLS needs no upstream change.
   - removes their dependency on the local `postgres` service (`depends_on: !reset {}`).
   - makes the retention job's `DATABASE_PROVIDER` and `DATABASE_URL` **required**. Compose refuses to start
     without them, so there is no silent fallback to the unused local database.
3. For `verify-ca` or `verify-full`, mount the provider's CA certificate and add `PGSSLROOTCERT` in a further
   override.
4. ViralTrack's `DATABASE_URL` may be the pooled URL, because the retention job uses only transaction-scoped
   settings. It must name the same database and schema as the foundation.

Verified: `docker compose … config` renders both setups. Without `DATABASE_URL` the managed setup fails with
"required variable DATABASE_URL is missing a value". **Not verified:** starting the stack against a managed
provider. No managed account exists and none was created.

## 6. Migration and schema ownership

- niche-finder alone creates and migrates its schema, on every start of `web`, and enables `vector` (best
  effort).
- ViralTrack runs no DDL, no migrations and no `CREATE EXTENSION`.
- There is no automatic destructive migration, no provisioning and no fallback to another database.
- Switching providers is a data move the operator performs (section 7); nothing in ViralTrack does it.

## 7. Switching providers

1. Stop the writers: `docker compose stop worker web retention`.
2. Back up the source database (`pg_dump -Fc`, or the provider's tool) and restore it into the target (an
   empty database with pgvector available).
3. In the target, as an admin:
   - `CREATE EXTENSION IF NOT EXISTS vector` in the foundation's schema or `public`. On Supabase the dashboard
     installs it into `extensions`, which niche-finder's `search_path` does not include.
   - Then run `python -m viraltrack.database` with the new settings and confirm exit 0, `pgvector_visible: true`
     and `ssl: true`.
4. Change the `POSTGRES_*` settings, `FOUNDATION_DB_SSL_MODE`, `DATABASE_PROVIDER` and `DATABASE_URL`.
5. Start `web` (its migrations run), then `worker` and `retention`. Check `docker compose logs retention`.

## 8. Known limitations

- No managed provider has been connected; their columns in the matrix are documentation-based.
- The foundation's DSN builder does not URL-encode `POSTGRES_PASSWORD` (upstream code).
- The foundation's pool size (20 per process) is not configurable without an upstream change. With the
  smallest plans of some providers this can exceed `max_connections` (see the compatibility document).
- pgvector is best-effort in the foundation: if `CREATE EXTENSION` fails, or the extension lives outside its
  `search_path`, niche-finder silently falls back to BLOB embeddings. ViralTrack's check reports this as a
  problem, but cannot prevent the fallback.
- `DatabaseSettings.ssl_mode` covers ViralTrack's connection only. The foundation's TLS is `PGSSLMODE` in its
  containers.
