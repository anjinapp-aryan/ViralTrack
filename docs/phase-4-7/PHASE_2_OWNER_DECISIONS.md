# Phase 2: owner decisions and readiness

Date: 2026-11-07. Nothing below is assumed approved. Companions: [PHASE_2_ARCHITECTURE_PROPOSAL.md](PHASE_2_ARCHITECTURE_PROPOSAL.md), [PHASE_2_IMPLEMENTATION_ROADMAP.md](PHASE_2_IMPLEMENTATION_ROADMAP.md), [POST_FRONTEND_CI_REPORT.md](POST_FRONTEND_CI_REPORT.md), [OWNER_DECISIONS.md](OWNER_DECISIONS.md).

## 1. Decisions needed

| # | Decision | Options | Recommendation | Blocks |
|---|---|---|---|---|
| 1 | Push `c3adf7e` so hosted CI can verify the D5 test fix and the new `web` job. `origin/main` is red right now | push / hold | Push, then wait for a green run | everything below |
| 2 | Make `web` a required check once it is green (with `viraltrack` and `discovery-offline`) | yes / no | Yes; steps in [CI_REQUIRED_CHECK.md](CI_REQUIRED_CHECK.md) | CI trust |
| 3 | Add `tests/test_api_d5.py` to the network-isolated `discovery-offline` job so the real-foundation D5 tests run on a hosted runner | yes / no | Yes; it also needs a per-file minimum in `tests/support/ci_checks.py` | hosted coverage of D5 |
| 4 | Authorize Phase 2A (creators, offline, no persistence, no dependency) | authorize / defer | Authorize | 2A |
| 5 | Source of the creator's video list: the foundation's `/channels/{id}/velocity` with raw fields only and local `published_at` order, or defer the list | use / defer | Use; it is the only source and the mapping keeps it policy-safe | 2A scope |
| 6 | Show `country`, `created_at` and `total_views` on the creator page | yes / no | Yes (raw platform values) | 2A scope |
| 7 | Authorize D6 (history and watchlist), starting with the timestamp audit | authorize / defer | Defer until 2A is done; then authorize the audit only | 2B, 2C |
| 8 | Classify "change in followers between two stored snapshots" as an allowed simple calculation, and its wording | allow with wording "change between two snapshots" / do not show | Allow, with both times shown | 2B |
| 9 | Watchlist writes (add, remove) and the authentication boundary they need | read-only mirror first / writes with an authentication proxy | Read-only mirror first; choose the authentication pattern before any write | 2C |
| 10 | Alerts: allow-list of event kinds (`title_change`, `silence_break`, `channel_gone`, `video_gone`) and whether Telegram or webhook delivery is ever allowed | allow-list only / also delivery / defer | Defer; counsel first (D4) | 2D |
| 11 | D7 live validation (one search call, at most 15 other units) to confirm real response shapes, timestamps and zero counts | authorize with the full request / not yet | Not yet; ask after 2A so one run can check both | 2B trust |
| 12 | Counsel questions of D4 (ranking, claims, wording) | send / hold | Send; they gate any "best creators", growth wording and alerts | 2D, wording |

## 2. Readiness

| Part | Status | What it needs |
|---|---|---|
| CI fix and `web` job | READY (committed locally) | decision 1 |
| 2A creators | READY, REQUIRES OWNER AUTHORIZATION | decisions 4 to 6 |
| 2B history | BLOCKED | D6 (7), snapshot classification (8), D7 check (11) |
| 2C watchlist | BLOCKED | D6 (7); authentication for writes (9) |
| 2D alerts | BLOCKED | D6 (7), counsel (12), delivery decision (10) |
| Any score, grade, projection, revenue, "best creator" ranking | BLOCKED by policy | not planned |

## 3. Summary of existing, reusable, adapted and new work

- **Already exists upstream:** collection and refresh, quota ledger, channel profile and history, watchlist, alert scan and delivery, score explanations, the internal dashboard.
- **Reuse as is:** all of the above through the foundation HTTP API; FastAPI, pydantic, the provider layer, the metric policy, provenance and retention; shadcn-admin, shadcn/ui, TanStack, Recharts (when the chart is built).
- **Adapt:** the creator profile mapping (three more raw fields) and the per-creator video list (four raw fields, local order).
- **Genuinely build (small):** the raw-only video mapping and its tests, the creator pages, later an alert allow-list.
- **Blocked:** history, watchlist, alerts, any scoring; D6 and D7 are not authorized; live data is not touched.
