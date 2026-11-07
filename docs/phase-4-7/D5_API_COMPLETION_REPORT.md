# D5 API core: completion report

Date: 2026-11-07. Baseline `48aa81a` (main = origin/main), foundation submodule `d872014` (unchanged). Nothing committed or pushed.

## 1. Executive summary

ViralTrack now has a versioned, read-only HTTP API (`viraltrack.api`, FastAPI) over its existing provider layer. Seven GET endpoints serve health, readiness, capabilities, discovery, search and creators. Every response passes through the same validation and metric policy as Python callers, and then through an independent response guard that fails closed. The API spends no quota, writes nothing, exposes no foundation route, and labels synthetic data as DEMO. Verdict: **GO WITH LIMITATIONS** (section 12).

## 2. Architecture implemented

```text
client ─HTTP/JSON─► viraltrack.api (FastAPI)
                      ├─ request validation (pydantic/Query: enums, patterns, bounds)
                      ├─ PlatformProvider (YouTubeProvider: approved sorts, 1,000,000 follower bound,
                      │                    duration filter, period/region checks)  ─► foundation HTTP API ─► PostgreSQL
                      ├─ normalized model (Content refuses non-ALLOWED metrics, RAW/DERIVED separated)
                      ├─ serialize (only the v1 fields; null for unknown)
                      └─ GuardedJSONResponse (walks every body; restricted key or wording → 500, no data)
```

Reused: `PlatformProvider`, `YouTubeProvider`, `build_providers`, `mapping`, `MetricPolicy`/`RULES`, `Provenance`, `viraltrack.config`, `viraltrack.database.connect`, the test fixtures, mock-transport pattern, synthetic corpus and in-process foundation runner. Built (ViralTrack-specific): routes, schemas, serializer, response guard, API settings. Not built: no new ingestion, database access layer, scheduler, cache, auth system or mock API.

Provider change (additive only): `PlatformProvider.check_ready()` (default `None`) and `YouTubeProvider.check_ready()`, which calls the foundation's free, read-only `GET /api/health`. No existing method changed.

## 3. Endpoint inventory

| Endpoint | Purpose | Notes |
|---|---|---|
| `GET /api/v1/health` | liveness | checks nothing; no configuration in the body |
| `GET /api/v1/health/ready` | readiness | provider backends (required) and, if `DATABASE_URL` is set, `SELECT 1` (reported, not required); 503 when not ready; no error text |
| `GET /api/v1/capabilities` | platforms, filters, sorts, metrics | YouTube available; Instagram and TikTok `available: false` with the reason; ingestion capabilities not listed; refused sorts listed with reasons |
| `GET /api/v1/discover` | discovery | `query` (switches to text search), `period`, `niche`, `creator_size` (`any`/`up_to_10k`/`up_to_100k`/`up_to_1m`, always bounded), `duration` (`any`/`up_to_3_min`/`over_3_min`), `region`, `min_views`, `sort` (`views`, `published_at`), `platform`, `page`, `page_size` |
| `GET /api/v1/search` | text search | `query` required, `period`, `niche`, `duration`, `sort`, `platform`, `page`, `page_size` |
| `GET /api/v1/creators` | creators of discovered videos | distinct creators among the first 1000 discovered videos by views, with `videos_in_result`; stated in `meta.notes` |
| `GET /api/v1/creators/{creator_id}` | one collected creator | identity, followers and uploads (raw, null when hidden); `videos: null` with a note (no per-creator video list exists) |

Deviations from the requested parameter list, with reasons: there is no date-range parameter, because the provider supports only a relative `period`; `creator_size` is an enum of bounded follower limits, because "unlimited" is not allowed; `query` on `/discover` delegates to text search and refuses `creator_size`, `min_views` and `region`, which text search does not support.

## 4. Data policy enforcement

- Only `views` and `published_at` sorts exist (OpenAPI enum). Restricted, refused, wrong-case and empty sorts are 422 before any foundation request.
- Response fields are fixed: `metrics` = views, likes, comments; `derived` = engagement_rate, views_per_hour_lifetime (display only, not sortable). All models forbid extra fields.
- Hidden or unreported values are `null`, never 0. A hidden like count gives `likes: null` and `engagement_rate: null` even when the foundation sends an engagement rate. A reported 0 stays 0.
- Every metric carries provenance: kind, source, provider, origin, `collected_at` (null, because the foundation does not report it), `foundation_first_seen_at` and note.
- DEMO: `meta.demo`, `meta.data_origin`, and `origin` on every item and metric. Synthetic ids are refused when the deployment claims real data.
- Guard: walks every body, nested objects and lists included, error bodies too. It refuses keys naming restricted, internal-only or withheld metrics, or foundation score fields, and refuses explanatory text (`notes`, `note`) that names them. Titles and names are not scanned. Tested with a provider note saying "outlier" (500, no data) and with nested keys.
- Instagram and TikTok are refused with `platform_unavailable` and the reason; the API never pretends they are active.

