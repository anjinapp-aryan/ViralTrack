# Owner decisions for the UI redesign

Date: 2026-11-07. Nothing below is approved yet.

| # | Decision | Options | Recommendation |
|---|---|---|---|
| 1 | Authorize D5 (ViralTrack API), the prerequisite for any ViralTrack UI | authorize / keep deferred | Authorize the API core first (UI 0.5) |
| 2 | New ViralTrack web app on React + Vite + TypeScript + Tailwind + shadcn/ui, separate from the foundation's UI | approve / choose a framework-free stack (more BUILD) | Approve: it is the option that reuses accessible components instead of building them |
| 3 | Design direction | A, B, C or a mix | B as primary, A for analytics and tables, C's niche map only |
| 4 | Thumbnails: show `thumbnail_url` hot-linked from YouTube (never downloaded or stored) | allow after counsel review / placeholders only | Ask counsel; use designed placeholders until then |
| 5 | 3D hero field | include later / never | Decide after UI 4 performance measurements; not in the first milestone |
| 6 | Dev-only MPL-2.0 tool `axe-core` | accept as unmodified dev tool / reject | Accept (same reasoning as `certifi`) |
| 7 | Keep the foundation dashboard as an internal operator tool | yes / retire it | Yes: it remains useful and must not be exposed publicly |
| 8 | Wording such as "viral", "trending", "breakout" in the ViralTrack UI | after D4 counsel answers | Use neutral words ("most viewed", "newest") until then |

## First authorized milestone (proposed)

UI 0.5 + UI 1: the ViralTrack discovery API and an app shell with the design system, theme, navigation, CI accessibility checks and an installed-dependency licence scan, showing one Discover page wired to DEMO data. Estimated 7 to 11 working days.
