# D1 CI integration proposal: running the upstream-backed offline tests in GitHub Actions

Date: 2026-11-05. PROPOSAL only. `.github/workflows/ci.yml` was not changed, nothing was installed, no CI run was triggered.
Labels as in [D1_CLOSURE_REPORT.md](D1_CLOSURE_REPORT.md): VERIFIED, INFERRED, PROPOSED, UNKNOWN, BLOCKED.

## 1. Problem

VERIFIED: 66 of the 123 D1 tests (those that replay the real upstream: most of `tests/test_discovery_d1_upstream.py` and
`tests/test_discovery_d1_policy.py`) need `VT_TEST_UPSTREAM_PYTHON`, a Python with the upstream requirements. The existing CI job
`viraltrack` installs `requirements-dev.lock` only, so they skip (run B of the D1 report: 335 passed, 68 skipped, 7 xfailed; 2 of the skips are the live-foundation tests, 66 are these).
The root-cause regression replay and the upstream-semantics tests therefore do not guard pull requests today.

## 2. Evidence gathered (read-only)

| Fact | Source |
|---|---|
| Existing job: PostgreSQL service `pgvector/pgvector:pg16`, `permissions: contents: read`, submodules checked out, pin check `d872014`, whole job about 40 s (install 6 s, tests 15 s) | `.github/workflows/ci.yml`; `gh run view 41878459985` step times |
| `upstream-suite` job installs `upstream/youtube-niche-finder/backend/requirements.txt` (269 lines, 86 pinned packages) and runs only on schedule or manual dispatch | `ci.yml`; the file |
| **No scheduled or manual run of `upstream-suite` exists in the repository history**, so its install and test time was **never measured** (UNKNOWN) | `gh run list` (all 40 recent runs are `push`) |
| Importing the upstream `api` module loads about 46 third-party top-level packages, including `fastapi`, `starlette`, `httpx`, `psycopg2`, `numpy`, `requests`, `python-dotenv`, `langdetect`, `cryptography`, `pydantic`, and, **eagerly**, `fastembed`, `onnxruntime`, `tokenizers`, `huggingface_hub`, `PIL`. It does **not** load `mcp`, `uvicorn` or `sentry_sdk` | measured locally by importing `api` in the sandbox venv (2.9 s import) |
| Size locally: `onnxruntime` 41 MB, `numpy` 24 MB, `cryptography` 11 MB, `tokenizers` 8 MB; whole sandbox site-packages 261 MB (includes 42 MB `pgserver`, sandbox only) | `du` on the sandbox venv |
| Pins overlap with ViralTrack's lock almost completely (`httpx`, `psycopg2-binary`, `certifi`, `idna`, `h11`, `httpcore` identical) but **not entirely**: `anyio` 4.16.0 (ViralTrack) against 4.15.1 (upstream) | both lock files |
| Local runtime of the three D1 files with the upstream interpreter on Windows: 125 s for 123 tests (one subprocess of about 1 s per upstream call) | D1 report |
| The runner already blocks `requests` and removes `YOUTUBE_API_KEY`, and the tests assert zero attempts | `tests/support/upstream_runner.py`, `tests/support/upstream.py` |

## 3. Options

| | 1. Extend the existing job | 2. Dedicated job | 3. Separate scheduled job |
|---|---|---|---|
| How | install the upstream requirements into the same environment | a second job, own virtualenv, same triggers as `viraltrack` | a new job on `schedule` / `workflow_dispatch` only |
| Dependency conflict | **Yes**: `anyio` 4.16.0 vs 4.15.1; a single environment can satisfy only one and `pip check` in the install step would be at risk | none (separate environment) | none |
| Effect on the fast job | slower by the install of about 86 packages, and every push pays it | none (runs in parallel) | none |
| Detects a regression | on every push and pull request | on every push and pull request | at most a week later |
| Lockfile discipline | mixes two pin sets | keeps ViralTrack's lock-compile check intact | same as 2 |
| Cost | highest per run | one extra runner per run | lowest |

**Recommendation (PROPOSED): Option 2, a dedicated job.** It is the only option that keeps the fast job and its lock check
unchanged, avoids the `anyio` conflict, and still runs on every pull request. Option 3 would let a D2 or D3 adapter
change merge without the root-cause regression test ever running, which defeats the purpose of D1.

## 4. Proposed job (not applied)

