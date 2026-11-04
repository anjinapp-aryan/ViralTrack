# Database provider compatibility

Date: 2026-11-04. Configuration design: [../architecture/DATABASE_CONFIGURATION.md](../architecture/DATABASE_CONFIGURATION.md).

Evidence levels used below:

- **Tested:** a real connection was made and the tests ran.
- **Documented:** taken from the provider's official documentation, read on 2026-11-04. Not connected.
- **Unverified:** neither tested nor stated in the documentation that was read.

No Neon, Supabase or Aiven account was created or connected. Every managed-provider cell is "Documented" at
best.

## What the stack needs from PostgreSQL

| Requirement | Why | Source |
|---|---|---|
| PostgreSQL 16 (tested) | Upstream CI and compose use `pgvector/pgvector:pg16` | upstream `docker-compose.yml`, CI |
| `vector` extension ≥ 0.5.0, visible to the foundation's `search_path` (its schema or `public`) | HNSW indexes on `videos.embedding_v` / `thumb_embedding_v`; `hnsw.iterative_scan` (0.8.0+) is used if present, best effort | upstream `schema.py` `_ensure_pgvector` |
| `CREATE EXTENSION` privilege (once), `CREATE ROLE` (row-level-security role, best effort) | Foundation `init_db` | upstream `schema.py` |
| JSONB, GIN on `to_tsvector`, B-tree | Upstream DDL | upstream `schema.py` |
| **Session semantics** for the foundation: per-connection `SET search_path` and `SET ROLE`, session advisory locks on a long-lived connection | Upstream `connection.py` | upstream code |
| Transaction-scoped settings only for ViralTrack (`SET LOCAL`, `set_config(…, true)`) | Portable through any pooler | `viraltrack/database.py` |
| Timestamps | Upstream stores ISO-8601 text with an offset (`datetime.now(timezone.utc).isoformat()`). Retention casts with `::timestamptz` and sets a fixed UTC offset per transaction, so server `TimeZone` does not matter | upstream `schema.py` `now_iso`, `viraltrack/retention/job.py` |
| Isolation | Default READ COMMITTED; the retention job runs in one transaction and commits only with `--apply` | `job.py` |

## Compatibility matrix

| | Local Docker | Neon | Supabase | Aiven | Generic PostgreSQL |
|---|---|---|---|---|---|
| Profile `DATABASE_PROVIDER` | `local` | `neon` | `supabase` | `aiven` | `postgres` |
| Config validation | Tested (unit) | Tested (unit, placeholder URLs) | Tested (unit, placeholder URLs) | Tested (unit, placeholder URLs) | Tested (unit) |
| Real connection | **Tested**: PostgreSQL 16.2 (pgserver, Windows) | Not tested | Not tested | Not tested | **Tested**: same server as `postgres` profile. CI will run `pgvector/pgvector:pg16` once pushed |
| TLS | Not forced | Documented: required; `verify-full` recommended; `channel_binding=require` supported | Documented: optional enforcement; `require` recommended; CA download for `verify-full`. ViralTrack requires ≥ `require` | Documented: URI uses `require` (no CA check); `verify-ca` with the project CA recommended; CA rotates | As configured; production requires ≥ `require` |
| pgvector | **Tested**: 0.6.2, HNSW index and cosine query | Documented: available on all plans; HNSW and IVFFlat; `CREATE EXTENSION vector` | Documented: available; enabled into schema `extensions` by default. **Must be installed in `public` or the foundation's schema** (see below). HNSW only mentioned | Documented: available, `CREATE EXTENSION vector` per database; HNSW **not documented** (only IVFFlat shown); version not stated | Depends on server |
| Direct connection | Yes | Documented: `ep-<id>.<region>.aws.neon.tech` | Documented: `db.<ref>.supabase.co:5432`, **IPv6 only** on Free/Pro without the IPv4 add-on | Documented: service URI | Yes |
| Pooler | — | Documented: PgBouncer **transaction** mode, host adds `-pooler`; session `SET`, advisory locks, `LISTEN` unsupported | Documented: Supavisor shared pooler `*.pooler.supabase.com`, port 5432 **session** mode and 6543 **transaction** mode, user `postgres.<ref>`, IPv4. Dedicated pooler (Pro+) transaction only | Documented: PgBouncer, transaction (default), session or statement mode; startup plan or higher | — |
| Foundation may use | the compose service | **direct only** | **direct (IPv6/add-on) or session pooler** | **direct**, or a pool in **session** mode | direct |
| Retention job may use | any | direct or pooled | any | any | any |
| Connection limits (smallest documented) | 100 (default `max_connections`) | Documented: 0.25 CU = 104 `max_connections`, 97 usable; pooled up to 10,000 clients | Documented: Nano (free) 60 direct, pooler 200 clients, pool size 15 | Documented: Developer 15, Free 20, Hobbyist 25, Startup-4 100; 3–6 reserved | Server setting |
| Scale-to-zero / pausing | — | Documented: suspends after 5 min inactive (free plan fixed), reactivates "within a few hundred milliseconds"; session state resets | Unverified here (free projects can be paused; not read today) | Unverified | — |
| `CREATE ROLE` / `CREATE EXTENSION` for the admin user | Yes (superuser) | Unverified | Unverified | Unverified (not stated on the pages read) | Depends |
| **Verdict** | **Supported, tested** | **Expected compatible (documented), untested** | **Expected compatible with the pgvector schema step (documented), untested** | **Expected compatible for the foundation if HNSW works (unverified), untested** | **Supported if PG16 + pgvector ≥ 0.5** |

