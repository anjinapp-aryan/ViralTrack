# CI hardening report: `discovery-offline` (five corrections from the D2 audit)

Date: 2026-11-06. Status: implemented and tested offline, **not committed, not yet run on GitHub**. No D2 production code, upstream file,
schema or Compose file was changed; no YouTube request, quota, commit or push. The job is **not** a required check and must not
become one until it has run green with these corrections.
Background: [D2_CI_IMPLEMENTATION_REPORT.md](D2_CI_IMPLEMENTATION_REPORT.md) (with its erratum) and the audit that preceded this change.

## 1. Initial state

`main` at `0cdaa44` equal to `origin/main`, clean working tree, nothing staged, submodule `d872014`. The job had already run once on GitHub
(run `42081777090`): 277 collected, 268 passed, 9 xfailed, 0 skipped; the firewall step took 234 s.

## 2. Changed files

| File | Change |
|---|---|
| `.github/workflows/ci.yml` | only the `discovery-offline` job (95 added, 21 removed against `0cdaa44`; against the baseline `5ed12ec` the file is 197 additions, 0 deletions, so `viraltrack` and `upstream-suite` are untouched) |
| `tests/support/ci_checks.py` | rewritten: `gate`, `require-summary`, exact xfail set, process-identity checks, hardened `isolation` |
| `tests/conftest.py` | +22 lines: `pytest_report_header` and `pytest_sessionstart` (identity check, active only when `VT_TEST_EXPECT_UID` is set) |
| `tests/support/upstream.py`, `upstream_runner.py`, `upstream_collect_runner.py` | the foundation runners report their uid/gid; the parent verifies it when `VT_TEST_EXPECT_UID` is set |
| `tests/test_ci_checks.py` | new: 39 offline negative and positive controls |
| `docs/phase-3/D2_CI_IMPLEMENTATION_REPORT.md` | erratum corrects two false statements |
| `docs/phase-3/CI_HARDENING_REPORT.md` | this report |

## 3. Findings and corrections

