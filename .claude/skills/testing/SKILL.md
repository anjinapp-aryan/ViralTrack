---
name: testing
description: Plan, write and run tests for ViralTrack changes and report exact results. Use whenever code changes, before declaring a task done, and when asked to validate the foundation.
---

# testing

## 1. Use what exists

- Framework: **pytest**. Config lives in `pyproject.toml` (`testpaths = tests`, markers `postgres`,
  `live_foundation`).
- Utilities: `tests/conftest.py`:
  - `load_fixture()` loads recorded responses.
  - the `pg_schema` fixture gives a fresh schema built from the **real upstream DDL**.
- Patterns: `httpx.MockTransport` with the `Recorder` in `tests/test_youtube_provider.py`.
- Lint: `ruff check .`

## 2. Write focused tests

- Every test must fail if the behaviour it covers breaks. Never add a test only to raise the count.
- Cover the change, its error paths and its boundaries (unsupported capabilities, provenance, retention,
  read-only providers).
- Fixtures must be synthetic or licensed. Never commit real platform data or secrets.
- Prefer unit tests, plus integration tests (Postgres), contract tests (upstream schema and API), and a live
  smoke test where it adds signal.

## 3. Run

| Scope | Command |
|---|---|
| Fast | `pytest` (Postgres and live tests skip) |
| Retention on real DDL | `VT_TEST_DATABASE_URL=postgresql://… pytest` |
| Live foundation | `VT_TEST_FOUNDATION_URL=http://localhost:8080 pytest -m live_foundation` |
| Upstream suite (when the submodule pin changes) | Linux Docker with `pgvector/pgvector:pg16`, as in `docs/phase-1/TEST_RESULTS.md`. Not on Windows |
| CI-equivalent | the steps in `.github/workflows/ci.yml` |

Run the relevant tests first, then the broader suite before finishing.

## 4. Report exactly

```text
Command:
Passed:
Failed:
Skipped:   (with reasons)
Duration:
```

Quote failures with their shortest decisive line. Never describe skipped or unrun tests as passing.
Never delete or weaken a failing test to make it pass without explicit approval.
