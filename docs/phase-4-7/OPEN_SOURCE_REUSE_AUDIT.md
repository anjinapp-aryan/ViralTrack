# Open-source reuse audit for phases 4 to 7

Date: 2026-11-07. Method: repository metadata from `gh api repos/<repo>` (licence identifier, last push, archived flag, stars) on this date. For every project whose identifier was missing or "NOASSERTION" the actual LICENSE file was read with `gh api repos/<repo>/license`; those rows say "file read". Other identifiers are GitHub's detection of a standard licence text. Nothing was installed, cloned or executed. Not reviewed for any candidate: test coverage, dependency tree, security posture, issue backlog; review those before adopting any dependency.

This supplements [../phase-3/OPEN_SOURCE_REUSE_AUDIT.md](../phase-3/OPEN_SOURCE_REUSE_AUDIT.md), whose licence column rested on listing-level data. GitHub access was available, so the audit is complete for the candidates listed; it is not exhaustive for the whole ecosystem.

Search order: this repository, current dependencies (`httpx`, `psycopg2-binary`), the pinned foundation, then GitHub.

## 1. Already available (checked first)

| Capability | Where it exists | Decision |
|---|---|---|
| Collection, quota guard, worker, snapshots | foundation (MIT, pinned `d872014`) | REUSE in place |
| Watchlist, alerts, digest, channel history, trajectory | foundation HTTP API (internal-only) | COMPOSE through its API, behind `MetricPolicy` |
| HTTP framework, validation, OpenAPI | foundation uses FastAPI and pydantic | REUSE the same stack if D5 is authorized |
| "What each number is" documentation | foundation `GET /api/scores` | REUSE as source text for D4, after policy review |
| Provenance, retention, metric policy, domain models | this repository | ADAPT for D4 explanations |
| Test framework, mock transports, synthetic corpus | this repository (pytest) | REUSE |

## 2. External candidates

