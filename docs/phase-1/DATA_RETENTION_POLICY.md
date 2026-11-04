# Data Retention Policy (B-6)

**B-6 status: PARTIALLY RESOLVED** (Phase 1.1). Storage retention is enforced and tested for every table,
and the four groups that were left open in Phase 1 now have decisions (next section). Two things remain
open: Google's approval for derived metrics, which is a policy question handled in DERIVED_METRIC_POLICY.md,
and one legal question about transcripts.

## Phase 1.1 decisions on the four open groups

| Group | Tables | Purpose and data | Raw/derived | Why ViralTrack needs it | Recomputable | Retention / deletion requirement | Compliance risk | **Decision** |
|---|---|---|---|---|---|---|---|---|
| 1. Foundation metadata | `meta` | Quota counters (`yt_units_<day>`, `search_calls_<day>`, per-user), worker status (`worker_last_*`, `worker_step_*`), budget blocks, digest send marks, `schema_version`; **`maturity_curve` and `maturity_curve_check`**: a curve fitted from view snapshots (JSON with `calibratedAt` / `checkedAt`) | Operational keys: neither raw nor derived. Curve: DERIVED aggregate | Quota guardrails and scheduling; the curve feeds age-adjusted scores, which are RESTRICTED | Curve: yes, refitted by the worker. Counters: n/a | Derived data stored past 30 days without approval is not allowed. Upstream keeps the last passing curve forever | Operational: none. Curve: MEDIUM | **KEEP WITH RETENTION**: operational keys kept; the curve and its check are deleted 30 days after their own timestamp |
| 2. The user's own channel (Authorized Data, OAuth) | `own_channels`, `own_channel_daily`, `own_video_metrics` (`own_oauth_pending` is upstream-managed) | Encrypted refresh token, YouTube Analytics views, watch time, revenue, CPM | RAW (authorized) | The "your channel next to the niche" feature | Yes, by re-sync while authorized | Authorized Data may be kept while the authorization is valid. Policy: delete data of users whose tokens cannot be refreshed. Upstream only records `last_error` and keeps everything | HIGH if kept after revocation | **KEEP WITH RETENTION**: kept while the daily sync succeeds; deleted (token, daily and video metrics) once no sync has succeeded for 30 days (`last_synced_at`, or `connected_at` when it never synced) |
| 3. Drafts | `drafts` | The user's draft title, description and tags; `review` = a JSON snapshot of corpus signals at save time | USER + DERIVED snapshot | Metadata review and outcome tracking | `review`: yes (re-run the review) | User text has no platform limit. The snapshot carries corpus statistics | LOW | **KEEP WITH RETENTION**: draft kept; `review` stripped after 30 days |
| 4. Transcripts | `transcripts`, `transcript_chunks` | Transcript text the user pasted from YouTube's UI, plus chunk embeddings | USER (+ DERIVED embeddings). Not API data | Hook scores and transcript search | Re-paste only | YouTube API policy does not govern pasted text. The creator's copyright and YouTube's ToS on copying may apply | Legal question | **REVIEW REQUIRED** (legal). **Phase 1.2: storage disabled.** While `VT_TRANSCRIPTS_APPROVED=false`, every run deletes all `transcripts`, `transcript_chunks` and `transcript_requests`. After approval, they are deleted with their video |

All four are implemented in `viraltrack/retention` and covered by `test_phase_1_1_decisions`, which runs on the
real upstream DDL.

## The rule being enforced

YouTube API Services Developer Policies III.E.4 (read 2026-11-03):

- "An API Client must not store statistics retrieved as Non-Authorized Data for more than 30 days."
- Other Non-Authorized data: "not longer than 30 calendar days … the API Client must either delete or refresh
  the stored data."
- "API Clients must use reasonable efforts to ensure that their stored API Data is consistent with the current
  data … verify, every 30 days, that the video has not been deleted."
- With an accepted "Analytics & Reporting" amendment (derived-metrics policy, from 2026-06-01): statistics
  "for up to 36 calendar months". Titles, creator names, descriptions and comment text stay on the 30-day rule.

## What upstream does (unsafe as-is)