| # | Finding | Correction | Evidence |
|---|---|---|---|
| 1 HIGH | Piped commands hide failures (`cmd \| tee` returns `tee`'s status without `pipefail`), so the isolation gate could not fail the job | Job-level `defaults.run.shell: bash` **and** an explicit `set -o pipefail` as the first line of every multi-line step; a static test enforces both; single-line steps may not contain a pipe | controls A, B and the step-level tests below |
| 2 MEDIUM | A missing, malformed or truncated JUnit report, or a missing summary, passed silently | `ci_checks.py gate` analyses the report without raising, **always** writes the summary, fails on any problem; `require-summary` fails for a missing, empty or header-less summary; the step has no pipe and `exit`s with the combined status; the old `\| tee summary.md` and `! grep` are gone | controls C to G |
| 3 MEDIUM | The identity of the pytest process was inferred | The job derives the numeric uid/gid of `vtoffline`, checks it differs from the runner's, checks that both rule sets name that numeric uid, prints `sudo -u vtoffline id`, and passes `VT_TEST_EXPECT_UID/GID` to pytest. `conftest.py` reads the real and effective ids from the operating system and **aborts the session (exit 3)** on a mismatch; the foundation runners report their own ids and the parent asserts them; the isolation check asserts them as well; pytest's header prints the identity | controls H, I |
| 4 MEDIUM | An unexplained 234 s firewall step | Every command in that step runs through `t`, which prints its start time (UTC), duration and exit status; the step prints its own total. Not identified yet (section 6) | log of the next run |
| 5 LOW | The number of xfails was not asserted | `EXPECTED_XFAILS` lists the nine known strict xfails by test id; the gate requires exactly that set (count and names); a test checks the list against the strict `xfail` markers in the sources | controls J |

Also added (informational only, never failing the job): a `Network diagnostics` step after the tests that prints the per-rule packet counters,
the resolver configuration, name resolution as the test user, docker networks and the database container's addresses, the listeners on 5432
and the database role's attributes.

## 4. Negative controls (offline) and exit statuses

All run on this machine (Windows, Git Bash, no network access, no database).

| Control | Command | Exit |
|---|---|---|
| A. failing command piped to `tee`, old behaviour | `bash -e -c 'false \| tee /dev/null'` | **0** (the defect, reproduced) |
| B. same with `pipefail` | `bash -e -o pipefail -c 'false \| tee /dev/null'` | **1** |
| C. valid report | `ci_checks.py gate valid.xml valid.md` | **0** |
| D. truncated report | `... gate truncated.xml ...` | **1** |
| E. malformed report | `... gate malformed.xml ...` | **1** |
| F. empty report | `... gate empty.xml ...` | **1** |
| F2. missing report | `... gate absent.xml ...` | **1**, and the summary was still written |
| G. missing summary | `ci_checks.py require-summary nothing.md` | **1** |
| G2. empty summary | `... require-summary blank.md` | **1** |
| G3. valid summary | `... require-summary valid.md` | **0** |
| H. wrong pytest uid | `VT_TEST_EXPECT_UID=99999 VT_TEST_EXPECT_GID=99999 pytest tests/test_domain.py` | **3** (`wrong process identity`) |
| I. right uid | POSIX only (this machine has no uid); covered by `test_pytest_starts_as_the_right_user_...` which skips here and runs on Linux | skipped locally |
| J. wrong xfail count or names | unit tests: 8 xfails, 10 xfails, a swapped name | each **1** |

The same controls exist as tests in `tests/test_ci_checks.py`. Beyond the commands above, they also run the **real text of the workflow steps**
under `bash -e` with stubs: the isolation step with a failing check exits non-zero and with a passing check exits 0; the report step exits
non-zero for a missing, empty, malformed, truncated or test-less report, exits 0 for a valid one, and exits non-zero when the checker succeeds
but writes no summary.

## 5. Test results

Local PostgreSQL 16.2 with pgvector 0.6.2; exit status 0 for every run.

| Run | Passed | Failed | Skipped | Xfailed |
|---|---|---|---|---|
| The five CI files with `--junitxml`, then the real `gate` | 268 | 0 | 0 | 9 (**gate exit 0**, so the nine ids match the real report) |
| `tests/test_ci_checks.py` alone | 37 | 0 | 2 (POSIX-only) | 0 |
| Full suite, database + upstream Python, `VT_TEST_REQUIRE_UPSTREAM=1` | **590** | 0 | 4 (2 live-foundation, 2 POSIX-only) | 9 |
| Full suite, database only (the fast job's conditions) | 491 | 0 | 105 | 7 |
| Plain `pytest` | 467 | 0 | 129 | 7 |
| `ruff check .` | clean | | | |

Before this change the corresponding full-suite figures were 553 / 454 / 430 passed.

## 6. Firewall timing

- **Measured on GitHub (before this change):** the whole "Cut off the network" step took 234 s (18:11:48 to 18:15:42 UTC). The log has no
  per-command times, so the slow command is **not identified**. It is one of: `sudo useradd --create-home`, `sudo chmod`, `mkdir`/`chmod`, or
  one of the three `sudo iptables -A` commands; the later `sudo -u vtoffline` calls were instantaneous, so `sudo` itself is not generally slow.
- **Local measurement:** none possible. This machine runs Windows; `useradd` and `iptables` do not exist here, so any number I gave would be invented.
- **Instrumentation added:** the next hosted run prints, per command, `[HH:MM:SS UTC] seconds rc=N command`, plus the step total. The cause will be
  visible there. If a single command dominates, the options are to run it earlier in parallel with the install, replace it, or add a time limit; none is applied here.

## 7. Network investigation

Evidence from the first hosted run, plus what the new diagnostics will add.

| Topic | Finding | Status |
|---|---|---|
| IPv4 rules | three rules for uid 1002: accept loopback, accept `172.16.0.0/12`, reject the rest (`icmp-port-unreachable`); external IPv4 targets answered `Connection refused` | verified on GitHub |
| IPv6 rules | installed (accept loopback, reject the rest); the external IPv6 target answered `Network is unreachable` because the runner has no IPv6 route, so the IPv6 REJECT rule never fired | rule present, effect **not exercised** |
| Scope | the runner user still reached github.com (HTTP 200): the agent is not affected | verified |
| DNS | the lookup of an external name **succeeded** for the test user (the message printed only after `getaddrinfo` returned); it goes through the loopback stub resolver, which runs as another user and is not blocked | verified: DNS is open |
| Docker / database | the database was reachable through `localhost:5432`; which rule carried it (loopback via the userland proxy, or the `172.16.0.0/12` allowance) is **unknown** until the counters are printed | pending next run |
| `172.16.0.0/12` | spans about a million addresses; likely unnecessary because of the loopback path (inferred) | pending counters |
| PostgreSQL permissions | the service role `vt` is the image's `POSTGRES_USER`, hence a superuser (inferred from the image's behaviour); a superuser can start programs inside the database container (for example `COPY ... PROGRAM`), which is outside the user-ID rule | the next run prints `rolsuper` |

### Proposed changes (NOT applied; need owner approval)

1. **Remove or narrow `172.16.0.0/12`:** drop it if the counters show the loopback rule carries the database traffic; otherwise allow only the database container's address (from `docker inspect`) instead of a million addresses.
2. **Close DNS for the test user:** reject port 53 (UDP and TCP) for that uid before the loopback accept, so only `localhost` and `/etc/hosts` names resolve. A local resolver listens on loopback, so a port-53 reject is needed in addition to the existing rules.
3. **Stop the superuser bypass:** have an administrator create the extension once and run the tests under a non-superuser role that owns the test database. That changes the foundation's start-up assumptions (it creates the vector extension itself) and needs its own check.
4. **Per-command time limits** in the firewall step once the slow command is known.

Limits that remain after this change: the isolation is a strong guardrail for accidental network use by test code, **not a security boundary against hostile test code**. It does not cover DNS, the database-superuser path or IPv6 routing; no new network call was introduced.

## 8. Not verified (needs the next hosted run)

- That `defaults.run.shell: bash` plus `set -o pipefail` runs cleanly on the hosted runner (the step texts were executed under Git Bash here).
- The numeric uid/gid, the identity line in pytest's header, and the foundation runner's reported ids on Linux.
- The firewall command timings and the rule counters.
- That the `Network diagnostics` commands behave on the runner (each is `|| true`, the step is `continue-on-error`).
- That the fast `viraltrack` job stays green: it now also runs `tests/test_ci_checks.py` (it needs `bash`, which the runner has).

A **negative control on GitHub** is still advisable once: a temporary workflow change that makes the isolation check fail, to see the job turn red. This was not done because it needs a push.

## 9. Statement

D2 production code is unchanged (`git diff HEAD -- viraltrack` is empty). D3 was not started. No YouTube API call, no quota, no commit and no push occurred; the
local PostgreSQL used for the tests was stopped afterwards. The isolation tests use local sockets only; no external address was contacted in this change.
