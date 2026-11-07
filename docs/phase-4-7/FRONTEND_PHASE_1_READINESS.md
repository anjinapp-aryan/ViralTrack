# Frontend phase 1: readiness review

Date: 2026-11-07. Review only. No frontend code, no installation, no commit. The plan under review is [FRONTEND_PHASE_1_PLAN.md](FRONTEND_PHASE_1_PLAN.md) (it lives in `docs/phase-4-7/`, not in `docs/ui-redesign/`). The D5 API it builds on is commit `4674803`.

## 1. Fresh reuse audit (evidence)

Method: on 2026-11-07, `gh api repos/<repo>` (licence identifier, last push, archived flag, stars, open issues plus pull requests); the licence file text through `gh api repos/<repo>/license`; the latest release; and the number of published repository security advisories (`/security-advisories`). Advisories are disclosed and normally fixed issues: a sign of a working disclosure process, not of open vulnerabilities. Not done: `npm audit`, transitive licence scan and bundle measurement, which all need an installation (milestone step 1).

| Candidate | Licence (file) | Last push / release | Open | Advisories | Use in phase 1 | Decision |
|---|---|---|---|---|---|---|
| satnaing/shadcn-admin | MIT, © 2024 Sat Naing | push 2026-09-10, last commit e16c87f 2026-06-11, v2.2.1 2025-11-06 | 27 | 0 | app shell, layout, sidebar, theme, settings, errors, data table, command palette, tests | **ADAPT** |
| shadcn-ui/ui | MIT | 2026-11-07, shadcn@4.23.0 | 1,766 | 0 | component source (already inside shadcn-admin) | REUSE |
| radix-ui/primitives | MIT, © WorkOS | push 2026-10-14, no GitHub release | 276 | 0 | accessible primitives under shadcn | REUSE; watch maintenance |
| mui/base-ui | MIT | 2026-11-07, v1.9.0 | 475 | 0 | alternative primitive layer that shadcn also supports | REFERENCE (fallback if Radix stalls) |
| TanStack router / query / table | MIT | active | 813 / 114 / 83 | 3 / 1 / 0 | routing, server state, tables (already in shadcn-admin) | REUSE |
| pacocoursey/cmdk | MIT | push 2025-10-29, v1.1.1 2025-03 | 80 | 0 | command palette (already in) | REUSE |
| emilkowalski/sonner | MIT | 2026-08, v2.0.8 | 85 | 0 | toasts (already in) | REUSE |
| Wombosvideo/tw-animate-css | MIT | 2026-02, v1.4.0 | 20 | 0 | CSS enter/exit animations (already in) | **REUSE as the only animation layer in phase 1** |
| motiondivision/motion | MIT, © Motion B.V. | 2026-11-07 | 4 | 0 | layout animation, counters | DEFER (not needed for the Discover page) |
| recharts/recharts | MIT | 2026-11-07, v3.10.1 | 470 | 0 | charts (already in shadcn-admin) | REUSE when a chart is needed; none in phase 1 |
| mrdoob/three.js, pmndrs/react-three-fiber, pmndrs/drei | MIT | r187 / v9.8.2 / v10.7.9 | 400 / 32 / 151 | 0 | 3D | **DEFER**: nothing in phase 1 needs 3D |
| jacomyal/sigma.js | MIT | sigma@4.0.4 2026-10-27 | 5 | 0 | niche map | DEFER to a later phase |
| openapi-ts/openapi-typescript (+ openapi-fetch) | MIT, © Drew Powers | 2026-09-25 | 287 | 0 | TypeScript types from `docs/api/openapi-v1.json`, tiny fetch client | **REUSE** (dev-time types, small runtime) |
| hey-api/openapi-ts | MIT | 2026-10-31 | 662 | 1 | client generator | REJECT (more runtime and open issues than needed) |
| orval-labs/orval | MIT | 2026-10-30 | 22 | 42 | client + query hook generator | REJECT (heavier; overlaps TanStack Query wiring) |
| lucide-icons/lucide | ISC (GitHub shows NOASSERTION) | 1.70.0 2026-11-06 | 363 | 0 | icons (already in) | REUSE |
| rsms/inter | OFL-1.1 | v4.1 2024-11 | 149 | 0 | UI font | REUSE (self-hosted, licence file shipped) |
| magicuidesign/magicui, ibelick/motion-primitives | MIT | 2026-11 / 2026-09 | 11 / 35 | 0 | animated extras | DEFER (need Motion) |
| Glass UI libraries | `gh search repos "glassmorphism shadcn"` returned one repository with 0 stars and no licence | — | — | — | — | REJECT; glass is a few design tokens and Tailwind utilities (`backdrop-blur`, translucent surfaces), not a dependency |

shadcn-admin dependency set (from its `package.json`): React 19.2, Vite, TypeScript, Tailwind 4.2, TanStack Router/Query/Table, 17 Radix packages, cmdk, sonner, recharts 3.8, lucide-react, zod, react-hook-form, date-fns, zustand, axios, react-day-picker, input-otp, react-top-loading-bar, tw-animate-css, plus `@clerk/react` and dev-only `@faker-js/faker`. All have permissive licences per npm metadata (not re-read file by file; done at install).

