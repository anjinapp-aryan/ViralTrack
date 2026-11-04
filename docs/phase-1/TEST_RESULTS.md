# Test Results

## Phase 2 Batch 3: ingestion profile and retention verification (2026-11-04, working tree on top of `76f9335`)

| Suite | Passed | Failed | Skipped | Duration |
|---|---:|---:|---:|---:|
| ViralTrack, all, against pgserver PostgreSQL 16.2 with pgvector 0.6.2 (`VT_TEST_REQUIRE_PGVECTOR=1`) | **202** | **0** | 2 (live foundation not running) | 19.2 s |
| ViralTrack, plain `pytest` | 179 | 0 | 25 (Postgres and live) | 13.6 s |
| `tests/test_retention_batch3.py` with Postgres | 21 | 0 | 0 | 2.7 s |
| Lint (ruff 0.16.9) | clean | | | |
| Compose: base; base + ingestion profile; base + managed-db + ingestion profile | render | | | |
| Upstream submodule | unmodified at `d872014` | | | |

Mutation check: making the expiry clock `updated_at`-first fails
`test_expiry_uses_the_text_clock_and_a_stats_refresh_cannot_extend_it`; the change was reverted and the file is
identical to the implementation tested.

GitHub CI on `76f9335` (Batch 2 and the database work, committed together by the owner; run 41841522121):
**success**, 181 passed, 2 skipped. Batch 3: **`GITHUB_CI_NOT_YET_EXECUTED`**.

Evidence and findings: docs/phase-2/INGESTION_PROFILE.md.

## Database provider configuration (2026-11-04, working tree; not a Phase 2 batch)

| Suite | Passed | Failed | Skipped | Duration |
|---|---:|---:|---:|---:|
| ViralTrack, all, against pgserver PostgreSQL 16.2 with pgvector 0.6.2 (`VT_TEST_REQUIRE_PGVECTOR=1`) | **181** | **0** | 2 (live foundation not running) | 16.2 s |
| `tests/test_database.py` with Postgres | 65 | 0 | 0 | 13.8 s |
| `tests/test_database.py` without Postgres | 60 | 0 | 5 | 13.2 s |
| Lint (ruff 0.16.9) | clean | | | |
| `python -m viraltrack.database` (local) | exit 0: PostgreSQL 16.2, pgvector 0.6.2 in `public`, HNSW-capable, visible | | | |
| `docker compose config` (base; managed override with and without `DATABASE_URL`) | renders; the managed override refuses a missing `DATABASE_URL` | | | |

A defect found by testing: this Windows PostgreSQL build rejects `TimeZone = 'UTC'` (no time-zone database).
ViralTrack now sets a fixed `+00:00` offset instead.

**No managed provider (Neon, Supabase, Aiven) was connected.** Their profiles are tested as configuration
with placeholder URLs only. The stack was not started in Docker in this task, because the Docker daemon was
not running.

## Phase 2 Batch 2: ingestion interface (2026-11-04, working tree on top of `9825f2d`)

| Suite | Passed | Failed | Skipped | Duration |
|---|---:|---:|---:|---:|
| ViralTrack, all (pgserver Postgres 16.2 + live demo foundation on :3903, **no YouTube key**) | **118** | **0** | **0** | 3.1 s |
| ViralTrack, plain `pytest` | 108 | 0 | 10 (8 Postgres, 2 live) | 0.3 s |
| `tests/test_ingestion.py` alone (offline) | 46 | 0 | 1 (live) | |
| Lint (ruff 0.16.9) | clean | | | |
| Upstream submodule | unmodified at `d872014` | | | |

`tests/test_ingestion.py` covers the following:

- **Disabled by default.** Each of the 4 ingestion methods makes **zero requests** while disabled. The disabled
  check runs before argument validation.
- **Success paths.**
  - Collect creator, collect query and refresh: exact POST bodies, the `X-NF-Client` header, and counts and
    quota figures copied from the foundation.
  - Quota left as None when the foundation reports none.
  - `ingestion_status`.