## 5. OpenAPI contract

OpenAPI 3.1, 7 paths, 22 component schemas, at `/openapi.json` (Swagger UI at `/docs`). A committed snapshot is in `docs/api/openapi-v1.json`, and a test fails if the contract changes without regenerating it (`python -m viraltrack.api.openapi > docs/api/openapi-v1.json`). Envelopes are `{"data": [...], "meta": {...}}` for lists, `{"data": {...}}` for items and `{"error": {"code", "message", "details"}}` for errors. Nullable fields are explicit (`anyOf` with null). Every content endpoint documents 422, 502, 503 and 504 with `ErrorOut`, and the creator detail endpoint also documents 404.

## 6. Security review

- No secrets in responses or logs. A test sets a foundation token and checks every endpoint and the log. Provider errors (which can name internal hosts) are logged by type only; clients get a fixed message. Validation errors do not echo input.
- No SQL is built (the only query is the literal `SELECT 1`). No user-controlled URL: the foundation base URL comes from configuration, and paths are fixed or percent-encoded ids. Creator ids are limited to `[A-Za-z0-9_-]{1,64}`.
- No foundation route is reachable through the API (`/api/health` on the API is 404). Only GET is routed (POST is 405). No ingestion route exists.
- CORS is closed by default. Allowed origins are exact, `*` is refused, and production requires https. Credentials are not allowed.
- The access log has method, path, status, duration and request id; no query string. An unsafe `X-Request-ID` is replaced.
- **Authentication is not implemented.** The API is localhost-only for this milestone: `VT_API_HOST` accepts only `127.0.0.1`, `::1` or `localhost` and refuses any other address at startup. Before any shared or public deployment, an authentication boundary is needed (a reverse proxy with an identity provider, or an API key or token at the gateway). Owner decision.
- Rate limiting is not implemented. Each request costs one foundation read, and no quota.

## 7. Performance observations

Measured locally against the foundation on the demo corpus (6 channels, 204 videos), one request each, not a benchmark: health 26 ms, readiness 76 ms, capabilities 3 ms, discover 24 items 62 ms (53 KB), discover with the duration filter 61 ms, search 62 ms, creators 57 ms, creator detail 14 ms, OpenAPI 26 ms. Bounds: `page_size` at most 100, `page × page_size` at most 1000, one foundation request per call. The duration filter and `/creators` ask the foundation for up to 1000 rows. That is bounded, but it is the largest payload, so it should be measured on a real corpus. There is no N+1 pattern; the API does no database query beyond readiness.

## 8. Test results

| Run | Result |
|---|---|
| New D5 tests, offline (`tests/test_api_d5.py`) | 135 passed, 4 skipped (the PostgreSQL integration tests), 0 failed |
| Full suite, offline (no database variables) | 945 passed, 141 skipped, 0 failed (810 passed and 137 skipped before D5; the 4 new skips are the integration tests) |
| Full suite with PostgreSQL 16 + pgvector and the pinned foundation code (`VT_TEST_DATABASE_URL`, `VT_TEST_UPSTREAM_PYTHON`, `VT_TEST_REQUIRE_PGVECTOR=1`, `VT_TEST_REQUIRE_UPSTREAM=1`) | 1081 passed, 5 skipped, 0 failed. Skipped and not run: 3 POSIX-only tests (Windows) and 2 live-foundation smoke tests (`VT_TEST_FOUNDATION_URL` not set) |
| OpenAPI snapshot | regenerated document equals `docs/api/openapi-v1.json` |
| `pip check` | no broken requirements |
| D5 integration tests (real foundation code on PostgreSQL, zero network attempts asserted) | 4 passed |
| `ruff check .` | clean |
| Live run: `python -m viraltrack.api` against the local foundation with demo data | all endpoints 200; foundation quota afterwards: 0 units, 0 search calls |

The coverage areas: endpoints, validation (33 invalid requests, each with no foundation request), unavailable platforms (8), policy (leak checks on all 7 endpoints, exact field sets, null handling, provenance, demo/real labelling, guard unit and end-to-end tests), pagination (slices, has_more true/false/unknown, empty pages), failures (connect error 503, timeouts 504, malformed 502, partial data), OpenAPI (paths, errors, enums, nullable fields, no restricted property, snapshot), security (CORS, settings validation, log content, request id, token never shown).

Not covered by this run: the hosted CI run (nothing pushed); Linux execution of the API tests (they are platform-independent and will run in the `viraltrack` job, which installs the updated lockfile).

## 8a. Final corrections (closure review)

