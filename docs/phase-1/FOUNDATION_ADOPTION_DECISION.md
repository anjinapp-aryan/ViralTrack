# Foundation Adoption Decision

**Chosen strategy: Option E — compose.** The upstream project is kept whole and unmodified, as a pinned
git submodule, and run as a service. ViralTrack's own domain lives outside it and reaches it only
through its documented HTTP API and, for retention, its database.

## What was adopted

| Item | Value |
|---|---|
| Repository | https://github.com/pandich93/youtube-niche-finder |
| Commit | `d872014` (main, 2026-10-25; 37 commits after release v0.5.0) |
| License | MIT (c) 2026 Fozil Umarov |
| Location in ViralTrack | `upstream/youtube-niche-finder` (git submodule) |
| Local modifications | **None.** The submodule is byte-identical to upstream. |

## Options considered

| Option | Verdict | Why |
|---|---|---|
| A. Fork/adopt the whole project and develop inside it | Rejected | ViralTrack code would mix with upstream code, so every upstream release becomes a merge. YouTube concepts would leak into the ViralTrack domain. Upstream moves fast (317 commits in two months). |
| B. Vendor selected modules | Rejected | Upstream modules read environment variables at import time and share one Postgres connection layer; pulling some out breaks them. Vendored copies stop getting upstream fixes. |
| C. Use it as a library dependency | Rejected | Upstream says "the backend is not an installable package" (`backend/pyproject.toml`): there is no package to depend on. |
| D. Extract reusable components into ViralTrack | Rejected | Amounts to a rewrite of tested code (1,786 tests, all passing), which goes against the reuse rule. |
| **E. Compose: run the foundation as a service and keep the ViralTrack domain independent** | **Chosen** | See below. |

## Why E

| Criterion | How E meets it |
|---|---|
| Maintainability | Upstream code is untouched. ViralTrack code is about 1,220 lines in its own package (plus 540 lines of tests). |
| Upgradeability | Upgrading means moving the submodule pin and re-running CI. `tests/test_retention_policy.py` fails if upstream adds a table the retention policy does not classify. |
| License compliance | Upstream's LICENSE stays with its source inside the submodule. Nothing is copied into ViralTrack code. |
| Isolation | The ViralTrack domain (`viraltrack/domain`) imports nothing from upstream. |
| Testability | The adapter is tested with recorded upstream responses. Retention is tested against the real upstream DDL. |
| Instagram/TikTok later | New providers implement `PlatformProvider`. Nothing YouTube-specific is in the domain. |
| Other data providers | Same interface. |
| Replacing the YouTube implementation later | Only `viraltrack/providers/youtube/` knows niche-finder exists. |

## Two deliberate couplings

1. **HTTP API.** `docs/http-api.md` is generated from upstream code and checked in upstream CI, so it is the most
   stable surface upstream offers.
2. **Database schema, used only by the retention job.** Retention needs to delete rows, and no upstream API
   does that. The coupling is guarded by a contract test that reads the pinned upstream schema.

## Not adopted (unchanged from Phase 0)

TikTok-Api, instaloader, Douyin_TikTok_Download_API and jev-social are not adopted: their data routes are not
legitimate for a commercial product. yuben-app, open-outlier, content-dashboard and social-dash remain
reference material only. None of their code is used.
