# Dependency Boundaries

```text
viraltrack/domain            imports: stdlib only
viraltrack/providers/base    imports: domain
viraltrack/providers/youtube imports: domain, base, httpx  -- the ONLY code that knows niche-finder exists
viraltrack/retention         imports: config, psycopg2     -- the ONLY code that knows niche-finder's tables
viraltrack/config            imports: domain.errors
```

ViralTrack code never imports a module from `upstream/`. The single exception is the test fixture
`tests/conftest.py::pg_schema`, which reads upstream's DDL so the retention tests run against the real schema.

## Contracts with the foundation and how each is guarded

| Contract | Used by | Guard |
|---|---|---|
| HTTP API: `/api/viral`, `/api/search`, `/api/channels/{id}`, `/api/channels/{id}/history` | YouTube adapter | Upstream generates `docs/http-api.md` from code and checks it in CI. ViralTrack tests use recorded responses and a live smoke test (`-m live_foundation`) |
| `X-NF-Locale: en` request header | YouTube adapter | Test. Without it, upstream hints and errors come back in Russian (`NF_DEFAULT_LOCALE=ru`) |
| Bearer personal token (multi-user mode) | YouTube adapter | Test |
| Postgres tables and columns | Retention job | `tests/test_retention_policy.py` fails on an unclassified upstream table. `tests/test_retention_job.py` runs on upstream's own DDL. Missing tables make the job fail closed (`SchemaNotFound`) |
| Submodule pin `d872014` | Everything | CI step checks the pin |

## Upgrading the foundation

1. `git -C upstream/youtube-niche-finder fetch && git -C upstream/youtube-niche-finder checkout <new>`
2. Update the pin check in `.github/workflows/ci.yml`.
3. Run `pytest` with Postgres and `-m live_foundation` against the new `web`, plus the weekly upstream suite.
4. Classify any new table the policy test reports.

## Replacing the foundation

Write a new adapter in `viraltrack/providers/youtube/` behind the same `PlatformProvider` interface, and a
retention policy for its storage. Nothing in `viraltrack/domain` changes.
