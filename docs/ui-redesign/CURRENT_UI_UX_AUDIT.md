# Current UI and UX audit (foundation dashboard)

Date: 2026-11-07. Based on the owner's screenshots of `#/viral` and `#/categories`, the local run on synthetic data, and the source. Not tested: screen readers, keyboard-only use, real thumbnails (the demo has none).

## 1. What works

- Clear left navigation and a consistent page header with niche and period filters.
- A real dark theme and light theme on CSS variables.
- Dense, useful data: a lot of signal per screen.
- No build step: fast to load and easy to read.
- Status in the sidebar footer (corpus size, quota left, history state) is a good pattern.

## 2. What makes it look like a prototype

| # | Problem | Evidence |
|---|---|---|
| 1 | **Badge overload.** A card carries up to seven competing numbers and labels (VPH, multiplier, VSR, label, RPM, trend arrow, "= 1") with equal visual weight | `#/viral` screenshot |
| 2 | **No visual hierarchy on cards.** Title, views, age, "brief · compare" links and creator sit in the same grey at similar sizes | `#/viral` |
| 3 | **Empty thumbnail boxes** take about 45 % of each card when thumbnails are missing; no designed placeholder | `#/viral` ("no thumbnail") |
| 4 | **Unexplained jargon** (VSR, 22.8x, "mega outlier") without inline definition; the scores page exists but is far away | `#/viral`, `/api/scores` |
| 5 | **Flat palette**: one blue accent for bars, buttons and badges; red and green arrows carry meaning without a legend | `#/categories` |
| 6 | **Table typography**: uppercase grey headers, no number alignment by tabular figures, no row emphasis, no sort affordance | `#/categories` |
| 7 | **System font only**, no type scale; headings and body are close in size | `styles.css` |
| 8 | **One breakpoint** (900 px); five fixed columns of cards at desktop | `styles.css` |
| 9 | **No motion** design at all: no loading skeletons, no transitions; content pops in | source |
| 10 | **Accessibility gaps**: six ARIA attributes in the whole shell; cards are not buttons; no reduced-motion rule; contrast of muted grey on near-black is borderline | grep, screenshots |
| 11 | **Brand**: "nf" monogram, emoji favicon | `index.html` |
| 12 | **Navigation length**: 30+ routes in one list, including admin and integration screens beside discovery | `router.js` |

## 3. Policy problems (more serious than looks)

Almost every number that draws the eye on `#/viral` is restricted or held back for ViralTrack (see `CURRENT_FRONTEND_ARCHITECTURE.md` section 5). A redesign that keeps these numbers would be unacceptable, however good it looks. Removing them also fixes problem 1.

## 4. What the redesign must keep

Information density in analytics views, the status footer idea, theme support, fast first paint, and the honest "calculated from your collected data" explanations (for example the note under Popular categories).