```yaml
  discovery-offline:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: read
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env: { POSTGRES_USER: vt, POSTGRES_PASSWORD: vt, POSTGRES_DB: vt }
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U vt" --health-interval 5s
          --health-timeout 5s --health-retries 10
    steps:
      - uses: actions/checkout@v4
        with: { submodules: true }
      - name: Check the foundation submodule is the pinned commit
        run: test "$(git -C upstream/youtube-niche-finder rev-parse --short=7 HEAD)" = "d872014"
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: |
            requirements-dev.lock
            upstream/youtube-niche-finder/backend/requirements.txt
      # ViralTrack's own environment (pytest and the package) ...
      - run: |
          python -m venv /tmp/vt && /tmp/vt/bin/pip install -r requirements-dev.lock
          /tmp/vt/bin/pip install --no-deps -e .
      # ... and a separate upstream environment: only what `api` imports, at the versions the
      # foundation pins (the pinned file is used as a constraints file, so nothing else is pulled in).
      - run: |
          python -m venv /tmp/up
          /tmp/up/bin/pip install -c upstream/youtube-niche-finder/backend/requirements.txt \
            fastapi httpx psycopg2-binary numpy requests python-dotenv langdetect cryptography \
            fastembed pillow
      - name: Cut off the network (loopback only; the database service is on 127.0.0.1)
        run: |
          sudo iptables -A OUTPUT -o lo -j ACCEPT
          sudo iptables -A OUTPUT -j REJECT
      - name: Offline discovery tests (real upstream code, synthetic data)
        env:
          VT_TEST_DATABASE_URL: postgresql://vt:vt@localhost:5432/vt
          VT_TEST_REQUIRE_PGVECTOR: "1"
          VT_TEST_UPSTREAM_PYTHON: /tmp/up/bin/python
          HF_HUB_OFFLINE: "1"
        run: /tmp/vt/bin/pytest -q -p no:cacheprovider tests/test_discovery_d1_adapter.py tests/test_discovery_d1_upstream.py tests/test_discovery_d1_policy.py
```

Notes on the choices:

- **Only required dependencies (INFERRED, untested):** the constraints approach installs the ten direct packages at the foundation's
  pinned versions and their transitive needs only. It leaves out `mcp`, `uvicorn` and `sentry-sdk`, which the measured import
  does not load. It cannot leave out `fastembed` or `onnxruntime`, because the upstream imports them at start-up. If the
  constrained install turns out to miss a module, the fallback is the full pinned file. This has **not** been tried: installing
  was out of scope.
- **Reuse of the pinned submodule:** the upstream source is read from the checked-out submodule; the pin check runs first.
- **Existing jobs intact:** `viraltrack` and `upstream-suite` are not touched. The pytest in the new job reuses the D1 tests and
  fixtures; no test is duplicated.
- **Duplicate installation:** the two environments share only the pip download cache (`cache: pip`), so wheels common to both
  are downloaded once.

## 4.1 Security

- No secrets are referenced. `YOUTUBE_API_KEY` is never defined; the runner removes it anyway; pull requests from forks
  receive no secrets from GitHub.
- `permissions: contents: read`. No write token use.
- Network is cut after installation with a loopback-only `iptables` rule (hosted runners allow `sudo`). PostgreSQL is reached
  through the service container's port on `127.0.0.1`. `HF_HUB_OFFLINE=1` makes any accidental model download fail loudly.
  Defence in depth: the runner's `requests` guard and the zero-attempt assertion already exist.
- The rule is an INFERRED approach for GitHub-hosted runners; whether the service container remains reachable under the rule
  must be confirmed on the first run. If it is not, fall back to the runner guard alone and document that.
- The upstream interpreter runs only code from the pinned submodule; no download of code happens after the install step.

## 5. Expected runtime (INFERRED; no measurement exists)

| Step | Estimate | Basis |
|---|---|---|
| Install both environments | 1 to 2 minutes, less with the pip cache | about 86 wheels, `onnxruntime` 41 MB; no CI measurement exists |
| Tests | 1 to 2 minutes | 125 s locally on Windows; Linux process start is faster; 123 tests, about 1 s per upstream call |
| Total | about 3 to 4 minutes, in parallel with the 40-second `viraltrack` job | |

Measure on the first run and record it; a later optimisation is a session-scoped runner process that imports the
upstream once and answers many requests (an estimated saving of most of the per-call second).

## 6. Failure behaviour

- A failing test fails the job and blocks merging if the job is made a required check. Recommended: make it **required after
  two consecutive green runs on `main`**, so a first-run infrastructure issue does not block the owner.
- If the install step fails, the job fails visibly; the fast job is unaffected.
- The strict `xfail` tests do not fail the job while the defects exist. When a defect is fixed its `xfail` becomes an
  unexpected pass and fails the job until the marker is removed (intended).
- A change to the submodule pin fails the pin check first, so a moved foundation cannot be tested silently.

## 7. What was not done

No workflow was edited, no package installed, no run triggered; the new job is **BLOCKED on owner approval** to change
`.github/workflows/ci.yml` and to accept the extra CI dependency footprint.
