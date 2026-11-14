# Post-frontend CI report

Date: 2026-11-07. Scope: Stage A (baseline) and Stage B (hosted CI) of the post-frontend task. No YouTube call, no quota, no push, no commit by the assistant. Authoritative companions: [CI_REQUIRED_CHECK.md](CI_REQUIRED_CHECK.md) (required-check steps) and [FRONTEND_PHASE_1_REPORT.md](FRONTEND_PHASE_1_REPORT.md).

## 1. Verified baseline

| Item | Result | How verified |
|---|---|---|
| HEAD | `c3adf7e` "fixing issues" (owner commit), one commit ahead of `origin/main` | `git status -sb`, `git log` |
| `origin/main` | `2ffec39` "added UI Support" (screenshots only; its parent `8916e37` is the frontend phase 1 commit) | `git fetch`, `gh` |
| Working tree | clean | `git status` |
| Submodule | `upstream/youtube-niche-finder` at `d872014`, unmodified | `git submodule status` |
| `c3adf7e` contents | exactly the three files this report describes: `.github/workflows/ci.yml`, `tests/test_api_d5.py`, `web/package.json` | `git show --stat` |

## 2. Hosted CI at `origin/main`: RED

GitHub Actions run `42365090372` for `2ffec39`:

| Job | Result |
|---|---|
| `viraltrack` | **failure** (step "Tests") |
| `discovery-offline` | success |
| `upstream-suite` | skipped (scheduled or manual only) |

Previous runs (`48aa81a`, `81a4214`, `907c601`) were all green, so the failure was introduced by the D5 / frontend phase 1 commits. The frontend commit was never tested on a hosted runner before it was pushed.

### Root cause

Three tests failed, all D5 integration tests that run the real foundation code on PostgreSQL: `test_integration_discover_on_the_real_foundation_is_policy_clean`, `..._pages_do_not_overlap_...` and `..._search_creators_and_detail_...`. Each got HTTP 500 from the API.

The hosted `viraltrack` job provides a PostgreSQL service (`VT_TEST_DATABASE_URL`) but, by design, no separate Python with the foundation's requirements (`VT_TEST_UPSTREAM_PYTHON`). The existing foundation-backed tests call `upstream_python()` first, which skips (or fails when `VT_TEST_REQUIRE_UPSTREAM=1`). My new `real_foundation` fixture seeded the database first and only called the foundation runner later, inside the mocked HTTP transport, so the missing interpreter surfaced as a server error instead of a skip. It never appeared locally because every local run set `VT_TEST_UPSTREAM_PYTHON`.

(The `duplicate key value violates unique constraint "videos_pkey"` line in the same log is PostgreSQL noting a deliberate duplicate-insert test elsewhere in the suite, not a cause.)

### Fix (already in `c3adf7e`)

`real_foundation` now calls `upstream_python()` before anything else. Reproduced the hosted environment locally (database set, no foundation Python): the three tests now **skip** with the standard message (149 passed, 3 skipped); with the foundation Python set, all pass (152 passed). The fix changes only the fixture, no assertion and no production code.

## 3. New `web` job (already in `c3adf7e`, not yet run on GitHub)

The existing workflow did not test `web/` at all. A dedicated job was added to `.github/workflows/ci.yml`, placed before `discovery-offline` because `tests/test_ci_checks.py` reads the workflow text from that job to the end of the file.

| Step | Command | Notes |
|---|---|---|
| Node | `actions/setup-node@v4`, Node 22 | Vite 8 requires 20.19 or 22.12 and later |
| Pinned pnpm | `corepack enable` | version from `"packageManager": "pnpm@10.20.0"`, added to `web/package.json`; no extra third-party action |
| Locked install | `pnpm install --frozen-lockfile` | fails if the lockfile is not current |
| Contract drift | `pnpm run api:types` then `git diff --exit-code -- src/lib/api/schema.d.ts` | the generated types must match `docs/api/openapi-v1.json` |
| Type check | `pnpm exec tsc -b` | |
| Lint | `pnpm exec eslint .` | |
| Format | `pnpm exec prettier --check .` | |
| Build | `pnpm run build` | |
| Test browser | `pnpm exec playwright install --with-deps chromium` | |
| Tests | `pnpm test` | Vitest in Chromium, includes the axe accessibility checks |
| Audit | `pnpm audit --prod`; `pnpm audit --audit-level high`; `pnpm audit \|\| true` | production tree must be clean; no high or critical anywhere; lower dev-tool advisories are listed but do not fail |

The Python side needs no new step: the `viraltrack` job already runs the whole suite, including the OpenAPI snapshot consistency test and the policy tests. Nothing in the existing jobs was weakened or removed.

### Local evidence (a clean copy of the committed tree, fresh install from the lockfile)

| Step | Result |
|---|---|
| `pnpm install --frozen-lockfile` | succeeds |
| API types drift check | consistent |
| `tsc -b`, ESLint | clean |
| Prettier | clean (see the line-ending note) |
| Build | succeeds |
| Vitest | 92 passed, 0 failed, 0 skipped |
| `audit --prod` | no known vulnerabilities |
| `audit --audit-level high` | exit 0; the full audit lists 2 moderate (ESLint toolchain, dev only) |

