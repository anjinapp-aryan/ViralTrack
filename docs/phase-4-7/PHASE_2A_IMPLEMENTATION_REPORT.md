# Phase 2A: creator discovery, implementation report

Date: 2026-11-14, updated 2026-11-15. Status: committed and pushed by the owner as `3845589` together with the CI repairs; hosted CI follow-up in [POST_FRONTEND_CI_REPORT.md](POST_FRONTEND_CI_REPORT.md) section 7. Scope was read-only: creators list, creator detail and a creator's videos. Nothing here ingests, persists, writes, alerts, calls YouTube or spends quota (the foundation reports 0 units and 0 search calls after every run). The upstream submodule is unchanged at `d872014`.

Authoritative companions: [PHASE_2_CREATOR_INTELLIGENCE_AUDIT.md](PHASE_2_CREATOR_INTELLIGENCE_AUDIT.md) (evidence), [PHASE_2_OPEN_SOURCE_REUSE_AUDIT.md](PHASE_2_OPEN_SOURCE_REUSE_AUDIT.md) (reuse decisions), [PHASE_2_ARCHITECTURE_PROPOSAL.md](PHASE_2_ARCHITECTURE_PROPOSAL.md), [POST_FRONTEND_CI_REPORT.md](POST_FRONTEND_CI_REPORT.md) (hosted CI), [PHASE_2_OWNER_DECISIONS.md](PHASE_2_OWNER_DECISIONS.md).

## 1. What was built

| Part | Result |
|---|---|
| Creators list | `GET /api/v1/creators` (already in D5) used by a new **Creators** page: period and creator-size filters, pagination within the 1000-creator window, DEMO label, the API notes verbatim, and a statement that it is not a creator index and not a ranking |
| Creator detail | `GET /api/v1/creators/{id}` (D5, unchanged fields) used by a new detail page: name, handle, followers and platform upload count as raw values with source and RAW tag; hidden or missing values written out; link to the platform channel |
| Creator videos | **New** `GET /api/v1/creators/{id}/videos` over a new provider method `get_creator_content`, using the foundation's `/api/channels/{id}/velocity` only through the ViralTrack API |
| Navigation | one new sidebar entry, **Creators**; no placeholder for anything not built |

### Profile fields: the three proposed extras were NOT added

`PHASE_2_OWNER_DECISIONS.md` decision 6 proposed three extra raw profile fields: `country` (text), `created_at` (UTC date) and `total_views` (raw count). It is a recommendation, marked neither approved nor rejected, and the task said not to approve fields by assumption. They are therefore **omitted**. The detail page shows only what D5 already approved: followers and upload count. Adding them later is a small change (map three more values, regenerate the contract) and needs only that approval.

## 2. Reuse decisions (fresh audit, 2026-11-14)

| Capability | Decision | Evidence |
|---|---|---|
| Creator profile, history, watchlist, alerts, scheduler, notifications | **REUSE** the foundation; nothing rebuilt; history, watchlist and alerts are not touched | audit document; foundation MIT (file read), pushed 2026-11-13, pinned `d872014` |
| Creators list | **REUSE** the D5 endpoint | existing code |
| Per-creator video list | **ADAPT**: the foundation's velocity route is the only source; ViralTrack maps four raw fields and discards the rest | route signature; live read |
| Creator page UI, cards | **COMPOSE** from shadcn components, the Discover `VideoCard`, `QuickView`, `Pager`, `ResultsHeader`, `MetricValue` and the shared state components | existing frontend |
| Typed client | **REUSE** `openapi-typescript` and `openapi-fetch` (regenerated types) | existing |
| Creator tracker projects on GitHub | none usable: 3 small repositories with no licence, 0 to 3 stars, nothing for two other queries | `gh search repos` today |
| Chart library | not needed in 2A (no history chart) | none added |
| **BUILD**, small and ViralTrack-specific | the raw-only video mapping with local ordering, the endpoint, the two pages | no existing code knows this policy |

No dependency was added to either the Python or the web project.

## 3. API and data mapping

`GET /api/v1/creators/{creator_id}/videos?period=all|Nd&page&page_size&platform`

