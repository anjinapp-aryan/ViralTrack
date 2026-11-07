# Current frontend architecture

Date: 2026-11-07. Read from source at `81a4214`, foundation submodule `d872014`. Nothing was changed.

## 1. The finding that shapes everything else

**ViralTrack has no frontend.** The repository contains a Python package (`viraltrack/domain`, `providers`, `retention`, `config.py`), tests and docs. There is no HTML, JavaScript, CSS, `package.json` or lockfile outside the submodule. The dashboard the owner inspected at `http://127.0.0.1:8081` is the **foundation's** dashboard (`upstream/youtube-niche-finder/frontend/`), served by the foundation's FastAPI app.

Consequences:

1. The foundation UI cannot be restyled in place: the submodule is never edited (CLAUDE.md).
2. The foundation UI shows restricted metrics on almost every screen (section 5), and it is internal-only by policy.
3. A ViralTrack UI is therefore a **new application** on top of a ViralTrack API. That API is stage D5, which is deferred. No UI implementation can start before D5 is authorized.

## 2. Foundation dashboard stack (verified in source)

| Aspect | What it is | Evidence |
|---|---|---|
| Framework | None. Plain ES modules (`<script type="module" src="app.js">`) | `frontend/index.html` line 107; `frontend/README.md`: "No build step: plain ES modules, no npm, no node_modules" |
| Build | None | no `package.json` anywhere in `frontend/` |
| Routing | Hash router, table of 30+ routes to screen functions | `frontend/router.js` |
| Rendering | Template strings assigned to `innerHTML` (109 uses in `ui.js` and `screens/*.js`), escaped by an `esc()` helper | `frontend/ui.js` |
| Styling | One hand-written `styles.css` (442 lines) with CSS custom properties, dark and light themes, one breakpoint (`max-width: 900px`) | `frontend/styles.css` |
| Components | Hand-written helpers in `ui.js` (920 lines): `videoCard`, `table`, `tile`, `barList`, `notice`, `toast`, tooltip | `frontend/ui.js` export list |
| Charts | Hand-written SVG: `lineChart`, `trajectoryChart`, `scatterChart` | `frontend/ui.js` lines 417 to 584 |
| Icons | Inline SVG `<symbol>` sprite in `index.html` | `frontend/index.html` |
| Fonts | `system-ui, -apple-system, "Segoe UI", sans-serif` | `styles.css` line 30 |
| Animation | None beyond CSS defaults | no animation library; no keyframes of note |
| i18n | Own dictionary system, Russian and English (`frontend/i18n/`) | `frontend/i18n.js` |
| Accessibility | Six `aria-`/`role` occurrences in CSS, `ui.js` and `index.html` together; no reduced-motion rules | grep count |
| Tests | Python static checks and a browser smoke test (`frontend/tests/test_smoke.py`, `make frontend-test`) | `Makefile` line 136 |
| Size | About 98 KB for shell, CSS and shared JS, plus about 4,300 lines of screen code | `wc` |
| Licence | MIT, Copyright (c) 2026 Fozil Umarov | `upstream/youtube-niche-finder/LICENSE` |

API client: `api()` in `frontend/ui.js` calls the foundation's own `/api/*` routes; contracts are documented in `upstream/youtube-niche-finder/docs/http-api.md`.

Startup: FastAPI `api:app` serves `/api/*` and the static `frontend/` folder (one process). Docker compose `web` service, or `uvicorn api:app` locally. The local run on synthetic data is documented in `docs/phase-4-7/D5_DASHBOARD_RECONNAISSANCE.md`.

## 3. ViralTrack's own UI-relevant code

| Asset | Where | UI relevance |
|---|---|---|
| Normalized model | `viraltrack/domain/models.py`: `Content` (title, `thumbnail_url`, `published_at`, `duration_seconds`, category, `metrics` RAW, `derived` DERIVED, `retrieved_at`), `Creator` (name, handle, followers), `ContentPage` (items, total, notes, funnel) | The only data a ViralTrack UI may show |
| Metric policy | `viraltrack/providers/youtube/metric_policy.py`: 4 ALLOWED, 10 RESTRICTED, 2 INTERNAL_ONLY; `Content` rejects non-ALLOWED values | Enforced before data reaches any UI |
| Provenance | `Provenance`: provider, source, collected_at, kind, origin (real / demo / test) | Source and freshness labels |
| Sorts | `views`, `published_at` only; others refused with a reason | The only sort controls a UI may offer |
| Filters | period, niche, region, category, follower cap (max 1,000,000), min views, `short_form` (duration ≤ 180 s) | Filter controls |
| HTTP API | **none** (D5) | Blocker |

## 4. Distinguishing what exists

| Category | Items |
|---|---|
| Existing upstream functionality | Discovery screens, search, categories, keywords, tags, niches and niche map, channel tracker, alerts, digest, history, packaging, ideas, transcripts, scores page, admin, MCP |
| Existing ViralTrack functionality | Provider, normalized model, metric policy, provenance, retention, D7 guard |
| Missing integration | A ViralTrack HTTP API; any ViralTrack UI; watchlist and history mapping (D6) |
| Must remain restricted | Viral score, outlier scores and labels, views per subscriber (VSR), RPM ranges, projections, Shorts label, semantic score, 24-hour velocity and acceleration (until snapshot recency is reliable) |
| Genuinely new | RAW/DERIVED labelling in the UI, provenance and freshness display, policy-safe sort and filter controls, DEMO labelling |

## 5. Restricted values visible in the current dashboard (from the owner's screenshots)

`#/viral`: VPH badge (24-hour velocity, held back), multiplier badge such as `22.8x` (outlier score, RESTRICTED), `VSR` (views per subscriber, RESTRICTED), "mega outlier" / "viral" / "strong outlier" labels (outlier band, RESTRICTED), `~$4.2–17 RPM` (estimated RPM, RESTRICTED, third-party data), red `0.67` arrows (a derived trend value). `#/categories`: "Median multiplier" (outlier), "Niche RPM" (RESTRICTED), "Growth" and "Share shift" (period comparisons; not classified for ViralTrack). Raw views, video and channel counts on these screens are allowed.
