# ViralTrack

Viral-content discovery and trend intelligence for creators.

ViralTrack is built on existing open source instead of from scratch. Its YouTube engine is
[youtube-niche-finder](https://github.com/pandich93/youtube-niche-finder) (MIT), included unmodified as a
pinned submodule. This repository adds a platform-neutral boundary around it:

- `viraltrack/domain`: a platform-neutral content model in which every metric carries provenance
  (raw platform data vs derived values)
- `viraltrack/providers`: a capability-based provider interface and the YouTube adapter
- `viraltrack/retention`: enforcement of YouTube's data-storage rules on the foundation's database

Instagram and TikTok are not integrated: Phase 0 found no legitimate discovery source for them.

- Setup: [docs/phase-1/LOCAL_SETUP.md](docs/phase-1/LOCAL_SETUP.md)
- Architecture: [docs/phase-1/ARCHITECTURE.md](docs/phase-1/ARCHITECTURE.md)
- Research and decisions: [docs/phase-0](docs/phase-0), [docs/phase-1](docs/phase-1)
- Third-party licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

## Development and tests

Python 3.10 or newer. Use a virtual environment: a bare `pytest` on a system Python fails at collection because
`psycopg2` is not installed there.

Windows PowerShell:

```powershell
git clone --recurse-submodules https://github.com/anjinapp-aryan/ViralTrack.git
cd ViralTrack
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if scripts are blocked: Set-ExecutionPolicy -Scope Process RemoteSigned
python -m pip install -e ".[dev]"     # installs the package, pytest and ruff (pinned in pyproject.toml)
ruff check .
pytest
```

Linux and macOS: the same, with `python3 -m venv .venv` and `source .venv/bin/activate`.

`pytest` alone runs the offline unit tests. It sends no network request and spends no YouTube quota. Some tests
need services this repository does not start, and they **skip** (they do not pass) when the service is absent:

| Variable | Needed for | Skipped without it (count in the current suite) |
|---|---|---|
| `VT_TEST_DATABASE_URL` | Tests against a real PostgreSQL 16 with pgvector and the foundation's schema: retention, database checks, and the discovery and collection tests that run the real foundation code. Use a throwaway database; the tests write to it. | about 132 |
| `VT_TEST_UPSTREAM_PYTHON` | Path of a Python that has the foundation's requirements installed, used by the tests that run the real foundation code (with the database above) | part of the group above |
| `VT_TEST_FOUNDATION_URL` | `pytest -m live_foundation`: a smoke test against a running foundation API (read-only) | 2 |

A further 3 tests are POSIX-only and skip on Windows. The skip count depends on the machine; on a plain Windows
checkout it is 137. A skipped test has not been run, so a green local result without the variables above does not
cover them. The hosted CI sets the database and upstream variables and fails if the expected tests are skipped.
See [docs/phase-1/LOCAL_SETUP.md](docs/phase-1/LOCAL_SETUP.md) and [docs/phase-1/TEST_RESULTS.md](docs/phase-1/TEST_RESULTS.md).
