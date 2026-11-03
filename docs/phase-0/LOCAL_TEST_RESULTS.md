# Local Test Results

Date: 2026-11-03. Machine: Windows 11 Pro, Python 3.12.10, Node 24.14.1, uv 0.12.15.
All candidates were shallow-cloned into `D:\WORK_SPACE\_vt_phase0_sandbox\c\`, outside the
ViralTrack repo, and **nothing was merged into ViralTrack**. Package caches and temp files were
redirected to the sandbox. npm lifecycle scripts were disabled except for an explicit
`npm rebuild better-sqlite3`.

## Environment limits that affected testing

| Limit | Effect |
|---|---|
| **C: drive had 0 MB free** at the start of testing | **Docker Desktop could not start** ("Docker Desktop is unable to start"). No `docker compose` path was tested for any candidate: every Docker row is **NOT TESTED**. |
| **No YouTube Data API key** in the environment | No live YouTube API data was collected. YouTube apps were tested on their own fixtures and demo seeds. |
| **TikTok domains unreachable** (connections time out; likely a national block) | No live TikTok test was possible. A proxy around the block was deliberately not used. |
| Instagram scraping not attempted | Instagram terms bar automated collection, so instaloader was install-tested only. |
| No Postgres server | niche-finder needs Postgres 16 with pgvector. A throwaway `pgserver` wheel (PostgreSQL 16.2 + pgvector 0.6.2) ran on D:. CI uses `pgvector/pgvector:pg16`. |

## Results summary

| # | Candidate | Install | Build | Automated tests | App starts | Functional check | Docker | Live data | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1 | pandich93/youtube-niche-finder @ d872014 | PASS | n/a (static JS frontend) | **1,784 passed, 2 failed** (3h35m) | PASS (`uvicorn api:app`) | PASS on demo seed | NOT TESTED | NOT TESTED | **PASS WITH LIMITATIONS** |
| 2 | shkuratovdesigner/yuben-app @ cd57c04 | PASS | PASS (`tsc -b && vite build`) | **459 passed, 9 skipped, 0 failed** | PASS (API + SPA) | Health only | n/a (none) | NOT TESTED | **PASS WITH LIMITATIONS** |
| 3 | theograe/open-outlier @ 84e4e1f | PASS | PASS (all workspaces, Next.js build) | core **2 passed**; api **4 failed** (Windows EPERM on temp-dir cleanup) | PASS (with a placeholder key) | Discover endpoint returns an empty set without a key | n/a (none) | NOT TESTED | **PASS WITH LIMITATIONS** |
| 4 | Evil0ctal/Douyin_TikTok_Download_API @ 5aa0352 | PASS (`uv sync`) | n/a | unit+replay (CI scope) **3,553 passed, 55 failed** | NOT TESTED | — | NOT TESTED | NOT TESTED (TikTok unreachable; ToS) | **PASS WITH LIMITATIONS** (code); data route rejected |
| 5 | davidteather/TikTok-Api @ 9963059 | PASS | n/a | Offline subset: **4 passed, 14 failed, 3 skipped** (Playwright browsers not installed) | n/a | Import OK | NOT TESTED | NOT TESTED | **FAIL** (as tested); data route rejected |
| 6 | instaloader/instaloader @ 7acd1b6 | PASS | n/a | none run (repo has one integration test that needs the network) | n/a | Import OK (v4.16) | n/a | NOT TESTED | **NOT TESTED** (functionally) |
| 7 | cadenburleson/social-dash @ c1e99c5 | PASS | PASS (`vite build`) | none exist | NOT TESTED | — | NOT TESTED | NOT TESTED | **PASS WITH LIMITATIONS** (build only) |

## Details

### 1. youtube-niche-finder — PASS WITH LIMITATIONS

- Install: `uv venv` + `uv pip install -r backend/requirements.txt` (79 packages). The first test
  run failed at collection with `ZoneInfoNotFoundError`: Windows has no IANA tz database, and CI
  runs on Linux. Adding `tzdata` fixed it. That is an environment gap, not a code defect.
- Test command (mirrors CI): `NICHE_DATABASE_URL=<pgserver> NICHE_REQUIRE_PGVECTOR=1 pytest -q tests/`
- **Result: 1,784 passed, 2 failed, 4 warnings in 12,908 s.**
  - `test_pgvector.py::test_a_crowded_channel_does_not_hide_other_channels_from_the_index`. Likely
    pgvector 0.6.2 (pgserver) vs the newer pgvector in CI's `pgvector/pgvector:pg16`. Unconfirmed.
  - `test_rls_login.py::test_a_wrong_password_falls_back_to_set_role_with_a_warning`. pgserver's
    `postgres` superuser has no password, so the "wrong password" path cannot occur.
    Environment-specific; unconfirmed.
- The 3.5 h runtime comes from Windows and per-module schema creation. CI runs the same suite on
  Linux.
- **App start:** `tests/seed_demo.py` seeded schema `demo` (6 channels, 204 videos, 601 stats
  snapshots, two snapshots 24 h apart). Then `uvicorn api:app --port 3903` → dashboard `GET /`
  returned 200.
- **Functional checks (demo data, 0 quota used):**
  - `/api/health`: shows quota buckets "search_calls_left_today: 100" and "units_left_today: 10000",
    which matches Google's 2026 quota model.
  - `/api/viral?period=7d`: outlier funnel (subs ≤ 10k → views ≥ 10k → views/sub ≥ 1.0) returned
    6 matches.
  - `/api/outlier-channels`: median-baseline multipliers (e.g. 78.09× for a 15k-sub Shorts channel).
  - `/api/keywords`: momentum, outlier lift and a trend score per n-gram.
  - `/api/channels/{id}/velocity`: per-video `vphLifetime`, `vph24h`, `viewsGained24h`,
    `acceleration`, `trend` (cooling/steady).
  - `/api/freshness`: `staleDays: 25`, `deletes: false` (see the retention finding in the deep audit).
  - `/api/niches/ranking` returned a payload with an unpaired UTF-16 surrogate, which my client
    could not print. The server responded; the root cause was not investigated (possibly a Russian
    or emoji string in the demo seed).
- **Not tested:** Docker compose stack, worker loop against the real API, Chrome extension, MCP
  server, Telegram/e-mail alerts, multi-user sign-up.

### 2. yuben-app — PASS WITH LIMITATIONS

- Backend: `pip install -r requirements.txt` + pytest → **459 passed, 9 skipped in 36 s**.
- Frontend: `npm ci` + `npm run build` → PASS. The package defines no `test` script (only `lint`
  with oxlint).
- Run: `YUBEN_SERVE_SPA=1 uvicorn app.main:app` → `/api/health` returned
  `{"status":"ok","service":"yuben-backend"}`, and `/` (SPA) returned 200.
- Not tested: an actual research run (needs a YouTube key plus an LLM key).

### 3. open-outlier — PASS WITH LIMITATIONS

- `npm install` (scripts disabled) + `npm rebuild better-sqlite3` + `npm run build` → all
  workspaces built (core, storage, sdk, api, cli, mcp, web/Next.js).
- `npm test` **before** a build fails, because the API tests import the built `@openoutlier/storage`.
  Upstream does not document this ordering. After the build: core **2/2 passed**; api **4/4 failed**
  with `EPERM … openoutlier-app-test-*` while deleting the temp directory. SQLite keeps the file
  open on Windows. Not reproduced on Linux.
- The API refuses to start without `YOUTUBE_API_KEY` (`Missing required environment variable`).
  With a placeholder key it started on :3901, and `/api/discover/outliers?q=fitness` returned
  `{"total":0,…}`, as expected without real data.

### 4. Douyin_TikTok_Download_API — PASS WITH LIMITATIONS (code quality only)

- `uv sync --all-extras` → OK. 4,393 tests collected.
- Running the whole tree marks contract tests as skipped (they need `DTK_CONTRACT_BASE_URL` and a
  live deployment). CI runs `tests/unit tests/replay` with `DTK_SECRET_KEY`; doing the same here gave
  **3,553 passed, 55 failed in 28 s**. The failures traced (`test_worker_ops_backup.py`) hit
  `AttributeError: module 'os' has no attribute 'fchmod'`, a POSIX-only call. The project targets
  Linux and Docker.
- Integration tests need TimescaleDB plus Redis services and were not run.
- Source check: `/{platform}/trending` supports `douyin` and `bilibili`; **TikTok answers
  `UNSUPPORTED_CONTENT`**.

### 5. TikTok-Api — FAIL as tested

- `pip install .` OK; `import TikTokApi` OK.
- The offline-capable tests (`test_proxy_provider`, `test_session_recovery`,
  `test_custom_launchers`) gave 4 passed and 14 failed, because Playwright's Chromium was not
  downloaded. It was not installed, since every functional path then needs a live tiktok.com
  session (`ms_token`), and tiktok.com is unreachable from this machine.
- Every remaining test (`test_trending`, `test_hashtag`, …) needs live TikTok and an `ms_token`.

### 6. instaloader — NOT TESTED (functionally)

- Installed and imported (4.16). No collection was run: Instagram's terms bar automated
  collection, and `get_explore_posts` and hashtag feeds need a logged-in account
  (`@_requires_login`).

### 7. social-dash — build only

- `npm ci && npm run build` PASS (warning: chunk > 500 kB). There are no tests. It would need
  RapidAPI keys to show data.

## Public endpoint probes (no credentials)

| Probe | Result |
|---|---|
| `https://www.youtube.com/oembed?url=…dQw4w9WgXcQ&format=json` | 200, with title, author and thumbnail |
| `https://www.googleapis.com/youtube/v3/videos?chart=mostPopular` (no key) | 403 |
| `https://www.youtube.com/feeds/videos.xml?channel_id=…` (two valid channels, with and without a browser UA) | **404** |
| `https://www.tiktok.com`, `developers.tiktok.com`, `ads.tiktok.com` | Connection timeout (12 s) |
| `https://www.instagram.com` | 200 |

## Cleanup

All four local servers (ports 3901–3904) and the pgserver Postgres were stopped. Sandbox
location: `D:\WORK_SPACE\_vt_phase0_sandbox\` (clones, virtualenvs, node_modules, caches, logs; D: free space fell from ~15.3 GB to ~12.9 GB during Phase 0). It can
be deleted at any time; it is not part of the ViralTrack repo.
