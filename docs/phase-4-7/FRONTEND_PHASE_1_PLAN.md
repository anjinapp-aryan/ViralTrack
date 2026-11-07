# Frontend phase 1: proposed plan (needs explicit approval)

Date: 2026-11-07. Proposal only. Nothing in this plan has started.

## Scope

A new `web/` application adapted from `satnaing/shadcn-admin` (MIT), connected to the D5 API, with the dark glassmorphism shell. The Python packages, the foundation and its dashboard stay unchanged.

## Steps

1. **Import:** copy shadcn-admin at a pinned commit into `web/`, keeping its `LICENSE` and copyright notice and recording the source commit in `THIRD_PARTY_NOTICES.md`.
2. **Remove:**
   - Clerk (`@clerk/react`, `src/routes/clerk`, Clerk assets).
   - Faker and every `features/*/data` demo dataset.
   - The demo features (tasks, chats, users, apps, sales cards) and any sponsor badges.
3. **Keep:** Vite, React 19, TypeScript, TanStack Router/Query/Table, Radix, Tailwind 4, Recharts, cmdk, sonner, the layout and sidebar, theme switch, settings, error pages, and the existing vitest and Playwright setup.
4. **Typed client:** generate it from `docs/api/openapi-v1.json`. Run a licence audit of the generator before adding it.
5. **Shell:**
   - Glass design tokens (dark first, light theme kept), with blur only on the header, sidebar and drawers.
   - Navigation for Overview, Discover, Creators and Settings.
   - A platform switcher driven by `/api/v1/capabilities`: Instagram and TikTok shown as unavailable, with the reason from the API.
6. **First page, Discover:**
   - Filters taken from the capabilities response.
   - Sort toggle offering only Most views and Newest.
   - Video cards: thumbnail placeholder until counsel decides on hot-linking, duration, title, creator, views and age.
   - A quick-view drawer with RAW/DERIVED labels and provenance.
   - A DEMO badge whenever `meta.demo` is true.
   - Loading, empty, error and unavailable states.
7. **Quality gates:**
   - axe on every route.
   - Playwright keyboard and reduced-motion tests.
   - Screenshot baselines in both themes at three widths.
   - A unit test that `null` never renders as 0.
   - A licence and `npm audit` report on the installed tree.
   - A CI job for `web/`.

## Out of scope for phase 1

No outlier, discovery or ranking scores. No history (D6), no 3D, no authentication UI (it waits for the API's authentication decision), and no change to the foundation dashboard.

## Estimate and decisions needed

About 7 to 11 working days.

Decisions needed:
- Approve phase 1.
- Choose the pinned shadcn-admin commit (default: the latest tag at the time of import).
- Approve the OpenAPI client generator once it has been audited.
- Decide whether thumbnails wait for counsel (default: placeholders).