Sources:

- Neon:
  - neon.com/docs/connect/connection-pooling
  - neon.com/docs/connect/connect-securely
  - neon.com/docs/extensions/pgvector
  - neon.com/docs/introduction/scale-to-zero
- Supabase:
  - supabase.com/docs/guides/database/connecting-to-postgres
  - supabase.com/docs/guides/platform/ssl-enforcement
  - supabase.com/docs/guides/database/extensions/pgvector
  - supabase.com/docs/guides/platform/compute-and-disk
- Aiven:
  - aiven.io/docs/products/postgresql/howto/connect-python
  - aiven.io/docs/products/postgresql/concepts/pg-connection-pooling
  - aiven.io/docs/products/postgresql/reference/pg-connection-limits
  - aiven.io/docs/products/postgresql/howto/use-pgvector
  - aiven.io/docs/platform/concepts/tls-ssl-certificates

## pgvector findings

- **Local, tested.** pgvector 0.6.2 is installed in `public`.
  - `test_real_pgvector_hnsw_index_can_be_created` created an HNSW index with `vector_cosine_ops` and ran a
    cosine query.
  - `python -m viraltrack.database` reported `pgvector_hnsw: true` and `pgvector_visible: true`, and exited 0.
- **CI.** The ViralTrack job now uses `pgvector/pgvector:pg16` with `VT_TEST_REQUIRE_PGVECTOR=1`, so a server
  without pgvector fails the run instead of skipping. It had been `postgres:16`, without pgvector.
- **Supabase.** The dashboard and its documented SQL install `vector` into schema `extensions`.
  - niche-finder sets `search_path TO "<schema>", public` and creates `vector(384)` columns, so the type would
    not resolve. The best-effort upgrade fails and niche-finder **silently** keeps BLOB embeddings.
  - ViralTrack's check reports this as "installed in schema 'extensions' … would silently fall back". It is a
    problem, exit code 5.
  - Fix as an admin before the foundation's first start: `CREATE EXTENSION vector WITH SCHEMA public;`, or
    `ALTER EXTENSION vector SET SCHEMA public;` if it is already enabled.
- **Aiven.** Its page shows only IVFFlat. HNSW needs pgvector ≥ 0.5.0; run the check command on the service
  and read `pgvector_version` / `pgvector_hnsw` before relying on it.
- **pgvector is never removed or replaced** by ViralTrack. A missing extension is reported as unsupported.

## Connection budget against provider limits

The foundation opens connections on demand, up to 20 per process (`web`, `worker`, `mcp`, `mcp-http`), plus
one held connection per advisory lock. The retention job adds 1.

