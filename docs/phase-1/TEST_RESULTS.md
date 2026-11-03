# Test Results

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
