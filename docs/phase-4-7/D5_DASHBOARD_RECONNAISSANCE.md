# D5 reconnaissance: the foundation's existing dashboard

Date: 2026-11-07. Read-only inspection plus a local run on synthetic data. No YouTube call, no quota, no production code, no submodule change, no commit. The numbers and screens described here belong to the foundation (`upstream/youtube-niche-finder`, pinned `d872014`, MIT) and are **internal-only** under the ViralTrack metric policy. This is not a recommendation to show any of them to ViralTrack users.

## 1. Repository state

`main` equals `origin/main` at `81a4214` (the two earlier commits are pushed), working tree clean, submodule `d872014`.

## 2. Architecture

* Frontend (`frontend/`): no build step, no npm, no framework. Plain ES modules and one `styles.css` with dark and light themes. `index.html` is the shell (sidebar, header with global filters). `router.js` is a hash router (`#/viral`, `#/find`, ...) mapping to one file per screen in `frontend/screens/` (about 4,300 lines in total). Interface strings are in `frontend/i18n/` (Russian and English).
* Backend (`backend/`): FastAPI app `api:app` (served by uvicorn) that exposes `/api/*` **and** serves the static `frontend/` folder, so the dashboard is one process. Business logic is in `backend/application/`, SQL in `backend/infrastructure/postgres/`, pure rules in `backend/domain/`. A separate `worker.py` collects and snapshots on a schedule; an MCP server (`server.py`) shares the same use cases.
* Storage: PostgreSQL 16 with the pgvector extension (embeddings). Single-user mode by default; multi-user accounts exist behind `NF_MULTI_USER=1`.
* Reuse note: it is FastAPI plus plain JavaScript. No second frontend stack would be needed to extend it; replacing it would be a rebuild of existing, working functionality.

## 3. Screens (from `router.js` and the sidebar)

| Area | Screens (route) | What it does |
|---|---|---|
| Discovery | Overview (`overview`), Viral videos (`viral`), Find / outlier search (`find`), Categories, Keywords, Top tags, Language gaps, Niches and niche detail, Niche map (`clusters`), Compare | Filtered lists over the local corpus with period, niche, region, category, subscriber, views, Shorts filters and several sorts |
| Keyword search | Find (`find`), Ideas check (`ideas`) | Text query with length, RPM, Shorts and YPP filters; idea verdicts |
| Scores and explanations | Help / scores (`/api/scores`: what every number is, formula, inputs, minimum sample); video "why it took off" (LLM, off without a provider); outlier traits, hooks, title patterns | Explanations of the foundation's own scores |
| Watchlist | Tracker (`tracker`), channel pages (`channel`), saved items (`saved`) | Add and remove tracked channels, channel analytics and growth |
| Alerts | Alerts (`alerts`), digest, notification settings | Topic watches, alert history, email or other notifications |
| History | Channel history (`/api/channels/{id}/history`), video trajectory, packaging (title and thumbnail changes), calendar | Snapshots over time |
| Data and operations | Data (collect a channel or niche), MCP connection, Own channels, Plan, Admin, Profile | Collection (spends quota with a key), integrations, accounts |

## 4. Local run result (synthetic data, no key)

* Database: a new, empty database `vt_demo` on the sandbox PostgreSQL (pgserver, port 57790, pgvector 0.6.2), separate from every earlier test database.
* Demo data: `backend/tests/seed_demo.py` (shipped upstream; `make seed` runs it) created 6 channels and 204 videos plus snapshots (601 video and 18 channel snapshots, 2 tracked channels, 1 niche "Demo", 2 title changes). It is documented as "synthetic-but-realistic data so every section can be exercised without spending YouTube quota".
* The API was started with `YOUTUBE_API_KEY` set to empty. Verified: `/api/health` reports `hasApiKey: false`, `units_today: 0`, `search_calls_today: 0`; `POST /api/collect/niche` answers "YOUTUBE_API_KEY is not set" (so no live collection is possible); `/api/viral`, `/api/search?query=ai`, `/api/channels/tracked`, `/api/scores`, `/api/niches`, `/api/freshness` and `/` all answered 200 with demo content; `/api/channels/{id}/history` returned two timestamped points (`t`, subscribers, videos, views).
* Running now at **http://127.0.0.1:8081** (background process of this session; stop it by closing the session or the `uvicorn` process; the database server keeps running until stopped).
* Not checked: the screens in a real browser (this session has no browser); the Docker path (Docker Desktop is not running here and drive C: has about 7 GB free, which is why the sandbox PostgreSQL was used); the worker (needs a key).

## 5. Startup commands (Windows PowerShell)

### A. What was run here (verified; sandbox from earlier phases)

```powershell
$sb = "D:\WORK_SPACE\_vt_phase0_sandbox"
$pg = "$sb\venv\ynf\Lib\site-packages\pgserver\pginstall\bin"
Start-Process -WindowStyle Hidden "$pg\pg_ctl.exe" -ArgumentList 'start','-D',"$sb\pgdata",'-o','"-p 57790 -c listen_addresses=127.0.0.1"','-l',"$sb\logs\pg_demo.log"
# once: create the demo database and extension (password is in $sb\pg.uri)
& "$pg\createdb.exe" -h 127.0.0.1 -p 57790 -U postgres vt_demo
& "$pg\psql.exe" -h 127.0.0.1 -p 57790 -U postgres -d vt_demo -c "CREATE EXTENSION IF NOT EXISTS vector"
$env:NICHE_DATABASE_URL = (Get-Content "$sb\tmp\demo.uri")
$env:YOUTUBE_API_KEY = ""; $env:NICHE_REQUIRE_PGVECTOR = "1"; $env:LLM_PROVIDER = "none"
$env:NF_DEFAULT_LOCALE = "en"; $env:PYTHONUTF8 = "1"; $env:PYTHONDONTWRITEBYTECODE = "1"
Set-Location D:\WORK_SPACE\ViralTrack\upstream\youtube-niche-finder\backend
& "$sb\venv\ynf\Scripts\python.exe" tests\seed_demo.py            # once
& "$sb\venv\ynf\Scripts\python.exe" -m uvicorn api:app --host 127.0.0.1 --port 8081
```