| Provider (smallest documented plan) | Limit | Risk |
|---|---|---|
| Neon 0.25 CU | 97 usable direct | Low for `web` + `worker` (≤ 40 + locks) |
| Supabase Nano | 60 direct; session pooler pool size 15 by default | **Medium.** `web` + `worker` can reach 40+. With the session pooler, its pool size (15) caps concurrent sessions, so raise it in the dashboard or keep MCP services off |
| Aiven Developer / Free / Hobbyist | 15 / 20 / 25 (minus 3–6 reserved) | **High.** One busy foundation process can exhaust them. Use Startup-4 (100) or larger |

The foundation's pool maximum is upstream code. Lowering it would need an upstream change, which is out of
scope.

## Provider setup

All values come from the provider's dashboard. Never compose hosts by hand, and never commit them.

- **Local Docker.** Nothing to set: `docker compose up -d postgres web worker retention`. To run ViralTrack on the
  host, use `DATABASE_URL=postgresql://<user>:<password>@localhost:5433/<db>` (upstream publishes Postgres on
  127.0.0.1:5433).
- **Neon.**
  - Console → project → **Connect**, which shows the pooled and direct connection strings; the pooled host has
    `-pooler`.
  - Foundation: the **direct** host in `POSTGRES_*`. ViralTrack: either; set `DATABASE_PROVIDER=neon`.
  - TLS: `verify-full` recommended (Neon docs). Which CA to trust was not read today; follow
    Neon's "connect securely" page.
- **Supabase.**
  - Project → **Connect**: direct connection, session pooler or transaction pooler.
  - Foundation: **session pooler** (IPv4) or direct (needs IPv6 or the IPv4 add-on).
  - ViralTrack: any; set `DATABASE_PROVIDER=supabase`.
  - Install pgvector into `public` first (above).
  - For `verify-full`, download the CA from Database Settings → SSL Configuration.
- **Aiven.**
  - Service → Overview → Connection information gives the **Service URI** and the CA certificate.
  - Set `DATABASE_PROVIDER=aiven`, using `sslmode=verify-full&sslrootcert=<path>` (or `verify-ca`).
  - Keep the CA bundle current, because Aiven rotates it.
  - If you use Aiven's PgBouncer pool for the foundation, configure it in **session** mode.
- **Generic.** Any PostgreSQL 16 with pgvector ≥ 0.5.0. Set `DATABASE_PROVIDER=postgres` and an explicit
  `DATABASE_SSL_MODE` (production: ≥ `require`).

After any setup, run `python -m viraltrack.database` (masked output; exit 0 means compatible).

## Backup and recovery (owner / counsel review)

- Provider backups and point-in-time restore keep **deleted rows** for the provider's backup window.
- The retention policy deletes YouTube data after 30 days (statistics up to 36 months only with the amendment).
- Whether backups that outlive that window are acceptable under YouTube's policies is a question for counsel.
  Until it is answered, keep the backup or history window at or below 30 days where the plan allows it, and
  record the setting in DATA_RETENTION_POLICY.md.
- A restore can bring back rows that were already deleted. **Run the retention job right after every restore.**
- Neither the backup windows nor the restore procedures of these providers were verified today; read the
  provider's backup page for the chosen plan.

## Recommendation for the first deployment

**Neon, with the direct connection for the foundation.**

- It is the only one of the three whose documentation states mandatory TLS, pgvector with HNSW on every plan,
  and roughly 97 usable connections on the smallest compute (enough for `web` + `worker`).
- Scale-to-zero is cheap for a low-traffic start. The worker keeps it active while it runs; whether open
  connections prevent suspension is not stated in the pages read.

Before relying on it:

1. Run `python -m viraltrack.database` against the real Neon database.
2. Run the ViralTrack suite with `VT_TEST_DATABASE_URL` pointing at a **separate test branch**, never at real
   data.
3. Check that the backup and history window agrees with retention.

Supabase is the alternative if its other services are wanted. It needs the pgvector schema step and the session
pooler on IPv4 networks. Aiven's small plans are too small for the foundation's connection use.
