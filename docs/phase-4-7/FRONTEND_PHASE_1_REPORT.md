# Frontend phase 1: completion report

Date: 2026-11-07. Baseline: `main` at `4674803` (D5), one commit ahead of `origin/main`; foundation submodule `d872014`, unchanged. Nothing was committed or pushed. No live API call was made and no quota was used: after all runs the foundation reports 0 units and 0 search calls today.

## 1. Result

A ViralTrack web UI in `web/`, adapted from `satnaing/shadcn-admin`, with two working pages: Discover and Data sources. It runs against the D5 API and the local demo foundation, and the owner can open it at http://127.0.0.1:5173. Verdict: **PASS WITH LIMITATIONS** (section 9).

## 2. Foundation adopted and what changed

| Item | Value |
|---|---|
| Source | https://github.com/satnaing/shadcn-admin |
| Commit | `e16c87f213a5ba5e45964e9b67c792105ec74d26` (verified: identical to `main` on 2026-11-07; v2.2.1 line) |
| Licence | MIT, © 2024 Sat Naing (file read; kept as `web/LICENSE`; notice added to `THIRD_PARTY_NOTICES.md`) |
| Import | GitHub tarball of that commit, copied to `web/` |

Removed:
- **Authentication:** Clerk (routes, logos, `@clerk/react`); the demo authentication (sign-in, sign-up, OTP and forgot-password pages, the `_authenticated` guard, the cookie token store `thisisjustarandomstring`, sign-out dialog, profile menu, team switcher).
- **Demo features:** the dashboard with sales cards, tasks, users, chats, apps, help centre, settings pages (profile, account, notifications, display, appearance), and the 401 and 403 pages.
- **Libraries and assets:** faker and all demo datasets; axios; form, OTP and date-picker libraries; zustand; recharts; the data-table kit and five unused Radix packages.
- **Template packaging:** Netlify and GitHub workflow files, the template changelog and social metadata.
- **Third-party font requests:** Google Fonts links, replaced by self-hosted Inter (`@fontsource-variable/inter`, OFL-1.1).

Kept: the layout and responsive collapsible sidebar, header, theme provider (dark, light, system), layout settings drawer, command palette, skip link, error pages (404, 500, 503), shadcn/ui components and the Vitest browser test set-up.

Added:
- **API client:** `openapi-typescript` (types generated from `docs/api/openapi-v1.json`) and `openapi-fetch`.
- **Pages:** the Discover feature and the Data sources page.
- **Status and branding:** an API status indicator, a "Local development" indicator, the ViralTrack mark and favicon, and brand tokens (cyan `#06B6D4`, teal `#14B8A6`, violet `#8B5CF6`).
- **Tests:** axe-core accessibility checks.

Template fixes made while integrating:
- The skip link pointed to a missing `#content`.
- The sidebar content was outside any landmark.
- The command palette's hidden title sat outside its dialog.
- Developer tools were shown by default in development; they are now opt-in with `VITE_DEVTOOLS=true`.

## 3. Reuse decisions

| Need | Decision | Source |
|---|---|---|
| Shell, navigation, theme, layout settings, command palette, errors | ADAPT | shadcn-admin |
| Components (Card, Sheet, Select, Popover, Tooltip, Badge, Skeleton, Alert, Input) | REUSE | shadcn/ui on Radix |
| Routing, URL state, server state | REUSE | TanStack Router (with zod search validation) and TanStack Query |
| API types and client | REUSE | openapi-typescript, openapi-fetch |
| Animation | REUSE | tw-animate-css and Tailwind transitions (no Motion, no 3D) |
| Icons, font | REUSE | Lucide, Inter (Fontsource) |
| Accessibility testing | REUSE | axe-core, Playwright Chromium (through Vitest) |
| Video card, quick view, metric display with provenance, filter bar, platform chips, states, pager | BUILD (small, ViralTrack-specific; composed from shadcn components) | — |
| Segmented control | BUILD (about 60 lines; the template has no toggle group, and adding `@radix-ui/react-toggle-group` was not justified for two controls) | — |

## 4. Dependencies, security and licences

- **Audit:** the template's June lockfile had 62 advisories (22 in the production tree). `pnpm update` within the template's own version ranges (no major upgrade) cleared them. Result: production tree **0 known vulnerabilities**; whole tree 2 moderate, both `minimatch` inside the ESLint plugin chain (dev-only, lint time).
- **Licences, production tree (`pnpm licenses list --prod`):** MIT 108, ISC 4, Apache-2.0 2, BSD-3-Clause 1, 0BSD 1, Unlicense 1 (`isbot`, through TanStack Router), OFL-1.1 1 (Inter).
  - MPL-2.0 2 (`lightningcss`, the Tailwind build-time CSS compiler, unmodified and not shipped in the bundle).