1. Paths and methods outside the API (unknown path, foundation paths such as `/api/health` or `/api/viral`, POST or DELETE) returned Starlette's bare `{"detail": ...}`, outside the error envelope and the guard. They now return the `{"error": ...}` envelope through the guarded response (`not_found`, `method_not_allowed`), and the `Allow` header is kept. 7 tests.
2. `VT_API_HOST` accepted any address. It is now limited to loopback addresses while the API has no authentication. 6 tests.

No other behavior changed, and the OpenAPI document is unchanged.

## 9. Regression

Existing ingestion, provider behavior, retention, domain model and D7 guard are unchanged. The full suite, including the PostgreSQL and foundation-backed tests, passes. The submodule is unchanged at `d872014`. The retention policy needs no change: the API persists nothing.

## 10. Git change summary

Modified: `pyproject.toml` (new optional extra `api` = fastapi, uvicorn; same two added to `dev`), `requirements-dev.lock` (regenerated with the CI command), `viraltrack/providers/base.py` and `viraltrack/providers/youtube/provider.py` (additive `check_ready`), `.env.example` (`VT_API_HOST`, `VT_API_PORT`, `VT_API_CORS_ORIGINS`), `README.md` (API section).
Added: `viraltrack/api/` (`__init__`, `__main__`, `app`, `schemas`, `serialize`, `guard`, `settings`, `openapi`), `tests/test_api_d5.py`, `docs/api/openapi-v1.json`, this report, `FRONTEND_PHASE_1_PLAN.md`.
Untouched and still uncommitted from earlier: `docs/ui-redesign/`.

Dependencies added (an optional extra, not core): fastapi (MIT) and uvicorn (BSD-3-Clause), the framework the foundation already uses. Transitive additions in the lockfile, licences read from installed metadata: starlette (BSD-3-Clause), pydantic and pydantic-core (MIT), annotated-types (MIT), annotated-doc (MIT), typing-inspection (MIT), click (BSD-3-Clause), h11 (MIT), colorama (BSD, Windows only), opentelemetry-api (Apache-2.0, pulled by the current fastapi). fastapi 0.162 was resolved; the foundation pins 0.158.1, and the constraint is `>=0.158.1`.

## 11. Known limitations

1. No authentication or rate limiting; local binding only (section 6).
2. Pagination is a window of at most 1000 items cut into pages (the foundation has no offset); pages can shift if data changes between requests; `has_more` is `null` when the window is full.
3. `collected_at` is null for every value: the foundation does not report read times. `foundation_first_seen_at` is a store time, not an observation time.
4. Creator listing is derived from discovered videos, not a creator index; creator detail has no video list.
5. No absolute date range, only relative periods.
6. Thumbnails are the platform's URLs (no download or storage); whether hot-linking is acceptable is a counsel question.
7. The Starlette test client prints a deprecation warning (it prefers `httpx2`); harmless, no action taken.
8. Not yet run in hosted CI.

## 12. Verdict

**GO WITH LIMITATIONS.** All critical acceptance criteria are met offline and on local PostgreSQL. The limitations that matter before any non-local deployment are authentication and hosted-CI confirmation.

| Criterion | Result |
|---|---|
| Baseline understood | yes: 810 passed, 137 skipped at `48aa81a` |
| Existing tests green | yes |
| Health and readiness | yes |
| Capabilities | yes |
| Discover, search, creators | yes |
| PostgreSQL integration | yes (real foundation code on PostgreSQL 16 + pgvector) |
| OpenAPI generated and validated | yes (tests and snapshot) |
| Restricted metrics cannot escape | yes (schema, model, guard; tested) |
| Missing values never fabricated | yes |
| Only approved sorting | yes |
| Instagram and TikTok unavailable | yes |
| DEMO provenance labelled | yes |
| Ingestion and retention unchanged | yes |
| Submodule unchanged | yes |
| No frontend migration | yes |
| No unapproved dependency | fastapi and uvicorn as an optional extra (D5-authorized, audited) |
| No user work lost | yes |

## 13. Addendum: search contract correction (after frontend phase 1)

Topic search (`/api/v1/search`, `/api/v1/discover?query=`) now reports `meta.sort: "relevance"`. It always carries a note that it ranks the collected videos by relevance to the text, does not exclude unrelated videos and is not a measure of popularity or performance. When no returned video has topic data (as in the demo corpus), it also says the order is not by relevance.

A `sort` with a query is refused (422 `sort_not_supported_with_query`), and `/search` no longer accepts `sort`. Browse sorts are unchanged. The similarity value stays INTERNAL_ONLY and is never returned.

Details: `FRONTEND_PHASE_1_REPORT.md` section 6. Tests: `tests/test_api_d5.py`, 148 passed offline. Full suite with PostgreSQL and the foundation: 1094 passed, 5 skipped.