| Rule | Implementation |
|---|---|
| Source | foundation `GET /api/channels/{id}/velocity?period&limit`, after `GET /api/channels/{id}` (the profile read, so an unknown creator is a 404: the foundation answers an empty list with 200 for any id) |
| Fields read | `videoId`, `title`, `publishedAt`, `views` only (`mapping.CREATOR_VIDEO_FIELDS`) |
| Fields discarded | `vphLifetime`, `vph24h`, `viewsGained24h`, `acceleration`, `trend`, `isShort`, `ageHours`, `snapshots`, any other key, and the foundation's `note` |
| Never available in this list | likes, comments, duration, thumbnail, language, category: all `null`, never defaulted |
| Order | **by ViralTrack**: `published_at` newest first, then video id; undated videos last. The foundation orders this list by `vph24h` (verified live: 115.4, 87.1, 59.0 with dates out of order), so its order is never used and cannot leak through a tie or a duplicate |
| Duplicates | the first copy in ViralTrack's order is kept; a note says how many were dropped |
| Window | at most 200 videos (`CREATOR_CONTENT_WINDOW`; the foundation has no cap and does per-video queries); `page x page_size <= 200` or 422 |
| Missing views | metric absent, shown as "views not reported"; a reported 0 stays 0 |
| Missing date | `published_at: null`; the retrieval or collection time is never substituted |
| Content type | always `video`: the foundation's `isShort` is RESTRICTED and ignored |
| Provenance | views are RAW (`youtube-data-api`), origin from the deployment (DEMO labelled), `collected_at` null because the foundation reports no read time |
| Total | known only when fewer videos came back than asked for |
| Response | the same `Page[Video]` envelope and the same response guard as every other list; `extra=forbid` schemas, so the upstream payload cannot be echoed |
| Errors | unknown creator 404, bad input 422 before any request, malformed foundation answer 502, unreachable 503, timeout 504; no internal detail in messages |

Two further changes came from the audit and tests:
- A new platform-neutral capability `creator_content` (domain), listed in `/api/v1/capabilities`; a provider without it raises `UnsupportedCapability`.
- **A boundary defect fixed in existing code:** `_path_id` quoted the id but left `.` and `..` alone, so a provider call with the id `..` sent `/api/channels/..`, which the HTTP client resolves to `/api`. The D5 API already blocked it with its id pattern, so nothing was exposed, but the provider now refuses `.` and `..` itself (test added).

The OpenAPI contract changed (one path, the capability, a description) and `docs/api/openapi-v1.json` and the web types were regenerated; the snapshot test passes.

## 4. Policy confirmation

| Rule | Status |
|---|---|
| No restricted score, grade, momentum, projection, revenue range, YPP or outlier value | none is read, mapped, returned or rendered; tests assert key and text absence on API and UI |
| No engagement or velocity sorting | the only list order is publication date (videos) and the existing views-based creator order; no sort parameter exists on either, and a sort in the URL is ignored |
| No unsupported historical claims, no invented timestamps | no history shown; `collected_at` stays null |
| No zero for missing values | tested at provider, API and UI level |
| No new tables, ingestion, watchlist writes, alerts | none |
| No live call | none; quota 0 |
| Thumbnails | none: avatars are initials, video thumbnails are placeholders, and the browser recorded no image request |

## 5. Verification

