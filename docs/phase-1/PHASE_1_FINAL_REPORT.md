# VIRALTRACK — PHASE 1 FINAL REPORT

Date: 2026-11-03. Nothing committed or pushed; waiting for approval.

## 1. Foundation adopted

`pandich93/youtube-niche-finder` at commit `d872014` (MIT), included **unmodified** as the git submodule
`upstream/youtube-niche-finder`.

## 2. Adoption strategy

**Compose (Option E) with an adapter.** It is not a fork (no upstream code changed), not vendored (no files
copied), not a library dependency (upstream is not a package) and not an extraction (that would be a rewrite).
The foundation runs as a service. ViralTrack reaches it through an adapter over its documented HTTP API, and
the retention job uses its database. This keeps upstream upgradable and the ViralTrack domain
platform-neutral. Details: FOUNDATION_ADOPTION_DECISION.md.

## 3. Reused functionality (unchanged, from the foundation)

- YouTube collection: `search.list`, `videos.list`, `videos.batchGetStats`, `channels.list`,
  `playlistItems.list`, quota guardrails, worker scheduling.
- Postgres + pgvector schema, migrations and stats snapshots.
- Outlier, velocity, acceleration and trend metrics, niches and keyword momentum.
- Dashboard (31 screens), saved items with folders, watchlist, alerts (dashboard, Telegram, e-mail), MCP server.
- Multi-user auth, sessions, API tokens, 2FA, Prometheus `/metrics`, structured access logs.
- docker-compose stack (postgres, web, worker, mcp) and CI patterns: ruff pin, lockfile check, pgvector service.

## 4. New ViralTrack code (≈1,220 lines + 540 lines of tests), each with a reason

| Code | Why it exists |
|---|---|
| `viraltrack/domain` (model, capabilities, errors) | The foundation's model is YouTube-specific. The product needs a platform-neutral model with provenance |
| `viraltrack/providers/base.py`, `registry.py` | Provider boundary, so Instagram/TikTok can be added and YouTube replaced |
| `viraltrack/providers/youtube` | Adapter from the foundation's HTTP API to the normalized model |
| `viraltrack/retention` | B-6: upstream deliberately deletes nothing, and YouTube policy requires deletion |
| `viraltrack/config.py`, `.env.example` | One validated, secret-masking configuration |
| `docker-compose.yml`, `Dockerfile` | Includes the upstream compose unchanged and adds the `retention` service |
| `.github/workflows/ci.yml`, `requirements-dev.lock` | CI for the boundary and a weekly run of the upstream suite |
| `THIRD_PARTY_NOTICES.md`, `README.md` | Attribution and entry point |

## 5. Architecture

Platform layer (providers) → normalized model → persistence (the foundation's Postgres) + retention job.
Intelligence is Phase 2+. See ARCHITECTURE.md.

## 6. Provider abstraction

`PlatformProvider` with declared `PlatformCapabilities`. Unsupported operations raise `UnsupportedCapability`
and make no network call. A future Instagram provider (official Graph API: known professional accounts and
limited hashtag search) implements the same class and registers in `registry.py`. TikTok waits for a
legitimate source. See PROVIDER_BOUNDARY.md.

## 7. Data model

`Content` / `Creator` / `Metric` / `Provenance`. Raw metrics (`source=youtube-data-api`) and derived
metrics (`source=niche-finder`) live in separate fields, and the model rejects mixing them. Collection time
is `None` when the foundation does not report it, never invented. See DATA_MODEL.md.

## 8. Data retention

**B-6: PARTIALLY RESOLVED.**

- Resolved: every upstream table is classified. A daily retention job enforces 30 days (or 36 months for
  statistics with an accepted amendment, with text still at 30 days). It deletes data for videos YouTube
  stopped returning and fails closed on a missing schema. It is tested on the real upstream DDL and runs in
  Docker.
- Not resolved: (a) the foundation still computes and displays derived metrics (outlier scores, revenue
  estimates, niche scores), which need Google's Analytics & Reporting amendment; (b) REVIEW tables `meta`,
  `own_*`, `drafts`, `transcripts*`; (c) identifier storage rule not located; (d) deployments must run the
  retention service. See DATA_RETENTION_POLICY.md.

## 9. License

- Upstream: MIT, notice kept (submodule `LICENSE` + `THIRD_PARTY_NOTICES.md`, verified byte-identical).
- Dependencies: permissive, plus LGPL psycopg2-binary and MPL certifi/tqdm, all unmodified. Model weights
  Apache-2.0 / MIT.
- Open items: `py_rust_stemmers` metadata, and **ViralTrack has no license of its own**.
- Files copied or adapted from upstream: none (only synthetic JSON fixtures recorded from its demo seed).
- Upstream modifications: none.

## 10. Local execution

- Docker: `docker compose build web retention` (47 s); `postgres` and `web` healthy, `/api/health` ok,
  `retention` applied.
- Without Docker: foundation on demo data. The adapter discovered, searched, and read creator and history.
  The retention report found 9 deletable rows.
- **No live YouTube data**: no API key on this machine, so `worker` and collection were not run.

## 11. Tests

Upstream (Linux Docker, pgvector, CI-equivalent):

```text
Passed: 1786
Failed: 0
Skipped: 0
(146 s)
```

ViralTrack (with Postgres + live foundation):

```text
Passed: 44
Failed: 0
Skipped: 0
```

Without a database: 37 passed, 7 skipped.

## 12. CI

Workflow written. **Not run on GitHub (nothing pushed).** Every step ran locally and passed.

## 13. UI reuse

The foundation's dashboard is REUSED as ViralTrack's UI. Branding and default language: ADAPT (later /
configuration). Player: BUILD later. Unified cross-platform dashboard: REFERENCE (social-dash,
content-dashboard). See UI_REUSE_DECISION.md.

## 14. Remaining blockers

| # | Blocker | Severity |
|---|---|---|
| 1 | No YouTube API key yet, so no real-data validation | HIGH |
| 2 | Google Analytics & Reporting amendment not filed; upstream shows derived metrics (B-6 remainder) | CRITICAL for production |
| 3 | REVIEW tables in the retention policy (`meta`, `own_*`, `drafts`, `transcripts*`) | MEDIUM |
| 4 | CI not yet run on GitHub | MEDIUM |
| 5 | ViralTrack has no license; `py_rust_stemmers` metadata | MEDIUM |
| 6 | Upstream defaults to Russian; must set `NF_DEFAULT_LOCALE=en` | LOW |
| 7 | Upstream exposes no per-item fetch time and no single-video endpoint | LOW |
| 8 | Instagram (official API only, limited), TikTok and trending audio unavailable (Phase 0 B-3, B-4, B-7, B-13) | CRITICAL for those features |
| 9 | One-author upstream (bus factor) | MEDIUM |

## 15. Phase 2 readiness

**READY WITH LIMITATIONS.** The boundary, model, provenance, retention and tests are in place, and the
foundation runs locally with its full suite green. Phase 2 cannot validate anything against real YouTube
data until a key exists. It should not ship derived metrics to users until the Google amendment is filed
and accepted.