Not verifiable locally: `corepack enable` (needs administrator rights on this Windows machine; it works on the Linux runner), Linux browser dependencies, and the actual GitHub execution. The workflow was parsed as valid YAML with the expected job and step list.

Line-ending note: the repository stores LF and `web/.prettierrc` requires LF, so Linux checkouts pass. On Windows with `core.autocrlf=true`, working copies are CRLF and Prettier reports every file; `pnpm format` or an LF checkout fixes it. A `.gitattributes` rule (`web/** text eol=lf`) would remove the trap. That is a one-line optional change, not made here.

## 4. What remains for hosted verification (needs the owner's push)

1. Push `c3adf7e`. Expected: `viraltrack` green again (three tests skip), `web` green, `discovery-offline` green.
2. If `web` fails on the runner, the most likely causes are the browser dependencies step or `corepack enable`; the workflow log names the step.
3. After one green run, add `web` to the required checks (see [CI_REQUIRED_CHECK.md](CI_REQUIRED_CHECK.md)). Because the current `origin/main` is red, the first protected push should wait for that run.

## 5. Recommendations (not implemented)

- The D5 real-foundation integration tests never run on a hosted runner today. To run them under the network-isolated `discovery-offline` job, add `tests/test_api_d5.py` to its file list and give it a per-file minimum in `tests/support/ci_checks.py`. It changes the gate's expectations, so it is the owner's call.
- Pull-request runs of the new job have not been observed (same caveat as before).
- Frontend tests pull Chromium (about 110 MB) on every run; a cache of `~/.cache/ms-playwright` would save a minute and is not added to keep the job simple.

## 6. Update 2026-11-14: hosted results and the repairs

### What was pushed

The owner pushed `c3adf7e` and the six Phase 2 documents together as `1cabc36`; `origin/main` is `1cabc36`. There was nothing left for the assistant to push.

### Hosted CI on `1cabc36`: still RED (run `42399588182`, repeated as `42616034887`)

| Job | Result | Cause |
|---|---|---|
| `discovery-offline` | success | |
| `upstream-suite` | skipped (scheduled or manual only) | |
| `viraltrack` | **failure** at "Check the lockfile is current" | a new `fastapi` release: the runner resolves `fastapi==0.162.2`, `requirements-dev.lock` pins `0.162.0` (the only differing line). The D5 test fix itself worked: the three tests are no longer the failure |
| `web` | **failure** at "Install the test browser" | `ubuntu-latest` is now Ubuntu 26.04 and Playwright 1.59.1 supports Chromium up to Ubuntu 24.04 ("Playwright does not support chromium on ubuntu26.04-x64") |

Neither failure is in the application code. The first is the lockfile check working as designed (it compares a fresh resolution with the lockfile, so any upstream release makes it fail until the lock is regenerated); the second is a runner image change.

### Repairs (prepared, uncommitted; need the owner's approval to commit and push)

1. `requirements-dev.lock` regenerated with the CI's own method (a fresh resolve into a new file; resolving into the existing file keeps the old pins). One line changes: `fastapi==0.162.0` to `0.162.2`. Verified: a fresh compile now matches it.
2. `.github/workflows/ci.yml`: the `web` job runs on `ubuntu-24.04` with a comment saying to move it together with the Playwright version.
3. Stage 3, the real-foundation environment: `tests/test_api_d5.py` (152 tests, 4 of them against the pinned foundation) and `tests/test_creators_2a.py` (86 tests, 2 of them against it) are added to the network-isolated `discovery-offline` job, with per-file minimums in `tests/support/ci_checks.py` (152 and 86).

### Network-isolated real-foundation environment (already existed; now covers the API)

`discovery-offline` is the environment asked for: a separate virtual environment holding the pinned foundation's requirements, a throwaway PostgreSQL service, synthetic seeded data, `YOUTUBE_*` and `NICHE_*` variables removed, `requests` replaced by a refusing guard, and the test user's outbound traffic blocked by firewall rules (loopback and the database allowed), with a JUnit gate that fails on any skip, xfail, missing file or shortfall below the minimums. Local run of that job's exact file list, with the database and the pinned foundation: **519 passed, 0 failed, 0 skipped, 0 xfailed**; gate passed. The foundation tests there run the foundation's real code, not mocks; the offline mock transport tests sit beside them.

### Remaining steps for hosted verification (owner)

1. Approve and push the repairs (lockfile, runner pin, job list and minimums).
2. Expected on the next run: `viraltrack`, `web` and `discovery-offline` green (`upstream-suite` skipped). If `web` still fails, the log names the step; the browser dependency step is the first suspect.
3. **Required check names** (job ids, as shown by `gh api repos/anjinapp-aryan/ViralTrack/commits/<sha>/check-runs`): `viraltrack`, `web`, `discovery-offline`. Do not require `upstream-suite`.
4. **Branch protection** (repository Settings, Rules, Rulesets, New branch ruleset): target `main`, enable "Require status checks to pass", add the three names above (they appear in the picker only after they have run), add the owner as a bypass actor if direct pushes should continue. The exact steps and a `gh api` command are in [CI_REQUIRED_CHECK.md](CI_REQUIRED_CHECK.md). Nothing was changed in GitHub.
5. Consider a scheduled or manual workflow that regenerates and proposes `requirements-dev.lock`: any upstream release turns the lockfile check red until someone regenerates it. That is a design choice of the existing check; it is not changed here.