- **Pre-flight**, with no POST made in each case:
  - no key (from `/api/health`);
  - the unit floor;
  - the search-call floor, counting the pages asked for;
  - quota not reported (3 shapes).

  A creator collection does not need search calls.
- **Upstream refusals.**
  - 428 maps to `ProviderCredentialsMissing`.
  - 429 `QuotaExceeded` maps to `QuotaExhausted`.
  - 429 `ManualRunLimit` with `Retry-After`: `RateLimited`, after which nothing is sent until the cooldown
    expires.
  - 401/403 map to `ProviderAuthFailed`.
  - 403 `PlanLimit` / `ReadOnlyView`, 404, 400 and 500 map to typed errors.
- **Input limits.** 9 invalid arguments rejected with no request.
- **Boundary.**
  - The client POSTs only to the 3 documented collection routes; others are refused, including path traversal.
  - Reads stay GET-only with ingestion enabled.
  - Base-class defaults raise `UnsupportedCapability`.
  - Settings are bounded and described.
- **Live (demo foundation, no key).**
  - `ingestion_status` reports `has_credentials=False`.
  - All three collection calls raise `ProviderCredentialsMissing`.
  - `/api/stats` is unchanged.
  - The foundation's access log shows **0** POST requests.

Real-data ingestion: **`REAL_DATA_VALIDATION_BLOCKED — YOUTUBE_API_KEY_NOT_CONFIGURED`**. No collection was
performed and no quota was spent.

GitHub CI: **`GITHUB_CI_NOT_YET_EXECUTED`** (not committed).

## Phase 2 Batch 1: GitHub CI

`9825f2d` (run 41832452818): **success**, 70 passed, 1 skipped (live).

## Phase 2 Batch 1: metric reconciliation (2026-11-04, working tree on top of `4b0bb9b`)

| Suite | Passed | Failed | Skipped | Duration |
|---|---:|---:|---:|---:|
| ViralTrack, all (pgserver Postgres 16.2 + live demo foundation on :3903) | **71** | **0** | **0** | 2.6 s |
| ViralTrack, plain `pytest` | 62 | 0 | 9 (8 Postgres, 1 live) | 0.2 s |
| Lint (ruff 0.16.9) | clean | | | |
| Upstream submodule | unmodified at `d872014` | | | |

New tests:

- `test_policy_inventory_is_exactly_4_10_2`
- `test_restricted_since_phase_2_cannot_be_sorted_by` ×2: acceleration and views_per_follower, discovery and
  search, with no request made
- `test_engagement_rate_omitted_when_likes_are_hidden`

Updated tests:

- `test_raw_and_allowed_derived_by_default`: 4 allowed.
- `RESTRICTED`: now includes acceleration and views_per_follower.
- `test_restricted_metrics_mapped_with_approval`: both are mapped only with the amendment flag.
- `test_adapter_never_filters_or_ranks_by_restricted_scores`: `/api/viral` always gets
  `min_views_per_subscriber=0`, and `/api/search` never gets it.

Live check against the demo foundation (origin `demo`, 0 quota):

- `/api/viral` without the parameter: the funnel includes `views per subscriber >= 1.0`.
- With `min_views_per_subscriber=0`: that step is gone.
- Through the adapter: 24 items, total 102. Derived metrics mapped: engagement_rate, views_gained_24h,
  views_per_hour_24h and views_per_hour_lifetime only.

GitHub CI: **`GITHUB_CI_NOT_YET_EXECUTED`** (not committed).

## Phase 1.2 (2026-11-03, working tree on top of `e035b11`)

| Suite | Passed | Failed | Skipped | Duration |
|---|---:|---:|---:|---:|
| ViralTrack, all (Postgres + live demo foundation) | **67** | **0** | **0** | 4.5 s |
| ViralTrack, plain `pytest` | 58 | 0 | 9 (8 Postgres, 1 live) | 0.2 s |
| Lint (ruff 0.16.9) | clean | | | |
| Retention fail-safe: wrong schema | exit 3, `retention error: no niche-finder tables in schema 'nope'` | | | |
| Upstream submodule | unmodified at `d872014` (0 changed files) | | | |

