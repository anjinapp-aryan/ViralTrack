# D2 CI implementation report: dedicated upstream-backed offline job

Date: 2026-11-05. Status: **implemented, NOT YET RUN IN GITHUB ACTIONS.** The workflow is uncommitted and the files it tests are
untracked, so it cannot run until the owner commits and pushes, which this assignment forbids. Everything below marked "local" was
checked on a Windows machine; nothing about the hosted runner, the firewall rule or the reduced dependency set has been
demonstrated yet. Design basis: [D1_CI_INTEGRATION_PROPOSAL.md](D1_CI_INTEGRATION_PROPOSAL.md). D2 code: [D2_IMPLEMENTATION_REPORT.md](D2_IMPLEMENTATION_REPORT.md).

## Erratum (2026-11-06, after the independent audit and the first hosted run)

- The first hosted run (GitHub Actions run 42081777090, commit `0cdaa44`) **passed**: 277 collected, 268 passed, 9 xfailed, 0 skipped.
  The firewall rules were installed for uid 1002 (IPv4 and IPv6), the runner user kept internet access, the test user's external
  connections were refused, and the database stayed reachable.
- Two statements in this report were **wrong** and have been corrected by the hardening change
  ([CI_HARDENING_REPORT.md](CI_HARDENING_REPORT.md)): (1) "any violation makes the step, and the job, fail" was false for the isolation
  check and for a crashing report checker, because a command piped into `tee` returns `tee`'s status when `pipefail` is off; (2) the
  process identity of pytest was inferred, not verified. Both are fixed and tested offline; the fix has not yet run on GitHub.
- The firewall step took 234 s in that run; the cause is not known (see the hardening report).

## 1. What changed

| File | Change |
|---|---|
| `.github/workflows/ci.yml` | one new job, `discovery-offline`, appended (123 added lines, 0 removed). The jobs `viraltrack` and `upstream-suite` are byte-for-byte unchanged |
| `tests/support/ci_checks.py` | new, standard library only: `isolation` and `report` checks used by the job |
| `tests/support/upstream.py` | `VT_TEST_REQUIRE_UPSTREAM=1` turns "upstream Python missing" from a skip into a failure (used only by the job) |

No dependency file, Compose file, secret, schema or upstream file was touched.

## 2. Job architecture

```text
discovery-offline  (ubuntu-latest, 20 min limit, permissions: contents: read, service: pgvector/pgvector:pg16)
  1 checkout with submodules
  2 pin check: submodule must be d872014
  3 setup-python 3.12 with pip cache (keys: requirements-dev.lock, the foundation's requirements.txt)
  4 install            [network open]  ViralTrack venv /tmp/vt-venv (requirements-dev.lock) and a separate /tmp/upstream-venv
  5 import smoke test  [network open]  `import api` in the foundation venv against the database service: fails early if the reduced install is short
  6 cut off the network for the test user   (iptables + ip6tables, scoped by user)
  7 verify isolation   (as the test user: external connections must FAIL, the database must still answer)
  8 run the five test files as that user, junit report written
  9 enforce collection and skip rules (always runs)
```

The fast `viraltrack` job is not a dependency of this job and vice versa; they run in parallel.

## 3. Dependencies and rationale

- **Separate environment** because the foundation pins `anyio` 4.15.1 and ViralTrack's lock pins 4.16.0 (compared in the proposal); the
  two never share a site-packages.
- **ViralTrack environment:** the existing `requirements-dev.lock`, as the fast job installs it.
- **Foundation environment:** `pip install -c upstream/youtube-niche-finder/backend/requirements.txt fastapi httpx psycopg2-binary numpy requests python-dotenv langdetect cryptography fastembed pillow`.
  The foundation's own pinned file is used **only as a constraints file** (read, never modified, never installed with `-r`), so every
  package that does get installed is at the exact version the foundation pins, and nothing else is installed.
- **Why this list (VERIFIED locally):** importing the foundation's `api` module loaded these packages and no others of its own;
  it did **not** load `mcp`, `uvicorn` or `sentry_sdk`, which the pinned file contains only as extras. The pinned file lists
  `python-multipart` as "via mcp", so it is left out too. The test runner uses FastAPI's in-process `TestClient` (needs `httpx`) and no server.
- **Not yet verified:** that this reduced set is complete on a clean Linux runner. The local runs used a Windows virtualenv that has
  the full upstream requirements. Step 5 exists to turn any missing module into an immediate, readable failure. If it fails, the fallback is
  the full pinned file (`pip install -r`), at a cost of the extra packages.
- **Footprint (local measurement):** importing `api` pulls `fastembed`, `onnxruntime` (41 MB), `tokenizers`, `huggingface_hub`, `Pillow`
  eagerly, which cannot be avoided without changing upstream. `HF_HUB_OFFLINE=1` makes any model download fail instead of reaching out.

## 4. Network isolation: design, and a change from the proposal

**The proposal's host-wide loopback-only rule would have broken the job.** The runner agent is a process on the same machine and must reach
GitHub to stream logs and report results; a rule that rejects all non-loopback output would cut it off, and the job would hang or be
cancelled. Found by reasoning about the runner (INFERRED; not tried). It also did not allow for the database service container, which
Docker may reach through a bridge network rather than loopback.

Implemented instead, scoped by **user ID**:

- a throwaway user `vtoffline` runs `pytest` and every subprocess it starts (the foundation runner included);
- `iptables -A OUTPUT -m owner --uid-owner vtoffline -o lo -j ACCEPT`, the same for `-d 172.16.0.0/12` (Docker's private networks, where a
  service container lives), then `-j REJECT` for that user's traffic; the same for IPv6 with `ip6tables` (loopback accept, reject);
- the runner agent and Docker (other user IDs) are unaffected;
- the rules and the full `OUTPUT` chains are printed to the log;
- `command -v iptables` and `command -v ip6tables` must succeed, otherwise the step fails with a message. **There is no fallback and no
  silent downgrade**: if the rules cannot be installed, the job fails.

Verification inside the job (step 7, as `vtoffline`), implemented in `tests/support/ci_checks.py isolation`:

- connection attempts to three public IPv4 addresses and one IPv6 address **must fail**; a name lookup of an external host, if it
  succeeds, must still be followed by a failing connection;
- a TCP connection to the database at `localhost:5432` **must succeed**;
- any violation makes the step, and the job, fail. For contrast it prints (informational only) whether the runner user can still reach
  github.com.

Local evidence for the check itself (Windows, no firewall): with a local listening socket standing in for "an external host that is still
reachable", `isolation` printed `ERROR ... SUCCEEDED; isolation is not effective` and returned 1; with the database port closed it returned 1.
(That run also showed that a real connection to `pypi.org:443` succeeds on this machine, as expected without a firewall.) So the check can
fail; whether the **rule** works on a hosted runner is **not** demonstrated.

Defence in depth that already existed and is local-verified: the offline runners replace `requests` with a guard that counts and refuses calls,
remove `YOUTUBE_API_KEY` (or set an unused placeholder in the route runner), and the tests assert zero attempts.

## 5. Test selection, collection and skip enforcement

The job runs five files: `test_discovery_d1_adapter.py`, `test_discovery_d1_upstream.py`, `test_discovery_d1_policy.py`,
`test_collect_period.py`, `test_collect_period_upstream.py` (277 tests locally: 268 pass, 9 strict xfail, 0 skip).

- `VT_TEST_REQUIRE_UPSTREAM=1` and `VT_TEST_REQUIRE_PGVECTOR=1`: a missing upstream Python is a **failure**, not a skip.
- `ci_checks.py report <junit.xml>` fails the job if any expected file has fewer tests than its recorded minimum (35, 53, 35, 119, 35),
  if any test is skipped (an xfail is recognised and counted separately), or if anything failed or errored. Local check: with the upstream
  Python missing the report returned 1 with 21 problems (skips and missing files); with it present it returned 0.
- Strict `xfail` is preserved: the markers are untouched, and an unexpected pass of a strict xfail fails the job.
- The job writes install time, test time, package count, environment size, the isolation output and the per-file counts to the run summary.

The minimum counts are a lower bound at the time of writing and must be raised when tests are added.

## 6. Local validation evidence

| Check | Result |
|---|---|
| Workflow YAML parses; three jobs; new job has the nine steps above | yes (PyYAML) |
| Diff of `ci.yml` | additions only (123 lines), existing jobs unchanged |
| The five files with the junit report and the report check | 268 passed, 9 xfailed, 0 skipped; check exit 0; 154 s on Windows |
| `ruff check .` (includes the new support files) | passes |
| Fast-job conditions (database, no upstream Python), full suite | 454 passed, 0 failed, 103 skipped, 7 xfailed |
| `iptables`, the hosted runner, the reduced dependency install, the `vtoffline` user and file permissions | **not checked** (Windows machine) |

## 7. First CI run: evidence still to be collected

Nothing has run in GitHub Actions. After the owner commits and pushes, the run summary of `discovery-offline` will contain the numbers requested.
Until then every line is unknown:

| Item | Value |
|---|---|
| Dependency installation duration | UNKNOWN (est. 1 to 2 minutes; no measurement exists for this job) |
| Test duration | UNKNOWN (154 s locally on Windows) |
| Collected tests | expected 277 |
| Passed / failed / skipped / xfailed | expected 268 / 0 / 0 / 9 |
| Network isolation installed | UNKNOWN |
| Local database reachable under isolation | UNKNOWN |
| Fast job stays green | UNKNOWN (expected: unchanged; the new tests add 154 tests to it, of which the upstream-backed ones skip there) |

## 8. Known runner limitations and risks (INFERRED unless stated)

- `/home/runner` and `/home/runner/work` may not be traversable by another user; the job runs `chmod o+x` on both. If the repository path
  differs, the test step fails with a permission error rather than hiding anything.
- If Docker reaches the service container through an address outside `172.16.0.0/12`, step 7 or the tests fail on the database; the failure
  is visible and the range can be adjusted.
- The test user has no shell and no write access outside `/tmp/vt-offline` and its own home; pytest's cache and bytecode writing are disabled.
- If hosted runners ever lack `iptables`, the job fails by design (no substitute is applied).
- Reasoning about the runner agent is inference; the user-scoped rule is the safer of the two designs but is untested.

## 9. Statement

No secrets, no YouTube key and no quota were used: the job defines none, has `contents: read` only, and the tests make no YouTube call. The existing
`viraltrack` job is unchanged. This job has **not** been run, so the claim that the isolation and the reduced install work is withheld
until the first run.
