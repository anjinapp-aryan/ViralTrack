# Phase 2 Batch 5: controlled real-data validation

Date: 2026-11-04 (follow-up 2026-11-05). Verdict: **PASS_WITH_LIMITATIONS**. No retention deletion was run.

**Execution environment: the real-data run was performed natively on Windows 11, not in Docker.** The foundation
(`uvicorn api:app`) and PostgreSQL 16.2 ran as host processes. The Docker Compose stack, its rendered profile and the
`retention` container were **not** started during this run; they are covered only by the render-based tests.

## Follow-up (2026-11-05)

| Item | Result |
|---|---|
| `collected_at` | Stays `None` while the real capture time is unavailable. Unchanged, now tested |
| `foundation_first_seen_at` | New optional field on `Provenance`: UTC, from the foundation's `firstSeenAt`. **Verified upstream meaning:** `videos.first_seen_at` and `channels.first_seen_at` are set once, by the foundation's own `INSERT ... ON CONFLICT DO NOTHING` (value: the row's `updated_at`, else the foundation's clock), and its upserts never rewrite them. So it is the **foundation's** first-insert time: not ViralTrack's ingestion time and not a capture time. An earlier draft named it `ingested_at`; that name was wrong and was removed (never released, so no alias). ViralTrack's own receive time is the existing `Content.retrieved_at`; ViralTrack persists nothing, so no separate `ingested_at` is added. It is never copied into `collected_at` |
| Timeout errors | A client timeout raises `ProviderTimeout` (a subclass of `ProviderUnavailable`). A read or write timeout has `outcome_unknown=True`: the request may have reached the foundation, which can still finish it, and a collection may already have spent quota. A connect or pool timeout has `outcome_unknown=False` (nothing delivered). A confirmed foundation failure is an HTTP error (`ProviderError` with a status) and is never a timeout. No POST is retried automatically |
| Collection timeout | New `VT_YOUTUBE_COLLECT_TIMEOUT_SECONDS`, default 120 (1 to 900), used only for collection POSTs. Reads keep `VT_YOUTUBE_TIMEOUT_SECONDS` (20). A timed-out collection is never retried |
| Test database | `vt_b5` dropped after verification; see section 7 |
| Discovery | Test plan only: [DISCOVERY_TEST_PLAN.md](DISCOVERY_TEST_PLAN.md). No further YouTube request was made |

Non-sensitive evidence kept: [evidence/batch5_evidence.json](evidence/batch5_evidence.json) (aggregates only).

## 1. Environment

| Item | Value |
|---|---|
| Foundation | `upstream/youtube-niche-finder` at `d872014`, unmodified; `api:app` served by uvicorn on 127.0.0.1:3903 (Windows, native, not Docker) |
| Database | local PostgreSQL 16.2 with pgvector 0.6.2, a fresh database `vt_b5`, schema `public` |
| Services started | the foundation API only. **No worker, no MCP, no frontend**, so no scheduled step ran |
| Foundation environment | `WORKER_THUMBS=0`, `WORKER_THUMB_EMBED=0`, `LLM_PROVIDER=none` (the values of `deploy/compose.ingestion-profile.yml`), key from the root `.env` |
| ViralTrack | `VT_YOUTUBE_INGESTION_ENABLED=true` in the validation process only (not in `.env`), `VT_YOUTUBE_MAX_SEARCH_PAGES=1`, `VT_YOUTUBE_MAX_VIDEOS_PER_COLLECT=20`, data origin `real` |
| Key | `/api/health` reported `hasApiKey: true`. The key was never printed; it is absent from the foundation log, the database log and the validation output (searched) |

Because the API was run natively, the Compose rendering of the profile did not start the process; the same three values
were set by hand. The rendered Compose configuration is covered by `tests/test_compose_safety.py`.

## 2. What was collected

| Step | Request | Result |
|---|---|---|
| 1 | `collect_creator("@GoogleDevelopers", max_items=20)`, `POST /api/collect/channel` | channel **Google for Developers**, ID `UC_x5XG1OV2P6uZZ5FSM9Ttw`; 20 videos found and stored; foundation reported `units_from_shared_pool: 3`, `search_calls: 0` |
| 2 | `collect_query("home espresso", pages=1)`, `POST /api/collect/niche` | 50 videos stored under niche `home-espresso`; 1 `search.list` call |

