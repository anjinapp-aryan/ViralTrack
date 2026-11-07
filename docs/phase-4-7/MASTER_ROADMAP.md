# Phases 4 to 7: master roadmap (Stage A baseline and audit)

Date: 2026-11-07. Scope: read-only audit and plan. No production code, test, schema, dependency, Compose or submodule change was made, no live API call was made, nothing was committed.

Companion documents: [OPEN_SOURCE_REUSE_AUDIT.md](OPEN_SOURCE_REUSE_AUDIT.md), [OWNER_DECISIONS.md](OWNER_DECISIONS.md), [LEGAL_POLICY_DEPENDENCIES.md](LEGAL_POLICY_DEPENDENCIES.md), [PHASE_DEPENDENCY_MATRIX.md](PHASE_DEPENDENCY_MATRIX.md). Earlier authoritative sources: [../phase-3/PHASE_3_FINAL_COMPLETION_REPORT.md](../phase-3/PHASE_3_FINAL_COMPLETION_REPORT.md) and [../phase-3/DISCOVERY_EXECUTION_ROADMAP.md](../phase-3/DISCOVERY_EXECUTION_ROADMAP.md).

Naming: the owner's prompt calls these Phases 4 to 7; the repository's Phase 3 roadmap calls the same work stages D4 to D7 (D4 explanations and confidence, D5 API and dashboard, D6 history and watchlists, D7 controlled live validation).

## 1. Verified baseline (checked on 2026-11-07)

| Item | Result | How verified |
|---|---|---|
| HEAD | `907c601` "fixing a bugs" | `git log` |
| Branch and remote | `main` equals `origin/main` after `git fetch` | `git status -sb` |
| Working tree | clean (before this audit added `docs/phase-4-7/`) | `git status` |
| Submodule | `upstream/youtube-niche-finder` at `d872014` (`v0.5.0-37-gd872014`), unmodified | `git submodule status` |
| Hosted CI | run `42241332404` for `907c601`: completed, success. `b51498d` run `42194024904`: success. `a540288` run `42190662882`: failure (the stub-permission defect, already fixed) | `gh run list` |
| Tests | 781 passed, 137 skipped, 0 failed, 0 xfailed. The skips are Postgres and live-foundation tests that need `VT_TEST_DATABASE_URL` / `VT_TEST_FOUNDATION_URL`, not set on this machine, so they were **not executed here**; hosted CI and earlier local Postgres runs executed them | pytest in a fresh venv built from `pyproject.toml` |
| Lint | `ruff check .` passes (ruff 0.16.9) | ruff |

Environment note: the machine's default Python lacks `psycopg2`, so a bare `pytest` fails at collection on `tests/test_database.py` and `tests/test_retention_interval.py`. That is an environment gap, not a repository defect; a venv from `pip install -e ".[dev]"` passes.

## 2. D3 closure verification

D3 is closed for its approved offline scope. Re-checked: approved sorts are only `views` and `published_at`; the 24-hour sorts, `views_per_hour_lifetime` and `engagement_rate` are refused with a stated reason; restricted names raise `RestrictedMetric`; the subscriber cap stays at 1,000,000; `short_form` is a duration filter. No new defect was found.

## 3. Engagement-rate finding (re-traced at the pinned commit)

`backend/domain/metrics.py` `engagement_rate(views, likes, comments)` returns `None` only when both likes and comments are `None`. If likes are hidden but comments exist it returns `(0 + comments) / views`, a silently understated value. `backend/application/discovery.py` maps `"engagement"` to `engagementRate` in `SORTS`, so ordering uses that figure. This agrees with D3 (hidden likes are counted as zero).

ViralTrack today shows the value only when likes are visible and refuses the sort. No code change is proposed. Options are in [OWNER_DECISIONS.md](OWNER_DECISIONS.md), decision 1. Recommendation: keep the committed behavior; if engagement ordering is wanted later, allow it only for rows whose likes are visible, computed in ViralTrack from raw views, likes and comments (plain arithmetic, no library).

## 4. What the foundation already provides (central to D5 and D6)

From `upstream/youtube-niche-finder/docs/http-api.md` and the source tree: a FastAPI HTTP API and an MCP server; a vanilla JavaScript dashboard (`frontend/`); a worker with snapshots; a watchlist (`/api/channels/tracked`, `POST /api/channels/track`); alerts, digest and notification settings; channel history, video trajectory and velocity from snapshots; `/api/scores`, which documents every number with formula, inputs and minimum sample; and an LLM "why it took off" explanation (204 when no LLM is configured). Backend stack from `backend/requirements.txt`: FastAPI, pydantic, httpx, mcp, sentry-sdk.

Consequence: D5 and D6 must not rebuild collection, scheduling, snapshots, watchlist storage, alerts or a dashboard. Those features exist but are internal-only under `docs/phase-1/DERIVED_METRIC_POLICY.md`. The ViralTrack work is the policy boundary: expose only ALLOWED metrics, attach provenance, keep restricted values out of every response, filter and sort.

## 5. Phase plans

### D4: discovery explanations and confidence (BLOCKED on policy)

Objective: show why a result was returned and how trustworthy the data is, without ranking or popularity claims that Google's terms may restrict.

Safe offline work now (documents only): inventory existing explanatory fields (provenance, mapping notes, `WITHHELD_*` reasons, funnel, `/api/scores`); propose a `DiscoveryExplanation` record listing, per result, the raw inputs that satisfied each filter, data age (from `Provenance.collected_at`) and which values were missing or withheld. It restates held facts; it scores nothing.

