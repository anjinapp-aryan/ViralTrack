# Phase 1.2 Release Gate

Date: 2026-11-03. Phase 1.2 committed and pushed by the owner as `4a0802d`; GitHub CI green.

## Verdict: `READY_FOR_PHASE_2_WITH_LIMITATIONS`

## What has been verified

| Item | Evidence |
|---|---|
| Foundation unmodified | Submodule clean at `d872014`. The CI pin check passes |
| Upstream suite | 1,786 / 0 / 0 (Linux Docker, Phase 1.1; submodule unchanged since) |
| ViralTrack suite | 67 / 0 / 0 locally (Postgres + live demo foundation). GitHub CI on `e035b11`: 64 passed, 1 skipped; on `4a0802d` (Phase 1.2): 66 passed, 1 skipped |
| Metric inventory | 16 rules reconciled: 6 ALLOWED, 8 RESTRICTED, 2 INTERNAL_ONLY (METRIC_INVENTORY_AND_APPROVAL.md) |
| Restricted metrics cannot leave ViralTrack | Fields: allow-list mapping + policy + `Content` invariant. Sorting refused. Filters: only allow-listed params are ever sent. Search uses the same path. ViralTrack has no export, API or MCP. Logs are masked |
| Capabilities | Registry builds YouTube only. `get_trending_content`, `get_content` raise `UnsupportedCapability` with no network call. `HASHTAGS` and `AUDIO` are declared unsupported. Instagram and TikTok have no provider, so nothing claims Reels, TikTok, trending feeds or audio |
| Demo vs real | `DataOrigin` everywhere; production requires `real`; demo ids are rejected as real (verified against the live demo foundation) |
| Retention | Every upstream table classified (contract test); daily Docker service; fail-closed with exit 3 on a missing schema; failed runs retried after 10 min and visible in `docker compose logs retention`; 30-day boundary enforced; 36-month statistics only with `VT_YOUTUBE_ANALYTICS_AMENDMENT_ACCEPTED=true` (config refuses more than 30 days otherwise) |
| Transcripts | Storage disabled: all deleted every run until `VT_TRANSCRIPTS_APPROVED=true` |
| Secrets | None in history or tree. Settings output masked (tested) |

## What remains unresolved

| # | Item | Owner of decision |
|---|---|---|
| 1 | `REAL_DATA_VALIDATION_BLOCKED — YOUTUBE_API_KEY_NOT_CONFIGURED` | Owner: provide a key |
| 2 | Google API Compliance Audit with the Analytics & Reporting amendment is not filed. 8 metrics stay RESTRICTED | Owner |
| 3 | The foundation's dashboard, API, export, MCP, extension and alerts show restricted metrics. Internal-only | Owner (decision E) |
| 4 | License: the repository is public with no license | Owner (decision A) |
| 5 | acceleration and views_per_follower confirmation; Shorts label policy | Owner / counsel (B, C) |
| 6 | Transcripts legal review; upstream still accepts manual pastes until the next run | Counsel (D) |
| 7 | `collected_at` unknown for list items (upstream does not expose it) | Upstream contribution |

## Security and licensing

- No secrets. Ids in URL paths are percent-encoded. SQL is parameterized. The retention container is
  non-root with no ports.
- The foundation has no sign-in unless `NF_MULTI_USER=1` and is bound to localhost; it must not be exposed.
- Dependencies: nothing blocked. Notices are required on distribution for MIT, LGPL psycopg2, MPL certifi/tqdm,
  Apache-2.0 model weights and the Debian base image. `py_rust_stemmers` is MIT.
- ViralTrack's own license is undecided.

## Platform coverage

| Platform | Status |
|---|---|
| YouTube (long-form, plus a duration filter for ≤ 3 min) | Implemented through the foundation. Only the demo corpus has been tested |
| YouTube Shorts as a label | RESTRICTED |
| Instagram Reels, Instagram trending | Unsupported (no provider; no legitimate global source) |
| TikTok discovery and trending | Unsupported (no legitimate commercial source) |
| Trending audio (all platforms) | Unsupported |
| Hashtag discovery | Unsupported (YouTube adapter; IG Graph hashtag search is a future provider) |
| Single-video lookup | Unsupported (no upstream endpoint) |

## Production readiness

**Not production-ready**, independent of Phase 2:

- there is no real-data validation;
- the amendment has not been filed;
- the license is undecided;
- the foundation surfaces need hardening (E) before any public deployment.

## Exact conditions for beginning Phase 2

Phase 2 may begin **only for safe raw-data development**, once the owner approves Phase 2:

**Allowed in Phase 2 now:**

- work on the ViralTrack provider layer, the normalized model and RAW metrics;
- the 6 ALLOWED derived metrics, labelled as not YouTube metrics;
- ordering by raw views, publication date or allowed metrics;
- duration filters;
- a ViralTrack UI/API that consumes only `Content`;
- player embeds (official IFrame or oEmbed);
- tests and fixtures with the `test` / `demo` origin.

**Not allowed until the stated approval exists:**

| Feature | Requires |
|---|---|
| Outlier, viral, projection, RPM scores; Shorts label; rankings or leaderboards by them | Google amendment accepted (+ counsel for RPM) |
| Showing the foundation dashboard, export, MCP or alerts to users | Amendment + decision E |
| Claims about real-data quality, quotas or production numbers | YouTube API key + REAL_DATA_VALIDATION.md completed |
| Storing or using transcripts | Counsel review + `VT_TRANSCRIPTS_APPROVED=true` |
| Instagram or TikTok features | A legitimate source (Meta App Review for the official Graph API; no TikTok source exists) |
| Public distribution of code or images | License decision (A) |