| Capability | Candidate (repository) | Licence | Last push, stars | Reason | Decision |
|---|---|---|---|---|---|
| API framework (D5) | fastapi/fastapi | MIT | 2026-11-06, 104,532 | Same framework as the foundation; automatic OpenAPI | REUSE if D5 authorized |
| API framework | pallets/flask | BSD-3-Clause | 2026-10-30, 75,056 | Second stack next to the foundation's | REJECT |
| API framework | litestar-org/litestar | MIT | 2026-11-06, 8,536 | Second stack | REJECT |
| Validation | pydantic/pydantic | MIT | 2026-11-06, 29,354 | Foundation already uses it; domain uses dataclasses by choice | REUSE only at the D5 API boundary |
| Contract testing | schemathesis/schemathesis | MIT | 2026-11-06, 3,750 | Property-based tests from an OpenAPI schema; finds leaked fields and 500s | Dev-only dependency in D5, owner to approve |
| Dashboard | streamlit/streamlit | Apache-2.0 | 2026-11-07, 46,247 | Separate server, own state model, heavy tree | REJECT for now |
| Dashboard | plotly/dash | MIT | 2026-11-06, 24,478 | Second web stack | REJECT for now |
| BI | apache/superset | Apache-2.0 | 2026-11-07, 75,444 | Own metadata DB and service; queries tables directly and would bypass `MetricPolicy` | REJECT |
| BI | metabase/metabase | AGPL core, commercial enterprise (file read) | 2026-11-07, 50,216 | AGPL | REJECT |
| Dashboards | grafana/grafana | AGPL-3.0 | 2026-11-07, 77,735 | AGPL | REJECT |
| Page interactivity | bigskysoftware/htmx | 0BSD (file read; GitHub shows NOASSERTION) | 2026-11-06, 49,611 | No build chain; fits a server-rendered read-only page; on the preferred-licence list | REFERENCE, candidate for D5 page |
| Charts | chartjs/Chart.js | MIT | 2026-10-23, 67,778 | Only if a chart is approved | REFERENCE |
| Charts | apache/echarts | Apache-2.0 | 2026-10-13, 67,690 | Same | REFERENCE |
| Charts | plotly/plotly.js | MIT | 2026-11-06, 18,376 | Heavy bundle | REFERENCE |
| Auth | lepture/authlib | BSD-3-Clause | 2026-11-06, 5,449 | Only if a login requirement exists | REFERENCE |
| Crypto (transitive) | pyca/cryptography | Apache-2.0 OR BSD (file read) | 2026-11-06, 7,834 | Dual licence acceptable if pulled in by an auth library | note only |
| Metrics export | prometheus/client_python | Apache-2.0 | 2026-10-30, 4,384 | Only if operational metrics are wanted | REFERENCE |
| Tracing | open-telemetry/opentelemetry-python | Apache-2.0 | 2026-11-07, 2,702 | Same | REFERENCE |
| Statistics | scipy/scipy | BSD-3-Clause | 2026-11-07, 15,191 | Only if a sample-based method for D4 is approved; arithmetic needs no library | REFERENCE (conditional COMPOSE) |
| Dataframes | pandas-dev/pandas | BSD-3-Clause | 2026-11-06, 50,504 | Not needed at current sizes | REJECT |
| Scheduler | agronholm/apscheduler | MIT | 2026-10-26, 7,690 | Foundation already has a worker | REJECT (duplicate) |
| Task queue | celery/celery | BSD-style (LICENSE head read; GitHub shows NOASSERTION) | 2026-11-07, 29,134 | Needs a broker; far larger than the need | REJECT |
| Task queue | python-arq/arq | MIT | 2026-04-16, 3,022 | Needs Redis; no push since April | REJECT |
| Postgres job queue | procrastinate-org/procrastinate | MIT | 2026-11-02, 1,445 | Would still duplicate the foundation worker | REFERENCE, only if D6 needs ViralTrack-owned jobs |
| Postgres queue | pgmq/pgmq | PostgreSQL licence | 2026-10-20, 5,386 | Extension install, unneeded | REJECT |
| Postgres cron | citusdata/pg_cron | PostgreSQL licence | 2026-09-08, 3,918 | Extension install, unneeded | REJECT |
| Partitioning | pgpartman/pg_partman | PostgreSQL licence (file read) | 2026-11-05, 2,850 | Unneeded for small, 30-day tables | REFERENCE |
| Time-series DB | timescale/timescaledb | Apache-2.0 / Apache-compatible / Timescale License mix (file read) | 2026-11-07, 23,819 | Mixed licence, unneeded | REJECT |
| Migrations | sqlalchemy/alembic | MIT | 2026-10-30, 4,467 | Foundation owns the schema; revisit only if D6 adds ViralTrack tables | REFERENCE |
| Change detection | deepcharles/ruptures | BSD-2-Clause (earlier audit, not re-read) | 2026-10-06, 2,108 | Needs history first | REFERENCE (after D6) |
| Notifications | caronc/apprise | BSD-2-Clause | 2026-11-06, 17,716 | Foundation already has alerts and digest | REFERENCE, only if notifications are authorized |
| HTTP mocking | lundberg/respx | BSD-3-Clause | 2026-07-21, 845 | Repository already has `Recorder` mock transports | REJECT (duplicate) |
| Cassette recording | kevin1024/vcrpy | MIT | 2026-11-03, 3,023 | Risk of storing real response data and headers; D7 writes a sanitized report instead | REJECT for D7 |
| Observability | pydantic/logfire | MIT | 2026-11-07, 4,537 | Vendor-service oriented; foundation uses Sentry | REJECT |

Search misses: `APScheduler/apscheduler` and `tabulator-js/tabulator-ts` returned 404 because the slugs were wrong; the correct APScheduler repository `agronholm/apscheduler` is in the table. No table-component library was audited because no table UI is authorized.

## 3. Conclusions

1. No capability of phases 4 to 7 justifies a new infrastructure dependency today.
2. If D5 is authorized, FastAPI (with pydantic at the boundary) is the only framework choice that adds no second stack; `schemathesis` is the one dev-only dependency worth approving; htmx is an option for a read-only page.
3. D6 needs no scheduler, queue or time-series engine: the foundation has them.
4. D4 and D7 need no external library.
5. BUILD items, all small and unique ViralTrack policy logic: the explanation record, the response-schema leakage test, the guarded live harness. Each is below the "significant BUILD" threshold, so no separate approval is requested now, and each will carry its own reuse note when implemented.
