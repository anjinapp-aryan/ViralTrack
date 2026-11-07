# Open-source reuse audit for the ViralTrack UI

Date: 2026-11-07. Nothing installed; no lockfile changed.

## Method and evidence

For each repository: `gh api repos/<repo>` (licence identifier, last push, archived flag, stars, open issues plus pull requests), `gh api repos/<repo>/license` (the **actual licence file text**, first lines read), `gh api repos/<repo>/releases/latest`, a root listing for test directories, and `npm view <package> version license dist.unpackedSize dependencies` for the published package. Raw output: session scratch files `ui_meta.txt`, `ui_meta2.txt`, `ui_lic.txt` (not committed).

Not done, stated honestly: security-advisory review per package, transitive dependency trees beyond the direct count, bundle measurements in a real build, browser testing. "Framework compatibility" comes from each project's documented scope, not from a trial integration. Unpacked size is the npm package on disk, **not** the shipped bundle (tree-shaking typically ships far less).

## 1. The decision that comes before any library

The foundation UI is framework-free and must not be modified. ViralTrack has no UI. So the choice is not "which library fits the current frontend" but "what stack should a new ViralTrack frontend use". Two options were compared:

| | Option R: React + Vite + TypeScript | Option V: no framework (Lit web components or plain ES modules) |
|---|---|---|
| Accessible primitives (dialog, menu, combobox, tabs, tooltip, popover) | REUSE Radix Primitives (MIT, Playwright e2e tests in repo) through shadcn/ui (MIT) | Must BUILD most of them, or adopt Shoelace (**archived** on GitHub) |
| Dashboard and chart components | shadcn charts on Recharts (MIT), Tremor (Apache-2.0) as reference | ECharts or uPlot directly; no component layer |
| Animated components | Motion (MIT), Magic UI and motion-primitives (MIT, copy-in) | Motion's framework-free `animate()` only |
| 3D | three.js through react-three-fiber and drei (MIT), lazy | three.js directly |
| Consistency with foundation | Different stack (acceptable: a separate app) | Same style as the foundation |
| Generic BUILD needed | Little | Large (accessible widgets, table, command palette) |

**Decision: Option R.** It is not a migration (there is no ViralTrack frontend to migrate), and Option V would require building generic accessible widgets, which the reuse policy forbids when a mature alternative exists. The foundation keeps its own UI unchanged as an internal tool.

## 2. Candidate evaluation

Licence column: what the licence file says. "Last push" and "release" from GitHub on 2026-11-07. Issues = GitHub open issues plus pull requests.

### Foundation and build

| Candidate | Capability | Actual licence | Maintenance | Tests | Framework | Effort | Decision |
|---|---|---|---|---|---|---|---|
| react (npm 19.3.1) | UI runtime | MIT | active | yes (upstream) | — | low | REUSE |
| vitejs/vite | build and dev server | MIT (file) | push 2026-11-06, v8.3.6 2026-11-05 | vitest configs in repo | any | low | REUSE |
| tailwindlabs/tailwindcss | styling tokens and utilities | MIT (file) | push 2026-11-06, v4.3.5 2026-11-06 | vitest | any | low | REUSE |
| TanStack/query | server state, caching, retries off by default for us | MIT | push 2026-11-07 | yes | React | low | REUSE |
| TanStack/table | headless data table (sort, column visibility) | MIT | push 2026-11-02 (v9 in beta; use v8 stable) | yes | React | low | REUSE |
| preactjs/preact | smaller React alternative | MIT (file), 11.2.0 | active | test dir | React-compatible with caveats | medium | REJECT (compat layer risk with Radix) |
| lit/lit | web components | BSD-3-Clause (file) | active | yes | none | high (Option V) | REJECT (see section 1) |

### Components and design system

