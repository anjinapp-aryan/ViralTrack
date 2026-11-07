# ViralTrack design system (proposal)

Date: 2026-11-07. A proposal, not an implementation. Built as Tailwind v4 theme tokens consumed by shadcn/ui components, so the look is ViralTrack's own while the components are reused.

## 1. Identity: "observed, not predicted"

The brand promise is honest data. It is made visible: every number can show where it came from, how old it is, and whether it is RAW or DERIVED. That is the recognisable element, more than any colour.

## 2. Colour tokens

| Token | Dark | Light | Use |
|---|---|---|---|
| `bg` | `#0c0d10` | `#fbfaf8` | page |
| `panel` / `panel-2` | `#15171c` / `#1c1f26` | `#ffffff` / `#f4f2ee` | cards, inputs |
| `ink` / `ink-2` / `muted` | `#f4f4f5` / `#c4c6cc` / `#8a8f99` | `#18181b` / `#3f3f46` / `#71717a` | text levels |
| `line` | `#262a33` | `#e7e5e0` | borders |
| `accent` (brand coral) | `#ff6b4a` | `#e5482a` | primary actions, active nav |
| `accent-2` (amber) | `#ffb547` | `#c77700` | focus ring, DERIVED tag |
| `raw` (green) | `#22c55e` | `#15803d` | RAW tag, freshness dot |
| chart series | indigo `#818cf8`, teal `#2dd4bf`, amber `#fbbf24`, rose `#fb7185`, sky `#38bdf8` | darker equivalents | categorical, max five |

Contrast targets: body text 4.5:1 and large text 3:1 (WCAG 2.2 AA) on both themes; to be verified with axe in implementation. Green and red never carry meaning alone; they come with a sign or word.

## 3. Typography

Inter (OFL) for UI with tabular figures on all numbers; Geist (OFL) optional for display headings. Scale: 12 / 13 / 14 (body) / 16 / 20 / 26 / 34 px; weights 400, 500, 600, 700; headings tracking −1.5 % to −3 %.

## 4. Spacing, radius, elevation, glass

4 px grid (4, 8, 12, 16, 24, 32, 48). Radius: 6 (chips), 10 (inputs), 14 (cards and thumbnails), 22 (hero). Shadows: one subtle level for cards, one deep level for drawers. Glass (backdrop blur) only on the sticky header and the drawer scrim, never on data surfaces.

## 5. Core ViralTrack components (on top of shadcn)

| Component | Built from | Behaviour |
|---|---|---|
| `VideoCard` | shadcn Card, AspectRatio | 16:9 thumbnail from `thumbnail_url` (hot-linked, never stored), duration chip, "≤ 3 min" chip when `short_form`, 2-line title, creator line, **one** hero number (views) and age |
| `QuickView` | shadcn Sheet (Radix Dialog) | all allowed values with RAW/DERIVED tags, provenance, add to watchlist |
| `MetricValue` | BUILD | value, tag, tooltip with formula; "Hidden by creator" or "Not available", never 0 |
| `FreshnessChip` | Badge | "Read from YouTube 2 h ago"; DEMO badge when `origin` is demo |
| `PolicySort` | ToggleGroup | options from the API capability list (today: Most views, Newest) |
| `FilterBar` | Command, Popover, Select | period, niche, creator size (≤ 1M), length, region |
| `EmptyState`, `ErrorState`, skeletons | shadcn | text explains why; nothing is hidden silently |

## 6. Information architecture (minimum viable)

| Section | v1 | Source |
|---|---|---|
| Overview | yes | discovery summary through the ViralTrack API |
| Discover | yes (primary) | `discover_content` / `search_content` |
| Niches | list in v1; map later | niche labels and counts (raw) |
| Creators | profile with raw counts | `get_creator` |
| Keywords | later | foundation keywords are derived (lift, momentum): needs classification first |
| Watchlists | after D6 | foundation watchlist |
| Analytics | raw aggregates only in v1 | sums and counts of allowed values |
| Alerts | later | foundation alerts; policy review needed |
| Settings | yes | theme, language, data origin display |

Keywords, Watchlists, Analytics history and Alerts are not in the first milestone because each depends on a policy or a deferred stage.