Blocked until owner and counsel decide: any statement that a result is popular, trending, viral, breakout or emerging; any ordering beyond the two approved raw sorts; any confidence value. A numeric score is not statistical confidence, and the repository has no sample-based method that supports one, so none will be produced unless a defensible method is approved.

Reuse: no scoring or explanation framework is justified. ADAPT existing `Provenance` and mapping notes into a typed record. `scipy` only if a statistical method is approved.

Acceptance: no restricted metric influences results; no unsupported claim; no fabricated confidence; missing and stale data stated; every explanation line traceable to a field; existing behavior unchanged unless approved; reuse audit recorded. Estimate: 2 to 3 working days after policy approval; the policy review is the long pole.

### D5: API and dashboard (DEFERRED, owner authorization required)

Objective: a ViralTrack-owned, policy-filtered discovery API and a thin view of it.

Recommended direction if authorized: a small FastAPI app (the framework and pydantic the foundation already uses, so no second stack) wrapping `PlatformProvider.discover()`, OpenAPI generated automatically, plus a minimal read-only page served from it (htmx is an option). `schemathesis` (MIT) as a dev-only contract-test dependency. Do not adopt a BI tool (Superset is heavy and queries tables directly; Metabase and Grafana are AGPL) or a JavaScript build chain for a first version.

Open points: who the users are and whether authentication is needed (decision 3); dashboard scope; whether the foundation dashboard stays internal and ViralTrack ships only an API.

Acceptance: only approved metrics exposed; no leakage through hidden fields, exports, filters or sorting (a response-schema test enumerating every key against `MetricPolicy`); provenance visible; schemas documented; security boundary tested; no business logic duplicated in the frontend. Estimate: API 3 to 5 days; read-only page 3 to 5 days.

### D6: history and watchlists (DEFERRED, owner authorization required)

Objective: tracked content with defensible history.

The foundation already stores snapshots, channel history and a watchlist. The recorded blocker is timestamp reliability: the discovery response carries no snapshot time, so ViralTrack cannot present 24-hour velocity as current. D6 starts with a read-only audit of what observation times the foundation's history endpoints (`/api/channels/{id}/history`, trajectory) expose. If they carry observation times, ViralTrack can map them as RAW with `Provenance.collected_at` set to the observation time; otherwise they stay unmapped. The 30-day retention applies to everything persisted. Any new ViralTrack table needs the data-retention checklist and an entry in `docs/phase-1/DATA_RETENTION_POLICY.md` first. Report-only retention stays the default.

Reuse: no new scheduler, queue or time-series engine; the foundation has a worker. TimescaleDB is a mixed-licence project (Apache-2.0, Apache-compatible and Timescale License, read from its LICENSE file) and unnecessary at this size. `ruptures` is a reference for much later.

Acceptance: defensible timestamps; no inferred history; missing never shown as zero; watchlists cannot bypass metric restrictions; retention, duplicates and failure recovery tested; provenance on every observation. Estimate: timestamp audit 2 days; the rest depends on its findings.

### D7: controlled live validation (REQUIRES SEPARATE AUTHORIZATION)

Offline preparation allowed now: choose the exact cases that need real data (real field shapes, `duration`, `publishedAt`, hidden-likes behavior); prepare a guarded harness over the existing `YouTubeProvider` and foundation path that enforces 15 units and one search call programmatically, never retries, and writes a sanitized report.

Quota accounting (corrected after reading the ledger code, `backend/infrastructure/youtube/client.py`): since 1 June 2026 `search.list` has its own bucket of 100 calls per day, and each search is also charged 1 unit to the 10,000-unit pool; channel and video reads cost about 1 unit per 50 items. So "other units" is the pool difference minus the search-call difference. The harness in [D7_OFFLINE_HARNESS.md](D7_OFFLINE_HARNESS.md) measures exactly that from `/api/health` before and after. Offline preparation is done; live execution is not authorized and no live call has been made.

## 6. Readiness summary

| Phase | Status | Can proceed offline now | Blocked by |
|---|---|---|---|
| D4 | BLOCKED | Inventory, explanation-model proposal (documents only) | Ranking and claims policy: owner and counsel |
| D5 | DEFERRED | Reuse audit and scope proposal (done here) | Owner authorization; D4 policy for what to display |
| D6 | DEFERRED | Read-only timestamp audit of foundation history endpoints | Owner authorization; retention design review |
| D7 | REQUIRES OWNER AUTHORIZATION | Harness design and authorization request | Written authorization; quota-accounting confirmation |

## 7. Risks and limitations

Technical: discovery quality on real data is unproven until D7. Operational: `discovery-offline` is not yet a required check. Licensing: only permissive dependencies are recommended; AGPL and mixed-licence tools are rejected. Privacy and data: the 30-day retention rule and the no-transcript, no-thumbnail-download, no-default-LLM rules constrain D5 and D6 displays. Cost: quota is the only live cost; offline work has none. Audit limits: licences were checked from GitHub metadata and LICENSE files; test coverage, dependency trees and security posture of candidates were not reviewed.

## 8. Recommended next action

Send the owner the checkpoint in [OWNER_DECISIONS.md](OWNER_DECISIONS.md). The smallest useful step that respects every gate is decisions 1 and 2 (engagement sort, and asking counsel the ranking question), because D4 and everything displayed in D5 depend on them. Nothing else should start before that.