## 2. Authentication: can Clerk be deferred? Yes, and it should be

- **The milestone does not need authentication.** The D5 API refuses to bind to anything but loopback, and phase 1 is a local development UI.
- **Clerk is a hosted, proprietary identity service.** Only its SDK is MIT (clerk/javascript). Adopting it means a vendor contract, user data processed by a third party, and frontend-only session handling. The ViralTrack API is Python, so it would still need its own token verification.
- **shadcn-admin's other "auth" is a demo:** `src/stores/auth-store.ts` keeps a token in a cookie named `thisisjustarandomstring`, and the sign-in, sign-up, OTP and forgot-password pages are not wired to any server. Keeping it would look like security without being any. **Remove both** the Clerk routes (`src/routes/clerk/**`) and the demo auth (`(auth)` routes, `_authenticated` guard, `auth-store`), along with `@clerk/react`, `input-otp` and the zustand auth store.
- **When authentication becomes necessary,** the boundary belongs in front of the Python API, not in the browser. The recommended pattern is a reverse proxy with OpenID Connect: `oauth2-proxy/oauth2-proxy` (MIT, v7.15.6 2026-11-05), with an identity provider chosen then, for example `authelia/authelia` (Apache-2.0, lighter) or `keycloak/keycloak` (Apache-2.0, heavier, 3,491 open).
- **Rejected for that later stage:**
  - `zitadel/zitadel`: AGPL-3.0.
  - `goauthentik/authentik`: mixed licensing ("Portions of this software are licensed as follows").
  - `better-auth/better-auth`: TypeScript server library; ViralTrack has no Node backend.
  - `nextauthjs/next-auth`: Next.js-oriented.
  - `supabase/auth`: implies Supabase, which was ruled out.
  - `logto-io/logto`: MPL-2.0 service; possible but not needed.

## 3. Current versus proposed architecture

Current: browser (none) · ViralTrack API (`127.0.0.1:8000`, read-only, 7 endpoints, OpenAPI snapshot) → provider → foundation → PostgreSQL. The foundation dashboard stays internal on its own port.

Proposed phase 1: `web/` (Vite dev server on `localhost:5173`, static build later) → ViralTrack API, with CORS limited to `http://localhost:5173`. No server code in `web/`, and no direct foundation access.

## 4. Reuse map for phase 1

| Need | Source | Strategy |
|---|---|---|
| Shell, sidebar, header, theme, settings, error pages | shadcn-admin | ADAPT (strip demo features) |
| Components (Card, Sheet, Select, ToggleGroup, Badge, Skeleton, Tooltip) | shadcn/ui on Radix (already in shadcn-admin) | REUSE |
| Routing and data fetching | TanStack Router + Query (already in) | REUSE |
| API types and client | openapi-typescript + openapi-fetch from `docs/api/openapi-v1.json` | REUSE (replace axios) |
| Animation | tw-animate-css + Radix `data-state` transitions (already in) | REUSE; Motion deferred |
| Icons, font | Lucide, Inter | REUSE |
| Glass look | design tokens + Tailwind utilities | BUILD (CSS only, no library) |
| `MetricValue`, `FreshnessChip`, `DemoBadge`, `PolicySort`, `PlatformSwitcher` | none exists | BUILD (small, ViralTrack-specific) |
| Charts, 3D, graph | Recharts / three.js / sigma.js | not in phase 1 |

## 5. Discover page component design

- **FilterBar:**
  - Options come from `/api/v1/capabilities` `filters`: `period` (select), `niche` (text), `creator_size` (select of the 4 enum values; "Any (up to 1M)"), `duration` (3-way toggle labelled "Any / Up to 3 min / Over 3 min"), `region` (select), `min_views` (number), `query` (search box).
  - When a query is typed, the discover-only filters (`creator_size`, `min_views`, `region`) are disabled with a tooltip; the API returns 422 for them.
- **PolicySort:** the two available sorts from `capabilities.sorts`, "Most views" and "Newest". The unavailable ones are not shown as options; the reasons appear in a help popover.
- **PlatformSwitcher:** YouTube active. Instagram and TikTok are disabled chips whose tooltip is the API's `reason`.
- **VideoCard:**
  - 16:9 thumbnail: a placeholder until counsel decides on hot-linking; then `thumbnail_url` with `loading="lazy"` and `referrerpolicy="no-referrer"`.
  - Duration chip, and an "≤ 3 min" chip when `duration_seconds` is 1 to 180.
  - Two-line title, then the creator name and followers (or "hidden").
  - One headline number (views) and the relative age.
  - DEMO badge when `origin` is not `real_provider_data`.
- **QuickView** (Sheet):
  - Every v1 field, each metric through `MetricValue`: value, RAW/DERIVED tag, source, a tooltip with the `note`, and "Hidden" or "Not reported" for `null`.
  - `collected_at` null shown as "read time not reported".
  - A link to the platform `url` (`rel="noopener noreferrer"`).
