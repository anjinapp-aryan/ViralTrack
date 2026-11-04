# Ingestion profile and retention verification (Phase 2 Batch 3)

Date: 2026-11-04. Status: implemented and verified locally; **not committed**. No YouTube API key is configured and
no real YouTube data was collected. Every test row below is synthetic.

## 1. Profile

Apply it as a compose layer; the upstream compose file stays unchanged:

```text
docker compose -f docker-compose.yml -f deploy/compose.ingestion-profile.yml up -d web worker retention
# managed database: add -f deploy/compose.managed-db.yml
```

| Setting | Value | Effect |
|---|---|---|
| `WORKER_THUMBS` | `0` | The worker never downloads thumbnails from `i.ytimg.com` and never writes `thumbnail_archive` |
| `WORKER_THUMB_EMBED` | `0` | The worker never downloads thumbnails to compute image vectors (upstream default is already 0) |
| `LLM_PROVIDER` | `none` | No LLM enrichment of API data |
| `VT_THUMBNAILS_APPROVED` | `false` (default) | Backstop: every retention run deletes `thumbnail_archive` and image vectors (see section 3) |
| `VT_TRANSCRIPTS_APPROVED` | `false` (default) | Every retention run deletes all transcripts |
| `VT_YOUTUBE_INGESTION_ENABLED` | `false` (default) | ViralTrack's on-demand collection is off (Batch 2) |

The override sets these on `web`, `worker`, `mcp` and `mcp-http`. Keys under `environment` beat the foundation's
`env_file`, so a stale upstream `.env` cannot turn them back on. What raw discovery still stores for a thumbnail
is the URL string that `videos.list` returns (`videos.thumbnail`), not an image.

Recommended worker settings for one 10,000-unit project: upstream defaults, `WORKER_REGIONS` limited to the
target markets, `WORKER_QUERIES` of at most about 20 terms (one `search.list` call each per day, from a bucket of
100), and the thumbnail and LLM settings above. These are estimates from upstream's documented costs, to be
re-checked during real-data validation.

## 2. Which tables collection writes, and what expires them

Verified against the pinned upstream source (`d872014`) by `tests/test_retention_batch3.py`. The test reads
`collecting.py`, `freshness.py`, `packaging.py`, `thumbnail_search.py` and `repositories.py`, extracts every
`INSERT INTO`, `UPDATE` and `DELETE FROM` target that is a schema table, and requires each to be classified in
`viraltrack/retention/policy.py`. It also requires that every table in the upstream DDL is classified.

| Table written by collection | Rule | Expiry clock |
|---|---|---|
| `videos` | PURGE | Deleted when `COALESCE(texts_refreshed_at, first_seen_at, updated_at)` is older than 30 days, or `updated_at` is older than the statistics window |
| `channels` | PURGE | Same text clock |
| `video_stats_history`, `channel_stats_history` | PURGE | `captured_at`, statistics window (30 days without the amendment) |
| `video_changes` | PURGE | `changed_at`, text window |
| `gone_items` | PURGE | `last_missing_at`; items confirmed gone delete their video or channel data |
| `chart_snapshots`, `chart_entries` | PURGE | Snapshot `captured_at`, statistics window |
| `video_niches`, `niches`, `tracked_channels` | CASCADE or KEEP | With their video, or user-owned |
| `thumbnail_archive` | PURGE | **All rows every run** until `VT_THUMBNAILS_APPROVED=true`; after approval, `captured_at`, text window |
| `transcripts`, `transcript_chunks`, `transcript_requests` | PURGE | **All rows every run** until `VT_TRANSCRIPTS_APPROVED=true` |

### The timestamp

- Text and identifiers expire 30 days after `texts_refreshed_at`, else after `first_seen_at`. Both are written only
  by their own path:
  - `first_seen_at` is set once, on insert.
  - `texts_refreshed_at` is set only by the foundation's freshness job, which re-reads rows older than
    25 days (`REFRESH_STALE_DAYS`).
- Collection's upserts never touch either column. Tests: `test_collection_upserts_cannot_touch_the_retention_clocks`,
  `test_only_the_freshness_job_sets_texts_refreshed_at`, `test_no_update_statement_rewrites_first_seen_at`.

### Can a scheduled refresh extend retention?

- **A statistics refresh cannot.** `refresh_stats` sets `updated_at=now` and the counters but not
  `texts_refreshed_at`. The test runs upstream's exact `UPDATE` statement on a video whose text is 31 days old: the
  retention run still deletes it. A video that was never text-refreshed expires 30 days after first sight.
- **A genuine re-read legitimately restarts the clock.** The freshness job re-fetches the text through
  `videos.list` and stamps `texts_refreshed_at`; the row then lives 30 more days from that re-read. That is the
  refresh-or-delete rule in YouTube's policy, not an extension. Test: `test_only_a_real_text_refresh_restarts_the_clock`
  (kept at +0 days, deleted at +31).