- **Licences, dev tree adds:** MPL-2.0 `axe-core` (dev-only, unmodified), CC-BY-4.0 `caniuse-lite` (data, build time), Python-2.0 `argparse`, BlueOak-1.0.0 and BSD-2-Clause packages.
- **Package manager:** pnpm 10.20.0 through Corepack, with the template's `pnpm-lock.yaml` kept and updated.

## 5. Behaviour and policy

- **API boundary:** the UI calls only `/api/v1/health/ready`, `/api/v1/capabilities` and `/api/v1/discover`, on its own origin. Vite proxies them to `127.0.0.1:8000`, so CORS stays closed on the API. The dev and preview servers bind to 127.0.0.1, and a non-loopback proxy target is refused. A browser network audit recorded **no request to any external host**.
- **Sorting:** only the sorts that `/api/v1/capabilities` marks available are offered (Most views, Newest). A restricted sort in the URL is ignored by the zod schema and never reaches the API.
- **Displayed values:**
  - The UI shows only raw values: views, likes, comments and creator followers, each with a RAW tag and source.
  - Derived values (engagement rate, lifetime views per hour) are never displayed, although the API carries them. Tests assert their values never appear.
  - No score, ranking or restricted label appears.
- **Missing values** are written out ("Hidden or not reported", "views not reported", "date not reported") and never shown as 0. A reported 0 stays 0.
- **DEMO labelling:** a "DEMO data" badge appears whenever `meta.demo` is true, and the quick view states the origin.
- **Freshness:** retrieval time is shown, and the quick view says the platform read time is not reported by the source.
- **Thumbnails:** placeholders only; no `<img>` and no request to the platform image host.
- **Retries:** `retry: false` everywhere; errors show a Retry button.
- **Unavailable platforms:** Instagram and TikTok are shown as unavailable, with the API's reason.
- **No authentication of any kind;** the sidebar and the Data sources page say so.

## 6. Search contract correction (owner decision: keep semantic relevance ordering)

The defect found during phase 1: with a query, the foundation ranks the whole collected corpus by an embedding similarity (`semanticScore`, INTERNAL_ONLY), ignores `sort_by` and filters nothing, while the D5 API labelled such results `sort: "views"`. It is corrected as the owner decided:

| Area | Change |
|---|---|
| API `meta.sort` | now `"relevance"` for topic search (`/api/v1/search`, and `/api/v1/discover` with `query`); `views` or `published_at` when browsing |
| API notes | topic search always carries: "Topic search ranks the collected videos by how closely they match the search text, as the data source computes it. It does not exclude unrelated videos, and relevance is not a measure of popularity or performance." |
| Demo / no topic data | when no returned video has a similarity value, the provider adds: "The data source has no topic data for these videos, so they are not ordered by relevance to the search text." Only the presence of the value is read; it is never mapped or returned |
| Sort with a query | refused with 422 `sort_not_supported_with_query` (on `/discover` with `query`, and any `sort` on `/search`), so a sort is never silently ignored. `/search` no longer has a `sort` parameter |
| Browse sorts | unchanged: `views` (default) and `published_at`; `relevance` is not a choosable sort (422) |
| Capabilities | each sort carries `applies_to` (`browse` or `topic_search`); `relevance` is listed as `topic_search` with a description that rules out popularity and performance |
| Similarity value | never in any response, key or schema (tests check values, keys and OpenAPI) |
| OpenAPI | regenerated `docs/api/openapi-v1.json`; frontend types regenerated |
| UI | topic search shows a fixed "Relevance" order instead of the sort control, the result header reads "Relevance to the topic", and the API notes are shown verbatim; the sort parameter is not sent with a query |

No other metric policy changed. Files: `viraltrack/api/app.py`, `viraltrack/api/schemas.py`, `viraltrack/providers/youtube/provider.py` (search note only), `tests/test_api_d5.py` (+15 tests), `docs/api/openapi-v1.json`, `web/src/lib/api/schema.d.ts` and the Discover components and tests.

## 6a. Final polish: desktop layout and cards

Before: the template's `max-w-7xl` (1280 px) container and fixed breakpoints gave 3 columns at 1440 px and 4 at 1664 px, with cards about 370 px wide and wide empty margins at large widths (`frontend-phase-1-screens/before/`).

After:
- **Container:** the Discover and Data sources pages use a fluid container up to 1680 px.
- **Grid:** the results grid is `repeat(auto-fill, minmax(min(100%, 15rem), 1fr))`. Measured columns: **4 at 1440 px, 5 at 1664 px, 2 at 834 px (tablet), 1 at 390 px (mobile)**, with cards about 260 to 280 px wide.
- **Toolbar:** search, period, creator size, length, More, Reset and Sort sit in one bordered toolbar, on one row at 1664 px and two at 1440 px.
- **Results header:** the count leads ("170 videos"), followed by the order, source, freshness and DEMO badge.
- **Cards:** a bordered surface, a two-line title with a fixed height so rows align, the creator, a divider, then views as the headline number with the age. Hover lifts the card and tints the border; focus shows a ring; both are disabled under reduced motion.
- **Thumbnail placeholder:** tinted with a CSS dot texture and shows the real category label. There is still no image request.
- **Skeleton:** has the same card shape.

