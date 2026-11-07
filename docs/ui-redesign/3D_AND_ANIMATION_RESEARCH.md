# 3D and animation research

Date: 2026-11-07. Library facts in `OPEN_SOURCE_REUSE_AUDIT.md`. No benchmark was run; figures below are design budgets to be measured in implementation, not results.

## 1. Where 3D and motion help, and where they hurt

| Use | Value to the user | Verdict | Library |
|---|---|---|---|
| A. Ambient background field (particles, network) | Brand identity only | **Only in the Overview hero**, never behind numbers or tables | three.js via react-three-fiber, lazy |
| A. Floating geometric shapes, parallax | Decoration | Reject | — |
| A. Ambient gradients | Depth at zero cost | Use (CSS radial gradients) | CSS |
| B. Niche map (niches as nodes, shared creator tags as links, size = video count) | Real exploration of how topics connect | **Yes, in 2D WebGL** | sigma.js + graphology |
| B. 3D niche or creator graph | Looks impressive, harder to read (occlusion, depth ambiguity) | Reject for v1; optional "3D view" toggle later | 3d-force-graph |
| B. Opportunity map | Would need a scoring policy (D4, blocked) | Blocked | — |
| C. Route transitions | Orientation | Short cross-fade (150 to 200 ms) | Motion |
| C. Card entrance and hover | Feedback | Staggered fade-up once per load, 3 px lift on hover | Motion / CSS |
| C. Filter transitions | Shows what changed | Layout animation when cards reorder | Motion `layout` |
| C. Chart transitions | Continuity | Recharts built-in animation | Recharts |
| C. Skeletons | Perceived speed | Yes, content-shaped | shadcn Skeleton |
| C. Animated counters | Delight on KPI tiles | Overview only, once | Magic UI NumberTicker (Motion) |
| C. Dialogs, drawers, collapse | Feedback | Yes | Radix + Motion |

The rule: motion explains a change; 3D appears where spatial layout carries meaning. Neither ever carries data that is not also available as text.

## 2. Important data rule for the niche map

Links must use raw, explainable data: shared creator tags or shared creators. They must **not** use embedding similarity (the foundation's `semantic_score` is INTERNAL_ONLY) and node size must not encode any restricted score. Position is a layout result and must be labelled as such, not as "closeness in popularity".

## 3. Performance and fallback design

- **Lazy loading:** three.js, R3F, drei and sigma.js live in separate chunks loaded only on the routes that use them, after first paint (`React.lazy`, dynamic `import()`).
- **One WebGL context** at a time; dispose geometry, materials and renderer on unmount (R3F does this; verify with a memory check in tests).
- **Pause** rendering when the canvas is off-screen (IntersectionObserver) or the tab is hidden; R3F `frameloop="demand"` for the niche map.
- **Reduced motion:** `prefers-reduced-motion` turns off the hero field, counters and layout animation; Motion's `useReducedMotion` and `MotionConfig reducedMotion="user"`.
- **No WebGL:** detect before loading; show a static gradient (hero) and a plain sortable list of niches (map).
- **Low-power and mobile:** cap device pixel ratio at 2, cap particle count by viewport width, disable the hero field under 640 px.
- **Budgets to measure:** main-route JavaScript under about 200 KB compressed without the 3D chunk; 3D chunk loaded only on Overview; LCP under 2.5 s and INP under 200 ms on a mid-range laptop (Core Web Vitals "good" thresholds). These are targets, not measurements.

## 4. What stays static

Tables, numbers, filters, metric labels, provenance chips, the Discover grid after its first entrance, and every analytics chart axis. Motion never delays access to data.