Setting `YOUTUBE_API_KEY` to empty matters: the repository's root `.env` holds a real key from an earlier phase, and this run must not use it. Stop with Ctrl+C, then `& "$pg\pg_ctl.exe" stop -m fast -D "$sb\pgdata"`.

### B. Documented upstream way (Docker; not run here)

```powershell
# start Docker Desktop first; free space on C: is needed for the images
cd D:\WORK_SPACE\ViralTrack\upstream\youtube-niche-finder
Copy-Item .env.example .env          # leave YOUTUBE_API_KEY empty; set NF_DEFAULT_LOCALE=en
docker compose build web
docker compose up -d postgres
docker run --rm --network niche-finder_default -e POSTGRES_HOST=postgres niche-finder:latest python tests/seed_demo.py
docker compose up -d web
start http://localhost:8080
```

(`.env` inside the submodule is git-ignored; do not commit it. Do not start `worker`: it collects and needs the key.)

## 6. Verification steps for the owner

1. Open http://127.0.0.1:8081 and wait for the Overview.
2. Open `#/viral` and `#/find`; try period, niche, region, subscriber and Shorts filters and each sort.
3. Open `#/tracker` (two tracked demo channels) and a channel page; look at the history chart.
4. Open `#/alerts`, `#/help` and the scores explanations.
5. Confirm the footer or Data screen shows no API key and zero units used.
6. Note every number you see that is in the restricted list below; those cannot reach ViralTrack users.

## 7. What can and cannot be exposed through ViralTrack

Policy: 4 metrics ALLOWED, 10 RESTRICTED, 2 INTERNAL_ONLY (`docs/phase-1/DERIVED_METRIC_POLICY.md`); the foundation's UI is internal-only.

| Dashboard capability | Exposable through ViralTrack | Reason |
|---|---|---|
| Video lists with raw views, likes, comments, publish date, duration, title, channel | Yes (already via `discover_content`/`search_content`) | RAW, with provenance |
| Filters: period, niche, region, category, subscriber cap (max 1,000,000), min views, duration filter `short_form` | Yes (already) | Approved |
| Sorts: views, published date | Yes | Approved; all others refused |
| Sorts and badges: viral score, outlier score, views per subscriber, age-adjusted outlier, RPM, projections, Shorts label | No | RESTRICTED |
| 24-hour velocity, acceleration | Not now | No reliable snapshot recency (D3-05) |
| Semantic ranking | No | INTERNAL_ONLY; relevance must not read as popularity |
| Scores page, "why it took off", hooks, title patterns, niche ranking, sponsors, policy signals | No (internal) | Derived or model-based; contain restricted inputs; LLM off by default |
| Watchlist (tracked channels) | Possible later (D6) | Needs retention design and a metric filter on what it shows |
| Alerts, digest, notifications | Not now | Not authorized; the foundation already has them |
| History / snapshots | Possible later (D6) | The history endpoint returns timestamped points (`t`); needs confirmation that `t` is the observation time on real data |
| Collection screens | Never from a UI | Spend quota; D7 harness governs any live call |

## 8. D5 integration gap report

1. **Policy filter at the display layer.** Every dashboard screen mixes allowed and restricted numbers. There is no existing switch to hide restricted fields; reusing the dashboard directly would expose them. The ViralTrack API must be the only public surface.
2. **No ViralTrack API yet.** `PlatformProvider` is a Python library; D5 would add a small FastAPI wrapper (the foundation's stack) and OpenAPI. Contract test with `schemathesis` (dev-only, MIT) that no response key is outside `MetricPolicy`.
3. **Provenance not shown.** The foundation UI does not display provider, source, collected time or RAW/DERIVED; ViralTrack's `Provenance` would be the new element.
4. **Demo labelling.** Seeded data is synthetic; `VT_YOUTUBE_DATA_ORIGIN=demo` must label it so a demo cannot be mistaken for real data.
5. **Authentication.** Single-user mode has none and is bound to 127.0.0.1; any shared use needs a decision (decision 3 in `OWNER_DECISIONS.md`). The foundation's multi-user mode exists but would still need the metric filter.
6. **Wording.** Titles such as "Viral", "Breakout", "Outlier" are used across the foundation UI; D4 counsel decisions are needed before any such word appears in ViralTrack.
7. **Localisation.** The foundation defaults to Russian unless `NF_DEFAULT_LOCALE=en`.
8. **Accessibility and performance** of the foundation UI were not tested.

## 9. Fresh reuse findings

* The existing dashboard is the reusable asset: FastAPI plus plain ES modules, no build chain, MIT.
* Recommended D5 options, smallest first: (1) no new UI; ViralTrack ships only a policy-filtered API and the owner keeps using the foundation dashboard internally; (2) add one read-only page served by the same ViralTrack API (htmx, 0BSD, or plain JavaScript, no framework); (3) fork or patch the foundation UI to hide restricted fields: **rejected**, it modifies the adopted submodule and breaks upgradability.
* No new open-source project is needed. The audit of BI and dashboard tools in `OPEN_SOURCE_REUSE_AUDIT.md` stands (Superset, Metabase, Grafana, Streamlit, Dash rejected).
