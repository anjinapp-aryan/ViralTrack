# Target UI architecture (proposal)

Date: 2026-11-07. Requires owner authorization of D5 before any implementation.

## 1. Current and target

```text
CURRENT
  browser ──► foundation FastAPI (api:app) ──► foundation frontend/ (vanilla JS, internal-only)
                     │
  ViralTrack Python package (provider, metric policy) — used only from Python, no HTTP, no UI

TARGET
  browser ──► ViralTrack web app (React + Vite, static files)
                 │  HTTP, JSON, OpenAPI
                 ▼
             ViralTrack API (FastAPI, D5) ──► PlatformProvider ──► foundation HTTP API ──► PostgreSQL
                 │  MetricPolicy + Provenance applied here, before any response
  foundation dashboard stays as an internal operator tool, unchanged
```

The policy boundary stays in Python. The web app never receives a restricted value, so it cannot leak one, and it holds no metric business logic beyond formatting.

## 2. Frontend layout

```text
web/                      (new top-level folder, own package.json and lockfile)
  src/app/                routes: overview, discover, niches, creators, settings (React Router or TanStack Router)
  src/components/ui/      shadcn/ui copies (MIT notices kept)
  src/components/vt/      VideoCard, QuickView, MetricValue, FreshnessChip, PolicySort, FilterBar
  src/lib/api/            typed client generated from the ViralTrack OpenAPI schema (openapi-typescript, MIT; audit at install)
  src/lib/query/          TanStack Query hooks; retries off for anything that could cost quota
  src/viz/                Recharts wrappers; lazy NicheMap (sigma.js); lazy HeroField (R3F)
  src/theme/              Tailwind v4 tokens (VIRALTRACK_DESIGN_SYSTEM.md)
  tests/                  vitest unit, Playwright e2e, axe checks, screenshot baselines
```

## 3. Component reuse map

| Requirement | Project | Strategy |
|---|---|---|
| Navigation, sidebar, tabs | shadcn/ui Sidebar, Tabs (Radix) | REUSE |
| Search and command palette | shadcn Command | REUSE |
| Filters | shadcn Select, Popover, ToggleGroup | REUSE |
| Data table | TanStack Table + shadcn Table | REUSE |
| Charts | Recharts via shadcn Chart | REUSE |
| Niche map | sigma.js + graphology | REUSE (ADAPT layout and styling) |
| Hero field | three.js + react-three-fiber + drei | ADAPT (one small scene) |
| Animations | Motion | REUSE |
| Counters, subtle borders | Magic UI NumberTicker, BorderBeam (MIT copy) | ADAPT |
| Icons | Lucide | REUSE |
| Skeletons, toasts, dialogs | shadcn Skeleton, Sonner (via shadcn; audit at install), Dialog/Sheet | REUSE |
| Server state | TanStack Query | REUSE |
| Video card | shadcn Card + AspectRatio | ADAPT |
| Metric display with RAW/DERIVED and missing-value wording | none exists | BUILD (small) |
| Policy-aware sort options | none exists | BUILD (small; options come from the API) |
| API and metric policy | ViralTrack Python | already built; D5 adds HTTP |

## 4. Data contract per component

| Component | Endpoint (proposed D5) | Fields | Missing data | Restricted |
|---|---|---|---|---|
| VideoCard / QuickView | `GET /v1/content/discover`, `GET /v1/content/search` | `content_id`, `title`, `thumbnail_url`, `duration_seconds`, `published_at`, `creator.name`, `creator.followers`, `metrics[views, likes, comments]`, `derived[engagement_rate, views_per_hour_lifetime]`, `provenance`, `origin` | `null` shown as "hidden" or "not available" | never present in the response |
| FreshnessChip | same, `retrieved_at` and `provenance.collected_at` | | `collected_at` is `None` today: show retrieval time and say observation time is unknown | — |
| PolicySort | `GET /v1/capabilities` | sort names, filter bounds | — | — |
| Overview tiles and bars | `GET /v1/content/summary` (aggregates of allowed RAW values) | counts, sums | omitted when no data | — |
| Niche list and map | `GET /v1/niches` | label, video count, shared tags | — | no semantic similarity |
| DEMO badge | `origin` on every item | | | |

Loading: skeletons. Errors: provider errors map to readable states (foundation unavailable, quota, not found). Demo data: the foundation seed plus `VT_YOUTUBE_DATA_ORIGIN=demo`.

## 5. Theme, animation, 3D and chart architecture

Theme: CSS variables from Tailwind tokens, `class="dark"` toggle stored per viewer, `prefers-color-scheme` default. Animation: Motion with `MotionConfig reducedMotion="user"`. 3D and graph: separate lazy chunks, WebGL detection, static fallbacks. Charts: Recharts, colours from tokens, every chart has a text alternative (table toggle).

## 6. Testing strategy

Unit (vitest): `MetricValue` never renders 0 for `null`; sort control renders only API-provided options. Contract: a test that walks every response schema and fails on a key outside `MetricPolicy` (Python side, D5). e2e (Playwright): keyboard-only flows, Escape closes dialogs, reduced motion disables animation. Accessibility: axe on every route, zero serious violations. Visual regression: Playwright screenshots in light and dark at three widths. Performance: Lighthouse CI budget on the built app (measure first, then set limits).
