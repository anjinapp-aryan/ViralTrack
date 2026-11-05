# Phase 2 commit map

Date: 2026-11-05. Base of Phase 2: `4b0bb9b`. Head at the time of writing: `5ed12ec` (GitHub CI green).

The history was kept as the owner committed it. It was **not** rewritten, squashed or amended. The commit
messages are generic ("fixing issues"), so this map is the reference for which commit delivered what.

**Several commits mix logical changes.** They are marked below. Where a capability was built in one commit and
corrected in a later one, both are listed; the later commit is the final behaviour. Use the "capability index" in
section 2 to find everything that belongs to one capability.

## 1. Commits in order

| Commit | Date (local) | Message | Delivers | Mixed? |
|---|---|---|---|---|
| `9825f2d` | 2026-11-04 | improvement and bug fixes | **Batch 1, metric reconciliation.** Policy is 4 allowed / 10 restricted / 2 internal-only; `acceleration` and `views_per_follower` restricted and never mapped; discovery always sends `min_views_per_subscriber=0`; `engagement_rate` omitted when likes are hidden. Files: `metric_policy.py`, `mapping.py`, `provider.py`, provider tests, metric docs | No |
| `76f9335` | 2026-11-04 | phase 2 features | **Batch 2, on-demand ingestion interface** (typed ingestion errors, quota pre-flight, cooldown, POST allow-list, `IngestionResult`/`QuotaStatus`, `tests/test_ingestion.py`) **and database provider configuration** (`DATABASE_*` settings, profiles, `viraltrack/database.py`, managed-database compose override, pgvector CI image, `tests/test_database.py`, architecture and compatibility docs) | **Yes: two independent features in one commit (24 files).** Shared files: `config.py`, `.env.example`, `TEST_RESULTS.md`, the Phase 2 plan, `DATA_RETENTION_POLICY.md`, `docker-compose.yml` |
| `c612136` | 2026-11-04 | fixing it | **Batch 3, ingestion profile and retention verification.** `deploy/compose.ingestion-profile.yml` (`WORKER_THUMBS=0`, `WORKER_THUMB_EMBED=0`, `LLM_PROVIDER=none`), `VT_THUMBNAILS_APPROVED`, thumbnail purge step in the retention job, 21 retention tests, `INGESTION_PROFILE.md` | No |
| `0c3c8c6` | 2026-11-04 | fixing bugs | **Environment templates support.** `.gitignore` entry for `.env_*` and `tests/test_env_templates.py`. The templates themselves (`.env_local`, `.env_dev`, `.env_prod`) are gitignored and not in the repository | No |
| `52e28e6` | 2026-11-04 | fixing major blocker | **F1 and F2.** Retention container no longer receives the whole `.env` (and so not `YOUTUBE_API_KEY`); the ingestion profile is merged by default through a multi-path `include` in `docker-compose.yml`; `tests/test_compose_safety.py` renders the real Compose configuration | No (docs only alongside) |
| `3836c34` | 2026-11-05 | fixing a bugs or phase 3 | **Configurable retention interval** (`VT_RETENTION_INTERVAL_SECONDS`, default 3600; `--loop` scheduler in `viraltrack/retention/__main__.py`; `tests/test_retention_interval.py`) **plus the first version of the Batch 5 validation report** **plus** `.vscode/settings.json` (editor setting, unrelated to the product) | **Yes: retention scheduling, a Batch 5 report and an editor file** |
| `1cc2c22` | 2026-11-05 | fixing issues | **Batch 5 follow-up, first pass.** `VT_YOUTUBE_COLLECT_TIMEOUT_SECONDS` (default 120) for collection POSTs; a provenance timestamp then named `ingested_at`; `tests/test_batch5_followup.py`; `DISCOVERY_TEST_PLAN.md`; `evidence/batch5_evidence.json`; Batch 5 report update | **Yes: timeout, provenance field, evidence and plan together. The `ingested_at` name was wrong and is replaced in `5ed12ec`** |
| `5ed12ec` | 2026-11-05 | fixing issues | **Correction and completion of the above.** `ingested_at` renamed `foundation_first_seen_at` (the foundation's first-insert time, not ViralTrack's ingestion time); `ProviderTimeout` with `outcome_unknown`; single-attempt behaviour for collection POSTs tested; docs and tests updated | **Yes: a rename correction and a new error type** |

Not in the history: no commit pushes Instagram, TikTok, transcript, thumbnail-download, LLM or restricted-metric
features. The upstream submodule is at `d872014` in every commit.

## 2. Capability index

| Capability | Commits (first to last) | Final behaviour is defined by |
|---|---|---|
| Metric policy (4 / 10 / 2), restricted sort refusal | `9825f2d` | `9825f2d` |
| Ingestion interface and quota pre-flight | `76f9335` | `76f9335`, plus timeout changes in `1cc2c22`, `5ed12ec` |
| Database provider configuration | `76f9335` | `76f9335` |
| Thumbnail-off profile and thumbnail purge | `c612136`, `52e28e6` | `52e28e6` (profile is the default) |
| Retention container key isolation (F1) | `52e28e6` | `52e28e6` |
| Retention interval and scheduler | `3836c34` | `3836c34` |
| Collection POST timeout | `1cc2c22`, `5ed12ec` | `1cc2c22` (setting), `5ed12ec` (error semantics) |
| `ProviderTimeout`, no retry of collection POSTs | `5ed12ec` | `5ed12ec` |
| Provenance: `collected_at` unknown, `foundation_first_seen_at` | `1cc2c22` (as `ingested_at`), `5ed12ec` | `5ed12ec` |
| Batch 5 real-data validation report | `3836c34` (first), `1cc2c22`, `5ed12ec` | the file as of `5ed12ec` |
| Discovery test plan and aggregate evidence | `1cc2c22`, `5ed12ec` (one line) | `1cc2c22` |

## 3. Reading the history

- `ingested_at` appears in `1cc2c22` and is gone in `5ed12ec`. It was never part of a released interface.
- `3836c34` contains `.vscode/settings.json`, which sets `python.terminal.useEnvFile`. It is not product code.
- Batch 4 (internal read API) was deferred and has no commit.
- Continuous integration passed on `9825f2d`, `76f9335`, `c612136`, `0c3c8c6`, `52e28e6`, `3836c34` and `5ed12ec`. The
  latest run on `5ed12ec` is the reference. CI runs offline tests only (see the readiness assessment).

## 4. Repository state when this map was written

- Branch `main`, equal to `origin/main` at `5ed12ec`; working tree clean before this file and the readiness
  assessment were added.
- Upstream submodule `d872014`, unmodified.
- Last full local run: 285 passed, 0 failed, 2 skipped (live-foundation tests) with PostgreSQL 16.2 and pgvector; plain
  `pytest` 262 passed, 25 skipped; Ruff clean.