- The rule errs towards deleting early, never late. A keyword or channel collection that re-fetches a row does not
  count as a text refresh for retention until the freshness job stamps it.
- Mutation check: making the clock `updated_at`-first makes
  `test_expiry_uses_the_text_clock_and_a_stats_refresh_cannot_extend_it` fail.

## 3. Thumbnails

- Download paths (`fetch_thumbnail`): only `application/packaging.py` (worker step) and
  `application/thumbnail_search.py` (worker step, `POST /api/thumbnails/embed`, MCP `embed_thumbnails`). Test:
  `test_thumbnail_downloads_are_reachable_only_from_two_guarded_steps`. The worker calls them only under
  `WORKER_THUMBS` / `WORKER_THUMB_EMBED`, and the profile sets both to 0.
- **Known limitation:** the manual API route and MCP tool can still download thumbnails when an operator calls
  them. Both belong to the internal-only foundation surfaces (decision E). Retention removes what they leave:
  `thumbnail_archive` rows, and `videos.thumb_embedding`, `thumb_embedding_v`, `thumb_embedded_at` (vectors derived
  from a downloaded image) on every run. Tests: `test_thumbnail_archive_and_image_vectors_are_purged_until_approved`
  and `test_after_approval_thumbnails_follow_the_text_window`.
- The thumbnail **URL** the API returns is kept like any other API text, on the 30-day window.

## 4. Transcripts

`test_transcripts_are_deleted_every_run_whatever_their_age`: a transcript created today is deleted by the next run
and the report counts it. Nothing collects transcripts; upstream accepts manual pastes, which survive at most until
the next daily run.

## 5. Failures are visible

| Failure | What happens | Test |
|---|---|---|
| Wrong schema name | Exit 3, `retention error: no niche-finder tables in schema …` on stderr, nothing deleted | `test_cli_failure_is_a_nonzero_exit_with_a_message_on_stderr` |
| Database unreachable | Exit 4, masked URL, after 3 attempts | `test_retention_cli_unreachable_database_exits_4` |
| Missing or invalid configuration | Exit 2 | `test_retention_cli_missing_url_exits_2` |
| Error part-way through a run | The whole transaction rolls back; nothing is half-deleted; the exception propagates (non-zero exit) | `test_a_failing_run_deletes_nothing_and_raises` |
| In the deployed service | A failed run is retried after 10 minutes, a successful one runs again after 24 hours, the container restarts unless stopped, and it starts only when `web` is healthy. Output is in `docker compose logs retention` | `test_the_deployed_retention_service_retries_failures_and_depends_on_web` |

Report mode (the default without `--apply`) rolls back and deletes nothing (`test_report_mode_deletes_nothing_even_for_expired_rows`).

**Limit:** there is no alerting. A failure is visible in the exit code and logs, but nobody is notified. Monitoring
the container's logs or exit status is a deployment task.

## 6. Connection pooling and deployment configuration

- The retention job uses exactly one connection, set up through the shared `DATABASE_*` settings (`viraltrack/database.py`).
  It uses only transaction-scoped settings, so it works through direct, session-pooled and transaction-pooled URLs.
- The foundation's pools (up to 20 connections per process) are upstream code. See
  [../deployment/DATABASE_PROVIDER_COMPATIBILITY.md](../deployment/DATABASE_PROVIDER_COMPATIBILITY.md) for the budget
  against each provider's limits.
- Rendered and checked: base compose; base plus ingestion profile; base plus managed-database override plus ingestion
  profile (`WORKER_THUMBS: "0"` and `PGSSLMODE: require` present). The compose checks do not start containers, and no
  container was started in this task (the Docker daemon was not running).
- The compatibility check `python -m viraltrack.database` reported exit 0 on the local PostgreSQL 16.2 with pgvector 0.6.2.

## 7. Provider backups (limitation, not a legal conclusion)

Managed providers keep backups and point-in-time history for their own windows. Deleted rows stay recoverable until
those windows pass. **Counsel has not reviewed or approved this**; nothing in this repository claims that provider
backups satisfy YouTube's 30-day rules.

Until a decision exists:

1. Choose the shortest backup or history window the plan allows, ideally 30 days or less, and record the setting in
   DATA_RETENTION_POLICY.md.
2. After any restore, run `python -m viraltrack.retention --apply` before serving data.
3. Treat the backup question as an open compliance blocker.

Neither the actual backup windows nor the restore behaviour of Neon, Supabase or Aiven was verified.

## 8. What was not done

- No real YouTube data was collected and no quota was spent. `REAL_DATA_VALIDATION_BLOCKED — YOUTUBE_API_KEY_NOT_CONFIGURED`.
- No container was started, and no managed database was contacted.
- No restricted metric, Shorts label, transcript or thumbnail processing was enabled.
