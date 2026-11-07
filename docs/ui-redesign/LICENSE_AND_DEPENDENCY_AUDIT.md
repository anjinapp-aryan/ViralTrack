# Licence and dependency audit for the proposed UI stack

Date: 2026-11-07. Licence text read from each repository's licence file through the GitHub API; npm licence field and direct dependency count from `npm view`. This is a technical audit, not legal advice. Items marked **REVIEW** need a human decision.

## 1. Proposed stack

| Package | Licence (file) | npm licence field | Direct deps | Unpacked size | Notes |
|---|---|---|---|---|---|
| react 19.3.1 | MIT | MIT | 0 | 0.2 MB | |
| vite 8.3.6 | MIT | MIT | — | — | dev only |
| tailwindcss 4.3.5 | MIT | MIT | 0 | 0.8 MB | build time |
| shadcn/ui components | MIT | (copied source) | per component | — | copied into the repo; keep the MIT notice |
| Radix primitives (e.g. `@radix-ui/react-dialog` 1.3.1) | MIT (© WorkOS) | MIT | 15 for dialog | 0.1 MB | |
| @tanstack/react-query, @tanstack/react-table | MIT | MIT | small | — | |
| recharts 3.10.1 | MIT | MIT | 11 | 7.5 MB | pulls d3 modules (ISC) |
| motion 14.10.1 | MIT (© Motion B.V.) | MIT | 2 | 1.0 MB | |
| three 0.187.0 | MIT | MIT | 0 | 21 MB | lazy chunk only |
| @react-three/fiber, @react-three/drei | MIT | MIT | several | — | lazy chunk only; drei pulls further packages, audit at install time |
| sigma 4.0.4 + graphology 0.26.0 | MIT | MIT | 2 + 1 | 3.4 + 2.7 MB | lazy chunk only |
| lucide (React package) | ISC | ISC | 0 | — | GitHub shows NOASSERTION because the file also carries an upstream notice; text is ISC |
| Inter, Geist | SIL OFL 1.1 | OFL | 0 | — | fonts may be used commercially and bundled; they may not be sold on their own; keep the licence file |
| Magic UI / motion-primitives (2 to 3 copied components) | MIT | — | — | — | keep MIT notices in copied files |
| @playwright/test 1.65.0 | Apache-2.0 | Apache-2.0 | 1 | — | dev only |
| axe-core 4.14.0, @axe-core/playwright | **MPL-2.0** | MPL-2.0 | 0 / 1 | 3.4 MB | dev only, unmodified; **REVIEW** (same reasoning as the accepted `certifi`) |

## 2. Rejected for licence reasons

| Project | Licence found | Why rejected |
|---|---|---|
| animate-ui/animate-ui | MIT **+ Commons Clause** (`LICENSE.md`) | Commons Clause removes the right to sell the software or a service whose value derives substantially from it |
| greensock/GSAP | no licence file; README and npm point to GreenSock's "Standard No-Charge License" | Proprietary terms, not an OSI licence; would need separate legal review; Motion covers the need |
| daniel-lundin/react-preloaders | repository not found | cannot verify anything |

## 3. Paid tiers and attribution

- Magic UI has a separate paid "Pro" product; only the MIT open-source components are considered.
- Tremor is Apache-2.0; NOTICE obligations apply if any file is copied (none planned).
- shadcn/ui and Magic UI code copied into the repository must keep their MIT copyright notices; record them in `THIRD_PARTY_NOTICES.md` when implemented.
- Fonts: ship the OFL text with the font files.

## 4. Transitive dependencies

Only direct counts were read. A full tree (`npm ls --all` and a licence scanner) must run at install time, in the first implementation milestone, with the `license-audit` skill. Expected copyleft-adjacent transitive items to watch: none known for this stack, but drei and recharts pull several packages that have not been reviewed.

## 5. Security

No advisory database was queried in this audit. At install time run `npm audit` and record the result; pin exact versions in the lockfile.

## 6. Platform data is separate

None of these licences says anything about YouTube data. Thumbnails: ViralTrack maps `thumbnail_url` from the API and shows the image from YouTube's servers; it never downloads or stores it (`VT_THUMBNAILS_APPROVED=false`). Whether hot-linking API thumbnails in a commercial UI is acceptable under the YouTube API terms is a **REVIEW** item for counsel (owner decision 4).