`backend/application/freshness.py`: "Nothing is deleted, here or anywhere else … Keeping data longer than 30
days without refreshing it, or keeping history, is the installation owner's own risk." Upstream does
re-read videos and channels older than 25 days (`REFRESH_STALE_DAYS`), but only within a daily cap and only
when quota remains. It keeps every history snapshot, every confirmed-gone item, thumbnail images and alert
payloads forever.

## The fix, at the ViralTrack boundary

`viraltrack/retention` (upstream is not modified):

| Window | Default | With accepted amendment (`VT_YOUTUBE_ANALYTICS_AMENDMENT_ACCEPTED=true`) | Config |
|---|---|---|---|
| Statistics (views, likes, comments, subscribers, ranks) | 30 days | up to 1095 days | `VT_RETENTION_YOUTUBE_STATS_DAYS` (rejected above the cap) |
| Text and media (titles, descriptions, names, thumbnails, LLM output) | 30 days | 30 days | `VT_RETENTION_YOUTUBE_TEXT_DAYS` (max 30) |

The job runs daily as the compose `retention` service (`--apply`). Without `--apply` it reports in a
rolled-back transaction, so a report shows exactly what an apply would delete. It **fails closed**: if the
foundation's tables are missing (wrong schema, foundation not started), it exits with an error instead of
reporting "nothing to delete". Timestamps that are not ISO-shaped are left alone and counted as `unknownAge`.

Upstream's 25-day refresh and this 30-day purge work together. Anything the worker keeps current survives;
anything it failed to refresh is deleted.

## Classification of every stored table

Source of truth: `viraltrack/retention/policy.py`. A test fails when the pinned upstream schema has a table
that is not classified there.

Actions: **PURGE** = deleted or stripped by age · **CASCADE** = deleted with its video or channel · **KEEP** =
not provider data · **REVIEW** = kept, open question.

### YouTube API data

| Table | Fields of note | Class | Why stored | Retention | Recomputable | Risk |
|---|---|---|---|---|---|---|
| videos | title, description, tags, thumbnail URL, counts, embeddings, labels | RAW + DERIVED + IDENTIFIER | the corpus | Row deleted when texts not refreshed in 30 d, or counts not refreshed within the stats window | re-collect costs quota | High → **PURGE** |
| channels | title, description, country, counts, llm_labels | RAW + DERIVED + IDENTIFIER | creator profiles | Row deleted when not refreshed in 30 d | re-collect | High → **PURGE** |
| video_stats_history | view/like/comment counts **plus title and thumbnail copies** | RAW | velocity and history | Rows: stats window. With the amendment, title and thumbnail are stripped after 30 d and the counts kept | no (history) | High → **PURGE** |
| channel_stats_history | subscriber/video/view counts | RAW | growth | stats window | no | High → **PURGE** |
| chart_snapshots / chart_entries | mostPopular ranks and views | RAW | chart history | stats window | no | **PURGE** |
| video_changes | old and new titles/thumbnails | RAW | repackaging feed | 30 d | no | **PURGE** |
| thumbnail_archive | **image bytes** of thumbnails | RAW | thumbnail-swap detection | 30 d | no | High → **PURGE** |
| video_categories | category names | RAW | filters | 30 d (upstream re-reads) | yes | **PURGE** |
| gone_items | ids YouTube stopped returning | IDENTIFIER + TEMPORARY | deletion detection | Confirmed items: **all their stored data deleted**. Marker: 30 d | — | **PURGE** |
| video_niches | video ↔ niche link | IDENTIFIER + USER | niche membership | with the video | yes | **CASCADE** |

### Derived from API data

| Table | Class | Retention | Note |
|---|---|---|---|
| video_insights (LLM analyses) | DERIVED + CACHE | 30 d | Built from titles and comments. Recomputable at LLM cost |
| video_sponsors (`evidence` quotes the description) | DERIVED + RAW | 30 d | Quotes provider text |
| sponsor_scan | TEMPORARY | with the video | |
| niche_clusters (outlier aggregates) | DERIVED | 30 d | Recomputed by upstream |
| video_tags (manual and LLM tags) | DERIVED + USER | with the video | Manual tags are lost with the video. Accepted |
| llm_cache | CACHE + DERIVED | 30 d | |
| events (alerts; payload holds titles and counts) | DERIVED | 30 d | Alert history older than 30 d is dropped |
| alert_deliveries | TEMPORARY | 30 d | |

### User content