| Candidate | Capability | Actual licence | Maintenance | Tests | Framework | Effort | Decision |
|---|---|---|---|---|---|---|---|
| shadcn-ui/ui | copy-in components on Radix + Tailwind; charts, command palette, sheet, sidebar | MIT (file), shadcn@4.23.0 2026-10-27 | push 2026-11-07, 127,539 stars, 1,766 open | CLI tests | React | low | **REUSE** (copy-in, restyle with our tokens) |
| radix-ui/primitives | accessible primitives | MIT (file, © WorkOS) | push 2026-10-14 | e2e + Playwright + vitest dirs | React | low | **REUSE** (via shadcn) |
| tremorlabs/tremor | dashboard components | Apache-2.0 (file) | last push 2025-10-10; `tremor-npm` last push 2025-01-13 | not checked | React | low | REFERENCE (maintenance slowing; overlaps shadcn charts) |
| ant-design/ant-design | complete design system | MIT | active, 1,149 open | yes | React | medium | REJECT (strong own visual language, large; overlaps shadcn) |
| mui/material-ui | complete design system | MIT | active, 1,534 open, v10 alpha | yes | React | medium | REJECT (Material look; overlaps) |
| adobe/react-spectrum (React Aria) | accessible hooks | Apache-2.0 | active | yes | React | medium | REFERENCE (alternative to Radix if needed) |
| floating-ui/floating-ui | positioning | MIT (file) | active | — | any | — | transitive of Radix; no direct use |
| shoelace-style/shoelace | web components | MIT | **archived** 2026-05 | — | none | — | REJECT (archived) |
| magicuidesign/magicui | animated copy-in components (number ticker, border beam, grids) | MIT (file) | push 2026-11-05 | not found | React + Motion + Tailwind | low | **ADAPT** (copy 2 to 3 components only; a paid "Pro" tier exists, do not use it) |
| ibelick/motion-primitives | animated copy-in primitives | MIT (file `LICENCE.md`) | push 2026-09-28 | not found | React + Motion | low | ADAPT (selectively) |
| animate-ui/animate-ui | animated components | **MIT + Commons Clause** (file) | push 2026-11-02 | — | React | — | **REJECT**: Commons Clause forbids selling the software or a service whose value derives from it; incompatible with a commercial product without legal review |

### Charts and graph

| Candidate | Capability | Actual licence | Maintenance | Tests | Framework | Effort | Decision |
|---|---|---|---|---|---|---|---|
| recharts/recharts | SVG charts | MIT (file), v3.10.1 2026-07-25 | push 2026-11-07, 470 open | yes | React | low | **REUSE** (via shadcn chart wrapper) |
| apache/echarts | canvas/SVG charts incl. graph, large data | Apache-2.0 (file), 6.1.0 2026-05-19 | push 2026-10-13, 1,487 open | test dir | any | medium | REJECT for v1 (overlaps Recharts; reconsider for very large series) |
| airbnb/visx | low-level D3 primitives | MIT (file), v4.0.0 2026-06-11 | last push 2026-06-22 | — | React | high | REJECT (more BUILD than Recharts) |
| leeoniya/uPlot | very fast time series | MIT (file), 1.6.32 2025-03-14 | push 2026-10-30 | test dir | any | medium | REFERENCE (if history charts get large) |
| d3/d3 | primitives | ISC (file) | active | yes | any | high | transitive only |
| observablehq/plot | exploratory charts | ISC (file) | active | — | any | medium | REJECT (overlap) |
| visgl/deck.gl | WebGL geo and large-scale layers | MIT (file) | active | — | any | high | REJECT (geo-focused, heavy; no map need) |
| jacomyal/sigma.js (+ graphology) | WebGL network graphs | MIT (file), sigma@4.0.4 2026-10-27; graphology MIT | push 2026-11-05 | vitest | any | medium | **REUSE** for the niche map (2D, readable, scales) |
| vasturiano/3d-force-graph | 3D force graph on three.js | MIT (file) | push 2026-11-05, 249 open | not found | any | low | REFERENCE (3D graphs are harder to read than 2D) |

### Motion and 3D