- **Channel choice.** The owner asked for a small channel. A channel's size cannot be known without spending quota, so a
  stable, public, active developer-relations channel was chosen and the cost was bounded by the 20-video cap. It is
  probably **not small**. Only this one channel was collected. The other 18 channels in the database (19 in total) are
  authors of the keyword-search results, stored as part of that search; they were not collected separately.
- **Totals.** Two collection requests, 70 videos, 19 channels, 70 statistics snapshots.
- **The client lost the result of step 2** (the 20-second read timeout applied then; collection requests now default to 120 seconds). The first keyword search made the foundation download its text embedding
  model from Hugging Face (50 videos were embedded; this is not a thumbnail), so the answer took longer than
  ViralTrack's 20-second timeout and ViralTrack raised `ProviderUnavailable` (now `ProviderTimeout`, which says the outcome is unknown). The foundation finished the work. The
  request was **not retried**, so nothing was spent twice. The outcome of step 2 is known from the foundation's quota
  meter and the database, not from an `IngestionResult`.

## 3. Quota

Meter: the foundation's `/api/health` (`unitQuota`, `searchQuota`), read before and after each step.

| After | `unitsToday` | `unitsLeft` | `searchCallsToday` | `searchCallsLeft` |
|---|---|---|---|---|
| Start | 0 | 10000 | 0 | 100 |
| Step 1 (channel) | 3 | 9997 | 0 | 100 |
| Step 2 (keyword) | **6** | **9994** | **1** | **99** |
| Verification reads | 6 (verification spent 0) | 9994 | 1 | 99 |

- **Total: 6 units and 1 search call, against a budget of 50 units.** The budget was held by a guard in the validation
  script (abort if `unitsToday` exceeded 50, checked after each step), by running the keyword search only after the
  channel step had been measured, by the request caps above, and by ViralTrack's pre-flight floors.
- The meter agreed with the figure in the foundation's step-1 response (3 units).
- **Accounting was checked against Google's documentation** before the keyword search, because a `search.list` call is
  often reported to cost 100 units. Google's quota page (read 2026-11-04 through a fetch subagent) says `search.list`
  costs 1 per call in its own bucket of 100 calls a day since 2026-06-01, and `channels.list`, `videos.list` and
  `playlistItems.list` cost 1 each. The foundation's counts match.
- **Limit of this check:** the counters are the foundation's own, kept in its database. Google's console quota dashboard
  was not consulted, so the figure at Google was not independently confirmed.

## 4. Provenance and timestamps

Checked through ViralTrack's provider (`search_content`, read-only) and directly in the database.

- 30 items returned by the search path: origin `real_provider_data`, provider `youtube`; provenance sources
  `youtube-data-api` (raw) and `niche-finder` (derived); adapter `youtube/niche-finder-http`.
- All timestamps are timezone-aware. `published_at` in the database ranges from 2016-01-22 to 2026-10-29; none is in the future.
- Foundation rows: `first_seen_at` and `updated_at` are ISO-8601 with `+00:00`, 2026-11-04T17:38:33Z to 17:38:40Z;
  `texts_refreshed_at` is empty for all 70 videos (only the freshness job sets it).
- **Follow-up:** each metric's provenance now also carries `foundation_first_seen_at`, the foundation's `firstSeenAt` in UTC, so a
  consumer can see when the foundation first stored the item. It says nothing about when a count was read from YouTube
  and is not ViralTrack's ingestion time.
- **Limitation: `Provenance.collected_at` was `None` for all 150 metric values.** The foundation's read API
  (`/api/search`, `/api/viral`) returns `firstSeenAt` but no statistics-capture time, and ViralTrack records an unknown time
  as `None` rather than guessing (project rule). The retention clock is unaffected because it reads the database, but a
  consumer cannot see when a view count was read. Possible follow-up for owner decision: use the foundation's snapshot data
  or `firstSeenAt` as a documented bound. Nothing was changed.

## 5. Restricted metrics

- The foundation's raw payload carries the restricted fields (`acceleration`, `viewsPerSubscriber`, `outlierScore*`,
  `outlierBand`, `viralScore`, `projected30dViews`, `estimatedRpm`, `semanticScore`, `baselineMedianViews`).
- ViralTrack's `Content` exposed only raw `views`, `likes`, `comments` and derived `engagement_rate` and
  `views_per_hour_lifetime`. **No restricted or internal-only metric appeared** (30 items, searched by name).
