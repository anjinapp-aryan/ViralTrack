# Test Results (2026-11-03)

## Upstream suite: youtube-niche-finder @ d872014

| Run | Environment | Total | Passed | Failed | Skipped | Time |
|---|---|---:|---:|---:|---:|---:|
| **Phase 1 (authoritative)** | Docker, `python:3.12-slim` (Linux) + `pgvector/pgvector:pg16`, `NICHE_REQUIRE_PGVECTOR=1`, same as upstream CI | **1,786** | **1,786** | **0** | **0** | **146 s** |
| Phase 0 (for comparison) | Windows, pgserver (Postgres 16.2, pgvector 0.6.2) | 1,786 | 1,784 | 2 | 0 | 12,908 s |

The two Phase 0 failures (`test_pgvector` crowded-channel index, `test_rls_login` wrong password) do not
occur in the CI-equivalent Linux environment, which confirms they came from the Windows/pgserver setup.
Command: `pytest -q -p no:cacheprovider tests/` in `backend/` (3 warnings: MCP deprecation notices and an
unknown pytest option passed by the runner).

## ViralTrack suite

| Run | Passed | Failed | Skipped | Time |
|---|---:|---:|---:|---:|
| With Postgres + live foundation (`VT_TEST_DATABASE_URL`, `VT_TEST_FOUNDATION_URL`) | **44** | **0** | **0** | 3.9 s |
| Without either (plain `pytest`) | 37 | 0 | 7 (6 Postgres, 1 live) | 0.2 s |
| Live smoke vs Docker foundation (empty corpus, :8090) | 1 | 0 | — | 2.3 s |
| Live smoke vs demo-data foundation (:3903) | 1 | 0 | — | 2.3 s |

Lint: `ruff check .` (ruff 0.16.9, the foundation's pin): all checks passed.

### Coverage of the required integration-boundary areas

| # | Area | Tests |
|---|---|---|
| 1 | Provider initialization | `test_registry_builds_youtube_only`, `test_token_sent_only_when_configured` |
| 2 | Normalized content mapping | `test_discovery_maps_to_normalized_content`, `test_shorts_query_maps_short_form`, `test_search_and_creator`, `test_model_is_platform_neutral` |
| 3 | Provider error handling | `test_unreachable_foundation`, `test_not_found_creator`, `test_bad_responses` ×4, `test_invalid_period_rejected_before_any_call` |
| 4 | Unsupported capability | `test_unsupported_raises_and_makes_no_call` ×2, `test_audio_and_hashtags_declared_unsupported` |
| 5 | Configuration | `tests/test_config.py` (10 cases: defaults, `.env.example`, caps, invalid values, secret masking) |
| 6 | Data provenance | `test_raw_and_derived_provenance`, `test_history_points_carry_their_capture_time`, `test_raw_and_derived_kept_apart`, `test_derived_metric_cannot_pose_as_raw`, `test_raw_metric_cannot_pose_as_derived` |
| 7 | Retention behaviour | `tests/test_retention_job.py` (6, on real upstream DDL), `tests/test_retention_policy.py` (3, schema contract) |
| 8 | Persistence boundaries | `test_provider_only_reads`, `test_user_data_survives`, `test_report_mode_changes_nothing` |

### Defects the tests found during Phase 1 (fixed)

1. The retention "strip text" shortcut skipped `saved_items.payload` whenever the text and stats windows were
   equal, so payloads were never stripped. Fixed with an explicit `covered_by_stats` flag.
2. The Docker `retention` service ran before the foundation created its schema and reported "nothing to
   delete". Fixed in two places: the service waits for a healthy `web`, and the job now fails closed when the
   schema is missing.
3. Foundation hints came back in Russian (`NF_DEFAULT_LOCALE=ru`). The adapter now sends `X-NF-Locale: en`.

## CI

`.github/workflows/ci.yml`, two jobs.

- `viraltrack` (on every push and PR): lockfile check, install + `pip check`, ruff, config check of
  `.env.example`, `docker compose config`, submodule-pin check, pytest with a Postgres 16 service.
- `upstream-suite` (weekly and on demand): the foundation's full suite on `pgvector/pgvector:pg16`.

**Status: not run on GitHub.** Nothing was pushed, as Phase 1 instructions require. Every `viraltrack` job
step was run locally and passed: `LOCK_OK`, `pip check` compatible, ruff clean, `CONFIG_OK`, `COMPOSE_OK`,
`PIN_OK`, 44/44 tests. The YAML parses. The `upstream-suite` job mirrors the Docker run above.
