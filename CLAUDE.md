# CLAUDE.md — ViralTrack

Read [AGENTS.md](AGENTS.md) first. It holds the general rules; this file adds project context for Claude.

## Mission

ViralTrack is a cross-platform viral-content discovery and trend-intelligence platform.

**DISCOVER → FILTER → WATCH → ANALYZE → TRACK → IDENTIFY OPPORTUNITIES**

Target platforms: YouTube, YouTube Shorts, Instagram Reels, TikTok, and future platforms, wherever
legitimate data access exists. Current reality (Phase 0): only YouTube has a legitimate discovery source.
Instagram is limited to the official Graph API: known professional accounts, plus 30 hashtags per 7 days.
TikTok discovery and trending audio have no legitimate commercial source yet.

## Repository map

| Path | What it is | May Claude edit it? |
|---|---|---|
| `upstream/youtube-niche-finder/` | Adopted YouTube foundation, git submodule pinned to `d872014`, MIT | **No.** Never edit. Adapt at the boundary. Its own `AGENTS.md`/`CLAUDE.md` apply only to upstream development |
| `viraltrack/domain/` | Platform-neutral model: `Content`, `Creator`, `Metric`, `Provenance` (RAW/DERIVED), capabilities, errors | Yes |
| `viraltrack/providers/` | `PlatformProvider` interface, registry, `youtube/` adapter over the foundation's HTTP API | Yes |
| `viraltrack/retention/` | Retention policy and job for the foundation's Postgres (blocker B-6) | Yes, with care: it deletes data |
| `viraltrack/config.py` | Validated `VT_*` environment configuration | Yes |
| `tests/` | pytest; `fixtures/niche_finder/` holds recorded synthetic upstream responses | Yes |
| `docs/phase-0/`, `docs/phase-1/` | Research, decisions, audits | Update; don't rewrite history |
| `docker-compose.yml` | Includes the upstream compose unchanged and adds `retention` | Yes |

## Foundation

Phase 0 selected `pandich93/youtube-niche-finder`. Phase 1 adopted it by **composition** (see
`docs/phase-1/FOUNDATION_ADOPTION_DECISION.md`). It already provides collection, quota guardrails, snapshots,
outlier/velocity/trend metrics, dashboard, saved items, watchlist, alerts, auth and MCP. Don't rebuild any of
these. If something must change, change it at the ViralTrack boundary and document the reason. Upgrade it by
moving the submodule pin.

## Reuse first

Every meaningful feature goes **REUSE → ADAPT → COMPOSE → BUILD**. Before coding, check in this order:

1. This repository.
2. Dependencies.
3. The foundation's HTTP API (`upstream/youtube-niche-finder/docs/http-api.md`).
4. GitHub and open source, where relevant.

For each candidate, inspect the source, license, maintenance, tests and whether it actually works. Use the
`reuse-audit` skill. Never rewrite stable functionality for style.

## Licenses

Preferred: MIT, Apache-2.0, BSD-2/3-Clause, ISC, 0BSD. Flag GPL, AGPL, LGPL, MPL, BUSL, proprietary, custom
and unclear licenses for explicit review. psycopg2-binary (LGPL) and certifi (MPL) are already reviewed and
accepted as unmodified libraries. Never copy unlicensed code. Repository license and dependency licenses are
separate concerns. Use the `license-audit` skill.

## Platform data

Software license ≠ platform data-access legitimacy. Never introduce:

- CAPTCHA, authentication or rate-limit bypass
- private API abuse or undocumented endpoints
- cookie harvesting
- ban evasion
- scraping that circumvents restrictions

TikTok-Api, instaloader, Douyin_TikTok_Download_API and jev-social were rejected for this reason. Don't
reintroduce them.

## Platform abstraction

```text
ViralTrack domain → PlatformProvider interface → platform adapter → foundation / external API
```

`viraltrack/domain` must never import or name YouTube specifics. New platforms are new providers (see the
`provider-development` skill and `docs/phase-1/PROVIDER_BOUNDARY.md`).

## No fake capabilities

If a platform does not legitimately provide something, the provider declares it unsupported, and calls raise
`UnsupportedCapability`. Never fabricate trending data, velocity, history, engagement, creator statistics or
audio trends. An unknown value is `None`, not a guess (for example `Provenance.collected_at`).

## Provenance

Raw provider data goes in `Content.metrics` (e.g. views, likes, comments, publishedAt). Derived data goes in
`Content.derived` (e.g. viewsPerHour, growthRate, acceleration, breakoutScore). The model rejects mixing
them. Every external metric carries `Provenance`: provider, source, collected_at, kind.

## Data retention

Whenever provider data is persisted, answer these and record the answers in
`docs/phase-1/DATA_RETENTION_POLICY.md` and `viraltrack/retention/policy.py`:

- What is stored, and why?
- How long?
- Can it be recomputed?
- Is it raw or derived?
- Must it be deleted?

YouTube default: 30 days. Statistics may be kept 36 months only after Google accepts the Analytics & Reporting
amendment, and text still follows the 30-day rule. Never inherit upstream persistence blindly: upstream
deletes nothing. Use the `data-retention` skill. Make no legal conclusions; flag questions for humans.

## Testing

Test framework: pytest. Commands:

- `pytest` runs unit tests; Postgres and live tests skip.
- `VT_TEST_DATABASE_URL=… pytest` adds the retention tests on the real upstream DDL.
- `VT_TEST_FOUNDATION_URL=… pytest -m live_foundation` runs the live smoke test.
- Lint: `ruff check .`
- Run the upstream suite in Linux Docker with `pgvector/pgvector:pg16`, not on Windows (see
  `docs/phase-1/TEST_RESULTS.md`).

Use the `testing` skill. No meaningless tests.

## Working style

- **Small changes.** No unrelated refactors or files. No broad rewrites unless asked.
- **Preserve upstream.** Keep license and attribution (`THIRD_PARTY_NOTICES.md`), document modifications,
  isolate ViralTrack changes, keep the foundation upgradable.
- **Workflow for significant tasks:**
  EXPLORE → REUSE AUDIT → PLAN → IMPLEMENT → TEST → REVIEW → DOCUMENT → HUMAN APPROVAL.
  Don't start coding if a reusable implementation might exist. Details:
  `docs/ai-development/AGENT_WORKFLOW.md`.

## Human approval

Claude may inspect, research, plan, implement, test, refactor within the task's scope, and document.

Claude must not, without explicit approval:

- change the architecture or the adoption strategy
- introduce questionable data sources or bypass platform restrictions
- change the licensing strategy
- remove important tests
- silently add large dependencies
- commit, push or merge

Work proceeds phase by phase. Stop at the end of each phase and wait.

## Skills

`.claude/skills/`: `reuse-audit`, `architecture-review`, `provider-development`, `testing`, `license-audit`,
`data-retention`, `code-review` (the project review checklist; invoked as the project skill).
