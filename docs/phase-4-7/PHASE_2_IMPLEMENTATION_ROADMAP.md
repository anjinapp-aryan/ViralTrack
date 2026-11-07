# Phase 2 (creator intelligence): implementation roadmap and phase dependencies

Date: 2026-11-07. A plan; nothing here is authorized. Related: [PHASE_2_ARCHITECTURE_PROPOSAL.md](PHASE_2_ARCHITECTURE_PROPOSAL.md), [PHASE_DEPENDENCY_MATRIX.md](PHASE_DEPENDENCY_MATRIX.md), [MASTER_ROADMAP.md](MASTER_ROADMAP.md). Estimates are working days for one engineer and are rough.

## 1. How Phase 2, D6 and D7 relate

The owner's Phase 2 ("creator intelligence") covers creators, watchlists, history and alerts. In the repository's roadmap, **history and watchlists are D6**, which stays deferred. So Phase 2 splits at that line:

| Part | Content | Needs D6? | Needs D7? | Needs D4 (claims policy)? |
|---|---|---|---|---|
| **2A** | creator list, creator detail (raw profile), creator's videos | no | not to build; useful afterwards to confirm real response shapes | no, if wording stays neutral |
| **2B** | creator history chart, change between two snapshots | **yes** (authorization and the retention design) | **yes for the timestamp and zero-count checks** before the chart is trusted | wording of "growth" |
| **2C** | watchlist read, then add and remove | **yes** | no | no |
| **2D** | alerts inbox, allow-listed kinds | **yes** | no | **yes** (what may be called an alert, trend or outlier) |

- **D6 depends on** an owner authorization and a retention design review. Its first step is the read-only timestamp audit already named in the master roadmap; this audit adds evidence (see the audit document, finding 2) but does not replace the real-data check.
- **D7 depends on** a separate written authorization and the quota-accounting confirmation in [D7_OFFLINE_HARNESS.md](D7_OFFLINE_HARNESS.md). It is independent of Phase 2 code, but 2B should not be trusted on real data without it.
- **Authentication** (reverse proxy with OpenID Connect) is a prerequisite for any write route or any shared deployment (2C writes). It is not needed for 2A, which is read-only and localhost only.
- **Hosted CI** must be green first: `origin/main` is currently red (see [POST_FRONTEND_CI_REPORT.md](POST_FRONTEND_CI_REPORT.md)); the fix is committed locally and needs a push.

## 2. Sequence

| Step | Work | Blocked by | Estimate |
|---|---|---|---|
| 0 | Push `c3adf7e`; confirm hosted `viraltrack`, `web` and `discovery-offline` are green; make `web` required | owner push | 0.5 |
| 1 (**2A**) | Provider: three more raw profile fields; `get_creator_videos` with raw-only mapping and local `published_at` order; capability note; tests including a fixture ordered by the withheld rate | owner authorization of 2A | 2 to 3 |
| 2 (**2A**) | API: extended creator detail, `GET /creators/{id}/videos`, schema and guard tests, regenerated OpenAPI snapshot and types; real-foundation integration tests | step 1 | 1.5 to 2 |
| 3 (**2A**) | Frontend: Creators and Creator detail pages, sidebar entry, tests (states, missing values, no derived value, axe, keyboard), screenshots | step 2 | 4 to 5 |
| 4 (**2A**) | Review, full local suites, hosted CI, completion report; stop for approval | step 3 | 1 |
| 5 (**D6**) | Timestamp audit of the foundation history on real data (needs D7 authorization) and retention design | D6 and D7 authorization | 2 plus the live run |
| 6 (**2B**) | History endpoint, chart (re-add `recharts` through the shadcn chart component, with its licence and audit scan), snapshot-change display, tests | step 5 | 4 to 6 |
| 7 (**2C**) | Watchlist read mirror; later, writes behind authentication and a quota guard | D6; authentication decision | 2 to 3 (read); 4 to 6 (writes) |
| 8 (**2D**) | Alert allow-list, inbox | D6; D4; delivery decision | 3 to 5 |

2A, steps 1 to 4: about 9 to 11 working days. 2B to 2D together: about 15 to 25 more, depending on the owner's decisions.

## 3. What can proceed offline now (after authorization)

All of 2A. It needs no persistence, no quota, no live call and no new dependency.

## 4. What is blocked

2B (D6, D7 check), 2C writes (authentication, quota guard), 2D (D4 policy, delivery decision), any ranking or "best creators" view (D4), any score or grade (policy: restricted).

## 5. Risks

- Upstream order and fields: the per-creator video list is ordered by a withheld value and mixes restricted fields; mitigated by the raw-only mapping and local ordering, and by a test that fails if either changes.
- The 1,000-item creator window: creators come from discovered videos, so a creator with few collected videos may be missing; stated in the UI.
- Zero counts on channels with partial data (upstream `or 0`); needs the D7 check and a UI note.
- 30-day history until the Analytics and Reporting amendment is accepted.
- The API remains unauthenticated and local only.
- Cost of a quota-spending route if writes are added later.

## 6. Acceptance gate for the first milestone (2A)

Defined in the architecture proposal, section 7. The milestone ends with a completion report and a stop; 2B to 2D start only on separate authorization.
