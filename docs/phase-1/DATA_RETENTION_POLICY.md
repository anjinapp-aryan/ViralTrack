# Data Retention Policy (B-6)

**B-6 status: PARTIALLY RESOLVED.** Storage retention is now enforced and tested. Open items are listed at the
end, under "What is NOT resolved".

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
| drafts | USER | **REVIEW** | `review` holds a snapshot of corpus statistics |
| transcripts, transcript_chunks | USER (+ DERIVED embeddings) | **REVIEW** | Pasted by the user from YouTube's UI, not API data. Still YouTube content |

### The user's own channel (Authorized Data, OAuth)

| Table | Action | Note |
|---|---|---|
| own_channels, own_channel_daily, own_video_metrics | **REVIEW** | Authorized Data may be kept while the authorization is valid, but must be re-verified every 30 days. Upstream behaviour on token revocation is not yet audited |
| own_oauth_pending | KEEP | Expiring state |

### Not provider data (accounts, billing, operations)

users, email_tokens, audit_log (upstream `NF_AUDIT_RETENTION_DAYS`, default 180), sessions, login_attempts,
user_settings, user_prefs, api_tokens, event_reads, plans, user_plans, plan_changes, manual_runs, llm_usage,
llm_reservations, user_totp, user_backup_codes, mfa_challenges, nf_rls_key: **KEEP**. `meta` (quota counters,
schema version, short caches): **REVIEW**, because its keys are undocumented upstream.

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

1. **Derived metrics are a policy question, not a storage one.** Upstream computes and displays outlier
   scores, revenue estimates, niche scores and channel comparisons. Without Google's acceptance of the
   Analytics & Reporting amendment, the guide says not to create derived metrics beyond simple arithmetic. The
   retention job cannot fix this. **Action: file the API Compliance Audit with the amendment before production
   use.**
2. REVIEW tables: `meta`, `own_*`, `drafts`, `transcripts*`.
3. Identifiers: policy text on storing bare video/channel ids was not located. ViralTrack keeps ids only where
   the user keeps them (watchlist, saved items).
4. Deployments must run the `retention` service (or `python -m viraltrack.retention --apply` daily).
   Running the foundation's compose file alone re-creates the unsafe behaviour.