| Candidate | Capability | Actual licence | Maintenance | Tests | Framework | Effort | Decision |
|---|---|---|---|---|---|---|---|
| motiondivision/motion | animation (React and vanilla) | MIT (file, © Motion B.V.), npm 14.10.1 | push 2026-11-07, 4 open | Playwright + tests dir | React and any | low | **REUSE** (single animation library) |
| greensock/GSAP | animation | **No licence file**; README points to GreenSock "Standard No-Charge License"; npm licence field "Standard 'no charge' license" | active | — | any | low | REJECT (proprietary terms, not OSI; overlaps Motion) |
| juliangarnier/anime | animation | MIT (file), v4.5.0 | active | — | any | low | REJECT (overlap with Motion) |
| daniel-lundin/react-preloaders | preloaders | repository **not found** (404) | — | — | — | — | REJECT (unavailable; skeletons come from shadcn) |
| mrdoob/three.js | WebGL engine | MIT (file), r187 2026-10-30 | push 2026-11-06, 400 open | test dir | any | medium | **REUSE**, lazy, one scene only |
| pmndrs/react-three-fiber | React renderer for three.js | MIT, v9.8.2 2026-10-15 | push 2026-10-21 | not checked | React | low | REUSE (with three.js) |
| pmndrs/drei | helpers for R3F | MIT, v10.7.9 2026-09-25 | push 2026-10-21, 151 open | not checked | React | low | REUSE (only the helpers used) |
| pmndrs/postprocessing | bloom and effects | Zlib (file) | push 2026-11-01 | — | three.js | low | DEFER (Zlib is permissive; not needed for v1) |
| pixijs/pixijs | 2D WebGL engine | MIT (file), v8.22.0 | active, 419 open | — | any | medium | REJECT (games-oriented; overlaps three.js and sigma) |
| tsparticles/tsparticles | particle effects | MIT (file), v4.4.0 | active | — | any | low | REJECT (14 direct dependencies for a decoration three.js already covers) |

### Icons and fonts

| Candidate | Capability | Actual licence | Maintenance | Decision |
|---|---|---|---|---|
| lucide-icons/lucide | icons | **ISC** (file; GitHub shows NOASSERTION), 1.70.0 2026-11-06 | active | **REUSE** (shadcn default) |
| tabler/tabler-icons | icons | MIT (file), v3.50.0 | active | REJECT (overlap with Lucide) |
| rsms/inter | typeface | SIL OFL 1.1 (file) | v4.1 2024-11 | **REUSE** (UI text, tabular numbers) |
| vercel/geist-font | typeface | SIL OFL 1.1 (file) | v1.9.2 2026-11-06 | REUSE for display headings (optional) |

### Quality tooling

| Candidate | Capability | Actual licence | Decision |
|---|---|---|---|
| microsoft/playwright | e2e, visual screenshots | Apache-2.0 (file), v1.65.0 2026-11-05 | **REUSE** (also replaces a paid visual-regression service) |
| dequelabs/axe-core (+ @axe-core/playwright) | automated accessibility checks | **MPL-2.0** (file) | REUSE as an unmodified dev-only tool (file-level copyleft; same treatment as `certifi`) |
| vitest (Vite project) + Testing Library | unit tests | MIT | REUSE |
| storybookjs/storybook | component workshop | MIT | DEFER (useful later; not needed for the first milestone) |

## 3. Overlap check (one library per job)

Components: shadcn/Radix only (no MUI, AntD, Tremor). Charts: Recharts only (ECharts, visx, Plot rejected). Graph: sigma.js only. Animation: Motion only (GSAP, anime.js rejected). 3D: three.js + R3F + drei only (PixiJS, tsparticles rejected). Icons: Lucide only.

## 4. BUILD items (ViralTrack-specific, justified)

1. `MetricValue` display component: renders a value with its RAW/DERIVED tag, "hidden by creator" or "not available" instead of zero, and a tooltip with the formula. No library knows the ViralTrack policy.
2. Policy-aware sort and filter controls: a thin wrapper over shadcn controls whose options come from the API's capability list, never hard-coded.
3. Provenance and freshness chip.
4. The ViralTrack API itself (D5, Python, FastAPI as already recommended in `docs/phase-4-7/OPEN_SOURCE_REUSE_AUDIT.md`).

Everything else is reused or copied in from MIT sources.