| Table | Class | Action | Note |
|---|---|---|---|
| saved_items | USER + RAW | **PURGE payload only** | The saved item (id, folder, note) is kept. The metrics snapshot `payload` is removed after 30 d |
| tracked_channels, niches, user_topics, cost_profiles, transcript_requests | USER (+ IDENTIFIER) | KEEP | The user's own choices |
| drafts | USER | **PURGE `review` only** | Draft kept; `review` snapshot removed after 30 d (Phase 1.1) |
| transcripts, transcript_chunks, transcript_requests | USER (+ DERIVED embeddings) | **PURGE ALL until approved** | Pasted by the user from YouTube's UI, not API data. All deleted every run while `VT_TRANSCRIPTS_APPROVED=false` (Phase 1.2); then deleted with their video |

### The user's own channel (Authorized Data, OAuth)

| Table | Action | Note |
|---|---|---|
| own_channels, own_channel_daily, own_video_metrics | **PURGE when unverified** | Kept while the daily sync succeeds; deleted with the token once no sync has succeeded for 30 days (Phase 1.1). Upstream keeps them after token failures |
| own_oauth_pending | KEEP | Expiring state |

### Not provider data (accounts, billing, operations)

users, email_tokens, audit_log (upstream `NF_AUDIT_RETENTION_DAYS`, default 180), sessions, login_attempts,
user_settings, user_prefs, api_tokens, event_reads, plans, user_plans, plan_changes, manual_runs, llm_usage,
llm_reservations, user_totp, user_backup_codes, mfa_challenges, nf_rls_key: **KEEP**. `meta` (quota counters,
schema version) are kept; the derived `maturity_curve` / `maturity_curve_check` expire after 30 days (Phase 1.1).

Caches outside Postgres: none found. Models live on the `models` volume, and those are model weights, not
API data.

## Verified behaviour

- Unit and Postgres tests (`tests/test_retention_job.py`, real upstream DDL): report mode changes nothing;
  the 30-day default deletes stale and gone videos and channels with their dependents; user items survive with
  their payload stripped; the amendment keeps counts 36 months but strips titles after 30 d; a bad schema name
  is rejected; a missing schema fails closed.
- Report run on the foundation's demo data: 9 rows would be deleted (one confirmed-gone channel and its
  history, plus 5 channel snapshots older than 30 days).
- Docker: the `retention` service runs after `web` is healthy and applies the policy (0 rows on an empty
  corpus).

## What is NOT resolved

1. **Derived metrics are a policy question, not a storage one.** The foundation still computes and shows
   restricted metrics on its own dashboard, API and MCP server. ViralTrack's provider layer now blocks them
   (DERIVED_METRIC_POLICY.md), and the foundation's UI is limited to internal use. **Action: file the API
   Compliance Audit with the amendment before production use.**
2. Transcripts: legal review (above). Storage is disabled meanwhile, but upstream still accepts manual
   pastes until the next run (OWNER_DECISIONS.md, D).
3. Identifiers: policy text on storing bare video/channel ids was not located. ViralTrack keeps ids only where
   the user keeps them (watchlist, saved items, draft links).
4. Deployments must run the `retention` service (or `python -m viraltrack.retention --apply` daily).
   Running the foundation's compose file alone re-creates the unsafe behaviour; use the root docker-compose.yml.
5. **Thumbnails** (Phase 2 Batch 3, owner decision 2026-11-04): the foundation's `thumbnail_archive` and the image
   vectors computed from downloaded thumbnails are deleted on every run until `VT_THUMBNAILS_APPROVED=true`; the
   worker steps that download them are off (`WORKER_THUMBS=0`, `WORKER_THUMB_EMBED=0`, applied by default through the `include` in docker-compose.yml, from
   deploy/compose.ingestion-profile.yml). Expiry clocks and evidence: docs/phase-2/INGESTION_PROFILE.md.
6. **Managed-database backups** (2026-11-04, docs/deployment/DATABASE_PROVIDER_COMPATIBILITY.md):
   - Provider backups and point-in-time restore keep deleted rows beyond 30 days. Counsel should confirm
     whether that is acceptable. Until then, keep the backup or history window at or below 30 days where the
     plan allows it, and record the chosen setting here.
   - A restore can bring deleted rows back, so run the retention job immediately after any restore.