| Check | Result |
|---|---|
| New backend tests (`tests/test_creators_2a.py`) | 86 collected at first, 167 after the adversarial id tests of 2026-11-15; offline 165 passed, 2 skipped (the real-foundation tests) |
| Network-isolated job list (the CI job's exact files) with database and foundation | 519 passed, 0 failed, 0 skipped, 0 xfailed; the gate passes with the new minimums (`test_api_d5.py` 152, `test_creators_2a.py` 86) |
| Backend, full suite offline | 1042 passed, 143 skipped (database, foundation, POSIX), 0 failed |
| Backend, full suite with PostgreSQL 16 + pgvector and the pinned foundation | **1180 passed, 5 skipped, 0 failed**. Skipped and not run: 3 POSIX-only tests (Windows) and 2 live-foundation smoke tests (`VT_TEST_FOUNDATION_URL` not set) |
| Ruff, `pip check` | clean |
| OpenAPI snapshot | consistent |
| Frontend tests (Vitest in Chromium, axe) | **128 passed**, 0 failed, 0 skipped (36 new: URL parameters, every state of both pages, policy and navigation, accessibility) |
| TypeScript, ESLint, Prettier, production build | clean; build succeeds |
| Dependency audit | production: no known vulnerabilities; whole tree: no high or critical (2 moderate, dev tooling) |
| Browser (Chromium, live demo stack) at 1440, 1664, 834 and 390 px, dark and light | grid columns 4, 5, 2, 1; no horizontal overflow; axe: 0 violations on Creators, detail and quick view in both themes |
| Keyboard | Tab reaches a creator card, Enter opens it; Escape closes the video quick view; back link works |
| States verified in the browser | unknown creator ("not in the collected data"), API down, loading, filtered-empty |
| External requests | none (only 127.0.0.1); API paths called: `health/ready`, `creators`, `creators/{id}`, `creators/{id}/videos` |
| Image requests | 0 |
| Quota | 0 units, 0 search calls |

Defects found and fixed during verification: a light-theme colour contrast of 4.41:1 on the avatar initials (now darker), the `..` path-segment boundary above, a duplicated "Videos" heading, an API path quoted in user-facing text, and a stray separator in the results line. Test-side mistakes (two ambiguous text matches, a test that rendered two apps) were corrected in the tests, not the code.

Screenshots: `docs/phase-4-7/phase-2a-screens/` (Creators dark 1440 px, creator page light 1440 px, Creators light 834 px, creator page dark 390 px).

## 6. Known limitations

1. **The creators list is derived from discovered videos** (first 1000 by views for the filters), not a creator index; the page says so. A creator with no matching collected video does not appear.
2. **A creator's video list is a window of at most 200** newest collected videos with only title, date and views. Likes, comments, length and thumbnail are unavailable from this source; the page and the API notes say so.
3. **`has_more` and `total` are unknown at the window edge**, as in D5.
4. **Real-data behaviour is untested:** hidden follower counts, partly missing counts and upstream zeros for unreported video or view counts (see the audit) need the D7 real-data check. Demo data cannot show them.
5. **No history, growth, watchlist or alert views.** They need D6 and decisions listed in `PHASE_2_OWNER_DECISIONS.md`.
6. The API is still unauthenticated and local only.
7. Hosted CI: the first run on this work (`43619693337`) was red for two causes outside 2A's code (lockfile check design, a model download in an offline test); see `POST_FRONTEND_CI_REPORT.md` section 7.

## 7. Missing values and zeros (2026-11-15 review)

ViralTrack never turns a missing value into 0: every mapper returns `null` for an absent or non-numeric value, and a reported 0 stays 0 (tested at provider, API and UI level). It can only keep the difference where the foundation still has it.

| Value | What the foundation stores when YouTube omits it | What ViralTrack shows |
|---|---|---|
| Creator followers (hidden subscriber count) | `null` (`subscribersHidden`) | "hidden or not reported" |
| Video likes, comments (hidden or absent) | `null` | not reported |
| Video views | **0** (`int(stt.get("viewCount", 0) or 0)` in `collecting.py`, at collection and at refresh) | 0, because the difference is gone before ViralTrack reads it |
| Creator upload count (`videoCount`) | **0** (same pattern) | 0, same reason |
| Creator total views (`viewCount`) | **0** (same pattern) | not shown (decision 6 not approved) |
| Chart-entry views | **0** (same pattern) | not used |

**Unresolved upstream behaviour.** For video views and the upload count, an omitted value and a real zero are stored identically by the foundation, so no layer above it can tell them apart. This is not changed here: the submodule is not modified, and a fix belongs upstream or in a ViralTrack-side collection path. Next steps, both needing a decision: the D7 real-data check (decision 11) to see whether YouTube ever omits these fields for public items, and, if it does, either a UI note on zero counts of channels that have other data (audit finding 3) or an upstream issue. Until then a 0 for views or uploads means "0 or not reported by the platform".
