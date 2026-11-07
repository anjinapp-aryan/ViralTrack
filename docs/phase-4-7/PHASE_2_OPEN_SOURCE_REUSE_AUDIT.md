# Phase 2 (creator intelligence): open-source reuse audit

Date: 2026-11-07. Order of search, as required: this repository, current dependencies, the pinned foundation, then GitHub and package registries. Licence facts were read from the actual licence files with `gh api repos/<repo>/license` (this session, and earlier today for the projects marked "see earlier"). Not reviewed: test coverage, transitive dependency trees and security advisories of candidates that are not adopted (stated limit). This supplements, and does not replace, [OPEN_SOURCE_REUSE_AUDIT.md](OPEN_SOURCE_REUSE_AUDIT.md), [../ui-redesign/OPEN_SOURCE_REUSE_AUDIT.md](../ui-redesign/OPEN_SOURCE_REUSE_AUDIT.md) and [FRONTEND_PHASE_1_READINESS.md](FRONTEND_PHASE_1_READINESS.md).

## 1. Search for a ready-made creator tracker

`gh search repos` for "youtube channel growth tracker", "youtube channel statistics history" and "youtube subscriber tracker dashboard" returned only three small repositories (0 to 3 stars; no licence declared on any of them) and nothing for the second and third queries. None is usable code. Earlier audits (Phase 0 and `OPEN_SOURCE_REUSE_AUDIT.md`) reached the same conclusion: the adopted foundation, `pandich93/youtube-niche-finder`, is the one maintained, permissively licensed (MIT) project that already collects, snapshots, tracks channels and raises alerts. **No replacement exists; nothing in this phase should be built that the foundation already does.**

## 2. Decision table

| Capability | Candidate | Licence (file read) | Status of the evidence | Decision | Reason |
|---|---|---|---|---|---|
| Collection, quota ledger, refresh, worker | foundation (MIT, pinned `d872014`) | MIT | read | **REUSE** in place | already works |
| Creator profile, history series | foundation `/api/channels/{id}`, `/history` | MIT | read, live demo | **REUSE** through HTTP, **ADAPT** at the mapping boundary | allowed raw fields only; restricted groups dropped |
| Creator's video list | foundation `/api/channels/{id}/velocity` | MIT | read, live demo | **ADAPT** | only per-creator list; four raw fields mapped, the rest discarded |
| Watchlist storage and refresh | foundation `tracked_channels`, `/api/channels/tracked`, `/api/refresh` | MIT | read | **REUSE** | no ViralTrack table (a second store would duplicate and diverge) |
| Alert scan, digest, delivery | foundation `events`, scan, digest, Telegram/webhook | MIT | read | **REUSE** later, behind an allow-list | internal-only today; kinds depend on restricted values |
| Provider interface, models, policy, provenance, retention | this repository | project licence | read | **REUSE** | `get_creator`, `get_creator_history`, `Creator`, `CreatorSnapshot` already exist |
| API and OpenAPI | FastAPI, pydantic (D5) | MIT | read | **REUSE** | same stack as D5 |
| Frontend shell, tables, dialogs | shadcn-admin, shadcn/ui, Radix, TanStack | MIT | read (earlier today) | **REUSE** | adopted in frontend phase 1 |
| Time-series chart (creator history) | recharts/recharts | MIT, "(c) 2015-present recharts" | read | **REUSE** (re-add; it was removed in phase 1) | chosen in the UI audit; shadcn chart wrapper builds on it |
| Very large time series | leeoniya/uPlot | MIT | read | REFERENCE | 30 days of points do not need it |
| Change-point detection on history | deepcharles/ruptures | BSD-2-Clause, "(c) 2017-2021 ENS Paris-Saclay, CNRS" | read | REFERENCE (not now) | needs far more history than the 30-day retention allows, and a "breakout" label is a D4 policy question |
| Multi-channel notifications | caronc/apprise | BSD-2-Clause | read | REFERENCE | the foundation already sends Telegram and webhook messages |
| Postgres job queue, schedulers, time-series DB | procrastinate, APScheduler, TimescaleDB | MIT, MIT, mixed (see earlier) | earlier audit | **REJECT** | the foundation worker exists; no new infrastructure |
| Authentication boundary (shared deployment) | oauth2-proxy (MIT) with Authelia or Keycloak (Apache-2.0) | see [FRONTEND_PHASE_1_READINESS.md](FRONTEND_PHASE_1_READINESS.md) | earlier today | DEFER | needed before watchlist writes or any shared use |

## 3. What is genuinely built (ViralTrack-specific, small)

1. A mapping function for the per-creator video list: four raw fields, an explicit drop of everything else, tests that restricted keys never survive. No library knows this policy.
2. A `CreatorProfile` extension of the existing `Creator` model (country, creation date, total views) if the owner approves showing them.
3. The creator pages of the UI, composed from existing shadcn components.
4. If approved later: an alert allow-list (an enumerated set of event kinds and payload fields).

Nothing here is a significant BUILD in the sense of the reuse policy; each item carries its own note when implemented.

## 4. Dependencies that would be added

Phase 2A (creators, no history): none. Phase 2B (history chart): `recharts` (MIT; about 11 direct dependencies; lazy-loaded on the creator page only), installed through the shadcn chart component. The licence scan and `pnpm audit` of the installed tree are part of that step, as in frontend phase 1.