- Sorting by `outlier_score` raised `RestrictedMetric`.
- Discovery requests always send `min_views_per_subscriber=0`. `discover_content(period=30d)` returned **0 items**: the
  foundation's default filters (channels of at most 10,000 subscribers, videos of at least 10,000 views) removed all
  three videos in that window. That is upstream default behaviour, not a defect, but it means discovery was not
  exercised beyond an empty result.
- Acceleration and views-per-follower were not used, collected or sorted by.

## 6. Thumbnails, transcripts, LLM

| Check | Result |
|---|---|
| Foundation `WORKER_THUMBS` / `WORKER_THUMB_EMBED` | `0` / `0`; the worker was never started |
| `thumbnail_archive` rows | **0** |
| Videos with `thumb_embedding` or `thumb_embedded_at` | **0** |
| `videos.thumbnail` | only `https://i.ytimg.com/vi...` URL strings |
| `transcripts`, `transcript_chunks`, `transcript_requests` | **0** each |
| LLM | provider `none`, as `/api/health` reports |
| Text embeddings (`videos.embedding`) | 50 videos. Computed locally from video text by the foundation's embedding model, whose weights were downloaded from Hugging Face on first use. Not an image and not a YouTube request. **Flag for the owner:** text-derived vectors are stored; retention removes them with their video row (30 days) |

Network traffic was not traced, so "no thumbnail download" rests on the disabled flags, the unstarted worker, the zero rows
and vectors, and a static test that the download code is reachable only from two guarded steps. The manual
`POST /api/thumbnails/embed` route was not called.

## 7. Retention, report-only

- `python -m viraltrack.retention` without `--apply` on the validation database: exit 0, `applied: false`, **0 rows** would
  be affected (everything is younger than the 30-day cutoff, 2026-10-05).
- To show that the data ages out, the same job was run in report mode with the clock set 31 days ahead. It **would**
  remove 260 rows (70 videos, 19 channels, 70 video and 19 channel statistics snapshots, 50 niche links, 32 category
  rows). The transaction was rolled back.
- A checksum of all 52 tables, taken from a separate connection before, after the CLI run and after the projected run,
  was identical each time. **Nothing was deleted.** `--apply` was never run.
- **Test database removed (2026-11-05).** Before dropping, `vt_b5` was confirmed to be the validation database (70 videos,
  19 channels, niche `home-espresso`, `first_seen_at` 2026-11-04, no open connection). It was dropped with
  `DROP DATABASE vt_b5`; the local server now lists only `postgres`. The validation logs and a scratch output that
  contained video titles were deleted too. Only the aggregates in `evidence/batch5_evidence.json` and this report remain.
  No retention apply was run on any database.

## 8. Tests

With local PostgreSQL 16.2 + pgvector (`VT_TEST_REQUIRE_PGVECTOR=1`):

- Full suite: **242 passed, 0 failed, 2 skipped** (the two live-foundation tests; `VT_TEST_FOUNDATION_URL` not set).
- `ruff check .`: all checks passed.
- Part A (retention interval) added `tests/test_retention_interval.py` (16 tests) and one compose test.
- The live-foundation smoke test asserts a key-less foundation and skips when a key is present, so it was not run.

## 9. Failures and limitations

1. Client timeout on the first keyword search (embedding-model download); result recovered from the meter. Addressed
   by the 120-second collection timeout, which was **not** re-tested against the live foundation (no further quota was
   spent); unit tests cover the setting and the single-attempt behaviour.
2. `collected_at` unknown for every metric (section 4); `foundation_first_seen_at` is added beside it, not in its place, and was
   verified against fixtures only, not the live foundation.
3. The channel is probably not small (section 2).
4. Quota figures come from the foundation, not the Google console (section 3).
5. Run natively on Windows, not in Docker; the Compose-rendered profile and the retention container did not run.
6. The text-embedding model is downloaded from Hugging Face on first use (an outbound dependency outside YouTube).
7. Discovery on this sample returned nothing under the default filters.
8. One channel and one keyword only: a smoke validation, not a load or accuracy test. Shorts classification was not examined.
9. Open from earlier reviews and unchanged: provider backup retention, transcript legal review, Google Analytics &
   Reporting amendment, licence decision.

## 10. Verdict

**PASS_WITH_LIMITATIONS.** Real data was collected within budget (6 of 50 units, 1 search call), carried real-data
provenance and valid timestamps in the foundation, exposed no restricted metrics, stored no thumbnails or transcripts, and
retention report mode changed nothing. The limitations above remain, chiefly the unknown `collected_at` and the
client-timeout behaviour.