No dependency was added for any of this.

## 7. Verification evidence

| Check | Result |
|---|---|
| TypeScript (`tsc -b`) | 0 errors |
| ESLint | 0 problems |
| Prettier | all files formatted |
| knip | no unused files or dependencies; 3 unused exports left in template utilities |
| Production build (`vite build`) | succeeds; main chunk 377 KB (114 KB gzip). It grew from 239 KB because `zod`, used by the Discover route's URL validation, moved from a separate chunk into the main one; the first page needed both chunks before too |
| Frontend tests (Vitest in headless Chromium) | **92 passed, 0 failed, 0 skipped** (10 files: formatting, URL params, API client errors, video card, the Discover page in every state, the Data sources page, template components) |
| Contract | types regenerated from `docs/api/openapi-v1.json`; the D5 snapshot test passes in the Python suite |
| Python, full suite with PostgreSQL 16 + pgvector and the pinned foundation code | **1094 passed, 5 skipped** (3 POSIX-only on Windows, 2 live-foundation smoke tests), 0 failed; ruff clean; `pip check` clean; OpenAPI snapshot consistent |
| End to end in Chrome (Playwright, live stack: demo foundation on 8081, API on 8000, UI on 5173) | Discover at 1440, 1664, 834 and 390 px in dark and light (columns 4, 5, 2, 1); topic search; quick view; Data sources; loading, empty and API-down states; no horizontal scroll at 390 px |
| Accessibility (axe-core 4.14, live pages) | 0 violations on Discover, quick view and Data sources, dark and light (after the template fixes in section 2) |
| Keyboard | first Tab reaches "Skip to Main"; tab order covers sidebar, header, platforms, search, filters, sort, cards; arrow keys change the sort and the URL; a real Escape closes the quick view (dark and light) |
| Reduced motion | card transition property is `none` with `prefers-reduced-motion: reduce` |
| Network | requests only to 127.0.0.1; API paths only `/api/v1/*` |

Screenshots committed in `docs/phase-4-7/frontend-phase-1-screens/` (four representative views, demo data): `discover-dark-desktop.png` (1440 px, dark), `discover-light-desktop.png` (1440 px, light), `discover-light-tablet-viewport.png` (834 px) and `discover-light-mobile-viewport.png` (390 px). The other captures from the verification runs (1664 px, quick view, Data sources, topic search, loading, empty and API-down states, and the two "before" images) were left uncommitted in the same folder.

Fixes found by the tests during the work:
- `openapi-fetch` captured `fetch` at start-up; it now looks it up per request.
- `aria-label`s on cards and platform chips did not contain their visible text (WCAG 2.5.3); they were removed so the visible text is the name.
- Opening the quick view focused an info icon and popped its tooltip, so the first Escape closed the tooltip instead of the panel; the panel now takes focus on open.

## 8. Startup

See `web/README.md` for the exact PowerShell commands for the foundation (8081, demo, no key), the API (8000) and the UI (5173).

## 9. Limitations and open items

1. **Topic search** is now honest (section 6), but on the demo corpus it cannot rank by relevance (no topic data), and the API says so.
2. **Thumbnails** stay placeholders until counsel decides on platform images.
3. **During topic search the order is fixed to relevance;** only Discover and Data sources exist (creators, history and watchlists are later phases).
4. **No CI job for `web/` yet.** The checks above were run locally. Adding a `web` job (pnpm install, typecheck, lint, test, build) is the next step once the owner wants it in CI.
5. **Remaining audit items:** 2 dev-only moderate advisories (`minimatch` in the ESLint chain).
6. **Not tested:** screen-reader runs with NVDA, JAWS or VoiceOver (automated axe only); Firefox and Safari (Chromium only); Lighthouse performance numbers.
7. **Only four screenshots are committed**; the remaining verification captures stay local and uncommitted.

## 10. Acceptance gate

| Criterion | Result |
|---|---|
| Based on the approved reusable foundation | yes, shadcn-admin `e16c87f`, MIT |
| No fake authentication remains | yes (Clerk and demo auth removed; tests list only the working pages) |
| Discover works with the ViralTrack API | yes (live run) |
| No restricted metric displayed or used for sorting | yes (tests and live check) |
| Works with demo data | yes, labelled DEMO |
| No live quota consumed | yes, 0 units and 0 searches |
| Responsive and polished | yes (3 widths, 2 themes; screenshots) |
| Build, type check, lint, tests pass | yes |
| Submodule unchanged | yes, `d872014` |
| No deployment, commit or push | yes |