The upstream suite was not re-run in Phase 1.2: the submodule is unchanged since the Phase 1.1 run
(1,786 / 0 / 0). New tests: `test_adapter_never_filters_or_ranks_by_restricted_scores`,
`test_transcripts_after_approval_follow_their_video`; `test_phase_1_1_decisions` now expects every transcript to
be purged.

GitHub CI on the pushed Phase 1.1 commit `e035b11` (run 41675734597): **success**, 64 passed, 1 skipped (live),
upstream-suite skipped by design.

GitHub CI on the pushed Phase 1.2 commit `4a0802d` (run 41677704227): **success**, 66 passed, 1 skipped
(live), upstream-suite skipped by design.

## Phase 1.1 (2026-11-03, working tree on top of `355cd19`)

| Suite | Environment | Passed | Failed | Skipped | Duration |
|---|---|---:|---:|---:|---:|
| Upstream youtube-niche-finder @ d872014 (full) | Docker `python:3.12-slim` + `pgvector/pgvector:pg16` (CI-equivalent) | **1,786** | **0** | **0** | 136 s |
| ViralTrack, all tests (unit + provider/adapter + Postgres integration + retention + live foundation) | Windows, Python 3.12.10, pgserver Postgres 16.2, demo foundation on :3903 | **65** | **0** | **0** | 4.2 s |
| ViralTrack, no database or foundation (plain `pytest`) | same | 57 | 0 | 8 (7 Postgres, 1 live) | 0.2 s |
| Lint (`ruff check .`, ruff 0.16.9) | | clean | | | |
| Docker: `docker compose up -d --build postgres web retention` | Docker Desktop 29.5.3 | postgres and web healthy; retention ran every rule, including the new Phase 1.1 ones (`own_unverified.*`, `meta.*`); none skipped | | | |

### New Phase 1.1 tests

| Area | Tests |
|---|---|
| Derived-metric policy | `test_restricted_metrics_never_mapped_without_approval`, `test_restricted_metrics_mapped_with_approval`, `test_internal_only_metrics_never_mapped`, `test_every_mapped_derived_field_has_a_policy_rule`, `test_every_upstream_numeric_field_is_classified`, `test_default_sort_is_by_raw_views`, `test_sorting_by_a_restricted_metric_is_refused_before_any_call`, `test_allowed_derived_sort_and_unknown_sort`, `test_shorts_filter_is_allowed_but_label_is_restricted`, `test_metric_policy_decisions`, `test_restricted_rule_must_name_its_approval`, `test_content_rejects_unexposable_metrics` ×2, `test_creator_metrics_are_checked_too` |
| Demo / test / real | `test_demo_corpus_cannot_pass_as_real_provider_data`, `test_real_ids_accepted_as_real`, `test_demo_metric_cannot_sit_in_real_content`, `test_production_requires_real_data_origin` |
| Provenance | `test_every_record_answers_the_provenance_questions` |
| Security | `test_creator_id_is_encoded_in_the_path` |
| Retention decisions | `test_phase_1_1_decisions` (own_* unverified, drafts.review, derived meta, transcripts cascade) |
| Config | `test_amendment_flag_is_the_only_source_of_approvals` |

Defect found during Phase 1.1: none in production code beyond the path-encoding issue (fixed). One test seed
had a primary-key collision and was fixed.

## CI

| Commit | Run | Result |
|---|---|---|
| `355cd19` (your push) | GitHub Actions 41671578970 | **success**: job `viraltrack` (lockfile, install + `pip check`, lint, config, compose, pin, tests **43 passed, 1 skipped**). `upstream-suite` skipped by design (schedule/dispatch only) |
| Phase 1.1 working tree | — | **`GITHUB_CI_NOT_YET_EXECUTED`**: not committed or pushed. Its local equivalent is above |

## Phase 1 (earlier, for reference)

Upstream 1,786/1,786 (Docker, 146 s); Phase 0 on Windows/pgserver 1,784/1,786 (two environment-only failures);
ViralTrack 44/44.