- **States:**
  - Skeleton grid while loading.
  - Empty state with the filters used.
  - Error state using the API `error.code` (`provider_unavailable`, `provider_timeout`, `invalid_request`, `page_out_of_range`).
  - Unavailable-platform state.
  - `meta.notes` shown in an info strip.
- **Pagination:** page and page size up to 100. "Load more" is disabled at `page × page_size = 1000`, and `has_more: null` reads "more may exist; narrow the filters".

## 6. Design system

The tokens from `docs/ui-redesign/VIRALTRACK_DESIGN_SYSTEM.md`, adapted to the dark glass direction:
- **Surfaces:** near-black navy base (`#05070d`) with translucent panels (`rgba(18,24,38,.62)`).
- **Accents:** cyan `#22d3ee` and teal `#2dd4bf` as primary, violet `#a78bfa` as secondary. Neon only on focus and active states.
- **Glass and contrast:** blur only on the header, sidebar and drawers. Data surfaces stay opaque enough to keep 4.5:1 text contrast (checked with axe).
- **Themes:** a light theme is kept.
- **Type:** Inter with tabular numbers.

## 7. Animation and 3D strategy

- **Phase 1:** tw-animate-css for drawer, dialog and toast enter/exit, plus a skeleton shimmer, all honouring `prefers-reduced-motion`. No Motion and no 3D.
- **Later phases:** Motion when card reordering or counters are wanted; sigma.js for the niche map; three.js through react-three-fiber only for an optional hero, lazy-loaded, if the owner still wants it after measurements.

## 8. API integration mapping

| UI | Endpoint | Fields |
|---|---|---|
| App boot, filters, sorts, platform chips | `GET /api/v1/capabilities` | platforms, filters, sorts, metrics, page limits |
| Discover grid | `GET /api/v1/discover` (with `query` → text search) | `data[]` Video, `meta` (has_more, total, demo, notes) |
| Search box (dedicated page later) | `GET /api/v1/search` | same envelope |
| Creator link in QuickView | `GET /api/v1/creators/{id}` | creator, demo, notes |
| Status indicator | `GET /api/v1/health/ready` | checks |

TanStack Query: retries off for 4xx and at most 1 for 503/504; `staleTime` about 60 s. All of these are free reads.

## 9. Security and data-policy boundaries

- The frontend holds no secrets and calls only the ViralTrack API, never the foundation. There is no authentication UI in phase 1.
- It shows only fields present in the OpenAPI types; nothing is computed except formatting. No metric, ranking or score is invented in the browser, and `null` is never coerced to 0 (enforced by a unit test).
- Thumbnails stay placeholders until counsel decides. Platform text (titles, names) is rendered as text, never as HTML.
- CORS is the single dev origin. Before any deployment, the reverse-proxy authentication from section 2 goes in front of both.

## 10. Test strategy

- **Unit (vitest, already in shadcn-admin):** `MetricValue` null handling; the sort control renders only API sorts; disabled filters with `query`; DEMO badge.
- **Component and browser tests (vitest browser + Playwright, already in):** keyboard flow, Escape closes the QuickView, focus return, reduced motion.
- **Accessibility:** axe on every route, with zero serious or critical violations.
- **Visual:** Playwright screenshots in dark and light at 375, 768 and 1440 px.
- **Contract:** TypeScript types regenerated from the OpenAPI snapshot in CI; the build fails on drift.
- **End-to-end:** against the D5 API in front of the demo foundation (no key, no quota).
- **Supply chain:** `npm audit`, licence scan, lockfile committed, exact versions.

## 11. Effort

About 7 to 11 working days, as planned:
- import and strip: 1 to 2;
- tokens, shell and platform switcher: 2;
- API client and Discover page with all states: 3 to 4;
- tests, CI and audit: 1 to 3.

## 12. Risks and open decisions

**Risks:**
- Radix maintenance is slower than it was; Base UI is the fallback through shadcn.
- shadcn-admin's last code commit was June 2026; it is a template, so it will be owned after the import.
- Glass effects cost GPU time and contrast; keep them limited.
- Thumbnail policy.
- Large result windows (up to 1000 items) on slow networks.
- The demo auth must not survive the strip.

**Decisions:**
1. Approve phase 1 as adapted here: no Clerk, no demo auth, no Motion, no 3D, openapi-typescript instead of axios.
2. The pinned shadcn-admin commit (default `e16c87f`, the latest).
3. Thumbnails: placeholders until counsel answers (default).
4. Accent palette: cyan and teal primary, violet secondary (proposed).
5. Later: the authentication pattern (reverse proxy with OIDC) and identity provider, before any non-local deployment.

**Recommendation: APPROVE WITH ADAPTATIONS** (the decisions above). The original plan is sound. The adaptations remove dependencies phase 1 does not need, and they replace shadcn-admin's demo authentication instead of keeping it.
