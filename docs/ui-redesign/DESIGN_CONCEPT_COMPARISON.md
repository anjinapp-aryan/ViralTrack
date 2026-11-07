# Design concept comparison

Date: 2026-11-07. The three concepts are standalone HTML files in [concepts/](concepts/) (open `concepts/index.html`, or serve the folder with `python -m http.server 8090` and visit http://127.0.0.1:8090/). They are **design concepts, not implementations**, use only synthetic DEMO data and show only approved metrics. They use no external dependency; where a production library would draw something (charts, 3D field, graph), a note in the file names it.

## Concepts

| | A · Premium Analytics | B · Creator Intelligence | C · Futuristic Intelligence |
|---|---|---|---|
| Feel | light-first, dense, calm SaaS | dark-first, editorial, thumbnail-first | deep navy, glass, ambient motion |
| Navigation | full sidebar with groups | top tabs, sticky blurred header | icon rail |
| Overview | KPI tiles, category bars, weekday histogram | (Discover is the home) | hero with ambient field, animated counters |
| Discovery | table with thumbnail column | large 16:9 grid, one hero number per card, quick-view drawer | compact list beside the niche map |
| Filters and search | chips + segmented sort + Ctrl K search | big search field, selects, length pills | command-style search |
| Analytics | strongest (charts, table, provenance footer) | quick-view detail only | niche map |
| States shown | — | loading skeleton, empty state, keyboard Escape, focus | motion toggle, reduced motion |
| Responsive | sidebar hides under 960 px, table columns drop | 4 → 2 → 1 columns | rail hides under 640 px |
| Risk | can feel generic | needs real thumbnails to shine (demo has none; counsel item for hot-linking) | performance, "gaming" look if overdone |

## Policy check (all three)

No VSR, outlier multiplier or label, RPM, projection, Shorts label, semantic score, 24-hour velocity or acceleration appears. Sort controls offer only Most views and Newest. Hidden likes show as "hidden", engagement as "n/a". Every page carries a DEMO banner. A `grep` for VSR, outlier score, RPM and viral score over the concept files finds nothing.

## Recommendation

**Use B as the primary direction**, borrow from A and C:

- B's shell (sticky header, coral accent, editorial type) and Discover grid with quick view: it fixes the two biggest problems of the current UI (badge overload and weak card hierarchy) and puts provenance where users look.
- A's table and chart components for Analytics and for a "table view" toggle on Discover: power users need density.
- C's niche map, lazy-loaded, as the one place where a GPU canvas earns its cost; C's hero field only if the owner wants it after seeing performance numbers.

Reasons: B best matches how creators browse (thumbnails first), it is the cheapest to build from shadcn parts, and it keeps motion to feedback rather than decoration.
