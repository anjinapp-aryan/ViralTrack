# ViralTrack web (frontend phase 1)

A local-development web UI for ViralTrack. It shows the Discover page and a Data sources page, and it reads data only from the local ViralTrack API (D5). It has no accounts and no sign-in, and **it must not be exposed on a network**. Both servers bind to `127.0.0.1`.

Adapted from [satnaing/shadcn-admin](https://github.com/satnaing/shadcn-admin) at commit `e16c87f213a5ba5e45964e9b67c792105ec74d26` (MIT, © 2024 Sat Naing; the licence is kept in [LICENSE](LICENSE)). The changes are listed in `docs/phase-4-7/FRONTEND_PHASE_1_REPORT.md`.

## Stack

React 19, Vite 8, TypeScript, TanStack Router and Query, shadcn/ui on Radix, Tailwind CSS 4, `tw-animate-css`, Lucide icons and self-hosted Inter. API types are generated from `../docs/api/openapi-v1.json` by `openapi-typescript`, and requests use `openapi-fetch`. Tests run with Vitest in Chromium (Playwright) and use axe-core for accessibility.

## Run the whole stack on Windows (demo data, no YouTube quota)

Three terminals, from the repository root `D:\WORK_SPACE\ViralTrack`. These are the commands used to verify phase 1; the sandbox paths are the ones on this machine (see `docs/phase-4-7/D5_DASHBOARD_RECONNAISSANCE.md`).

**1. Foundation in demo mode (port 8081, no API key)**

```powershell
$sb = "D:\WORK_SPACE\_vt_phase0_sandbox"
$pg = "$sb\venv\ynf\Lib\site-packages\pgserver\pginstall\bin"
Start-Process -WindowStyle Hidden "$pg\pg_ctl.exe" -ArgumentList 'start','-D',"$sb\pgdata",'-o','"-p 57790 -c listen_addresses=127.0.0.1"','-l',"$sb\logs\pg_demo.log"
$env:NICHE_DATABASE_URL = (Get-Content "$sb\tmp\demo.uri")
$env:YOUTUBE_API_KEY = ""; $env:NICHE_REQUIRE_PGVECTOR = "1"; $env:LLM_PROVIDER = "none"
$env:NF_DEFAULT_LOCALE = "en"; $env:PYTHONUTF8 = "1"; $env:PYTHONDONTWRITEBYTECODE = "1"
Set-Location D:\WORK_SPACE\ViralTrack\upstream\youtube-niche-finder\backend
& "$sb\venv\ynf\Scripts\python.exe" -m uvicorn api:app --host 127.0.0.1 --port 8081
```

`YOUTUBE_API_KEY` is set to empty on purpose, so no collection is possible.

**2. ViralTrack API (port 8000)**

```powershell
Set-Location D:\WORK_SPACE\ViralTrack
.\.venv\Scripts\Activate.ps1                 # a venv with: python -m pip install -e ".[api]"
$env:VT_YOUTUBE_FOUNDATION_URL = "http://127.0.0.1:8081"
$env:VT_YOUTUBE_DATA_ORIGIN = "demo"          # labels the data DEMO in every response
python -m viraltrack.api
```

**3. Web UI (port 5173)**

```powershell
Set-Location D:\WORK_SPACE\ViralTrack\web
corepack enable                               # once; or: npm install -g pnpm@10
pnpm install --frozen-lockfile                # once
pnpm dev
```

Open **http://127.0.0.1:5173** in Chrome. The UI calls `/api/v1/...` on its own origin, and Vite forwards those calls to `http://127.0.0.1:8000`. To use another loopback port, set `VT_API_PROXY_TARGET`. A non-loopback target is refused.

## Scripts

| Command                                         | What it does                                                                   |
| ----------------------------------------------- | ------------------------------------------------------------------------------ |
| `pnpm dev`                                      | development server on 127.0.0.1:5173                                           |
| `pnpm build` / `pnpm preview`                   | production build and a local preview on 127.0.0.1:4173 (same API proxy)        |
| `pnpm typecheck`                                | `tsc -b`                                                                       |
| `pnpm lint` / `pnpm format:check` / `pnpm knip` | ESLint, Prettier, unused code                                                  |
| `pnpm test`                                     | Vitest in headless Chromium (run `pnpm exec playwright install chromium` once) |
| `pnpm api:types`                                | regenerate `src/lib/api/schema.d.ts` from `../docs/api/openapi-v1.json`        |

Set `VITE_DEVTOOLS=true` to show the TanStack Router and Query devtools in development.

## Rules this UI keeps

- Data comes only from the ViralTrack API. The foundation and YouTube are never called from the browser. Nothing collects data or spends quota.
- Only the API's approved sorts are offered (Most views, Newest), and the options are read from `/api/v1/capabilities`.
- Derived values and scores are not displayed. Hidden or missing values are written out ("Hidden or not reported") and never shown as 0.
- Thumbnails are placeholders. No platform image is requested until the use of platform images is reviewed.
- Nothing is retried automatically; a failed request shows a Retry button.
- There is no authentication of any kind, real or pretend.
