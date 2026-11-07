# UI implementation roadmap

Date: 2026-11-07. Estimates are working days for one engineer and are rough. Nothing here is authorized; every phase needs owner approval, and all of them depend on D5.

| Phase | Content | Depends on | Estimate |
|---|---|---|---|
| UI 0 · Research and audit | This package | — | done |
| UI 0.5 · ViralTrack API (D5 core) | FastAPI wrapper over `discover_content`, `search_content`, `get_creator`, capabilities; OpenAPI; schema-leak test | **D5 authorization** | 3 to 5 |
| UI 1 · Shell and design system | Vite + React + TS + Tailwind tokens, shadcn init, sidebar/header, theme, fonts, Lucide, routing, error boundary, Playwright + axe in CI, licence scan of the installed tree | UI 0.5 | 4 to 6 |
| UI 2 · Discover | FilterBar, PolicySort, VideoCard, QuickView, skeletons, empty and error states, table-view toggle, DEMO labelling | UI 1 | 5 to 8 |
| UI 3 · Overview and analytics | KPI tiles and raw aggregate charts (Recharts), provenance panels; history charts only after D6 | UI 2; D6 for history | 4 to 6 |
| UI 4 · Exploration and motion | Niche map (sigma.js, lazy), counters, layout animation; optional hero field after a performance review | UI 3 | 4 to 7 |
| UI 5 · Hardening | accessibility audit, visual regression baselines, performance budgets from measurements, browser matrix (current Chrome, Edge, Firefox, Safari) | all | 3 to 5 |

Total, roughly 23 to 37 working days after D5 is authorized. Policy-dependent wording (D4) can change labels late, so labels live in one dictionary.

Order rationale: the API first, because the UI must never call the foundation directly; Discover before Overview, because it is the product's core and it proves the policy boundary; 3D last, because it is optional and must be justified by measurements.
