# Final Adoption Decision

**Decision:** FORK `pandich93/youtube-niche-finder` (MIT) as ViralTrack's foundation. Add a
thin adapter and labeling layer (COMPOSE official APIs). BUILD only five small gaps. REJECT
unofficial Instagram/TikTok collection for launch.

Status: **proposed, awaiting owner approval.** Phase 1 has not started.

## The question

> "If we wanted to launch ViralTrack with the minimum amount of original code, which existing
> open-source projects should we reuse, fork, adapt and compose?"

## The answer

| Layer | Use | Strategy | Original code needed |
|---|---|---|---|
| YouTube discovery, outliers, Shorts, velocity, history, trends, niches, creators, country/language filters | `pandich93/youtube-niche-finder` @ v0.5.0+ | **FORK** (track upstream; send generic fixes upstream) | None |
| Database, worker, dashboard, alerts (Telegram/e-mail/digest), saved items, watchlists, multi-user auth, MCP, Chrome extension | same | **FORK** | None |
| YouTube data | YouTube Data API v3 (official), incl. `videos.batchGetStats` | **COMPOSE** | None (NF client exists) |
| Retention policy (30 days, or 36 months once Google approves) | NF `application/freshness.py` | **ADAPT** | Small purge job + config flag |
| Video playback | YouTube IFrame API; Instagram oEmbed; TikTok oEmbed | **COMPOSE** | Small player component |
| Instagram | Meta Graph API: Business Discovery (watchlist of professional creators) + Hashtag Search (30 tags/7 days) | **COMPOSE** + thin **BUILD** adapter | Medium adapter inside the fork's collector pattern |
| Cross-platform | Side-by-side lists from the shared `source`-tagged tables | **BUILD** (thin) | Small |
| Provenance labels ("not from YouTube"; "tracked creators only"; "NOT AVAILABLE") | Policy requirement | **BUILD** (thin) | Small |
| TikTok discovery, trending audio (all platforms), global Instagram Reels discovery | — | **REJECT** at launch; displayed as NOT AVAILABLE | None |
| On-demand topic research with LLM narrative (optional, later) | `shkuratovdesigner/yuben-app` (MIT, 459/459 tests) | **REUSE** as a reference/sidecar, only if needed | None until chosen |

**Not adopted:** Veyra (proprietary), MediaCrawler (non-commercial), DashPersona (BUSL),
TrendRadar (GPL, off-scope), viral-reels-scout and tkt-cli (no license), instaloader, TikTok-Api,
Douyin_TikTok_Download_API and jev-social (data routes violate platform terms; code licenses
are fine).

## Conditions attached to this decision

1. **YouTube policy.** File the API Compliance Audit with the "Analytics & Reporting"
   derived-metrics amendment early in Phase 1. Until it is accepted, the fork must purge
   non-authorized statistics after 30 days, and must label outlier and velocity numbers as
   ViralTrack metrics.
2. **No blended cross-platform score** until Google's response clarifies the "merge or combine
   YouTube API data with any other data" rule for the approved use case.
3. **Legal review** before any Instagram or TikTok vendor data (Apify, ScrapeCreators,
   EnsembleData). Without written approval, those adapters are not built.
4. **Fork hygiene.** Rebase on upstream regularly. Keep ViralTrack changes in clearly separated
   modules (`sources/`, retention, player, labels) so upstream merges stay cheap.

## Estimated reuse

- **22 of 40** listed requirements (55 %) are delivered by the fork as-is, verified by endpoints and
  tests on demo data.
- **7** need thin builds: 5 Instagram adapter rows, comparison view, player.
- **11** are **not legitimately available** (global IG Reels discovery, IG trending audio and
  topics, all 7 TikTok rows).
- Of everything that *can* be built legitimately (29 rows), **~76 % by row count is reused**. By
  implementation effort it is roughly 90 %, because the reused rows are the heavy ones (worker,
  history, scoring, dashboard, auth, alerts).

## Recommended Phase 1 (exact action)

1. Free disk space on C: (or move Docker Desktop's WSL data to D:) so Docker can start.
2. Fork `pandich93/youtube-niche-finder` into the ViralTrack GitHub account. Use the
   `anjinapp-aryan/ViralTrack` repo (currently empty) as the fork's home, or keep a separate fork
   and point ViralTrack to it — owner's choice.
3. Create a dedicated Google Cloud project and YouTube Data API key. Run the fork unchanged with
   `docker compose up -d postgres web worker` on 3 target niches for 7 days. Measure: outlier
   precision (manual review of the top 50), velocity signal quality, quota use per niche.
4. Submit the YouTube API Compliance Audit with the Analytics & Reporting amendment (derived
   metrics + 36-month storage).
5. Only after steps 3–4: implement the retention job and source labels (small), then the player
   component.
6. In parallel, **non-code**: obtain a legal opinion on Instagram/TikTok vendor data; create a Meta
   app and start App Review for Instagram Public Content Access and Business Discovery.

Phase 1 must start with the permanent rule:
**SEARCH → VERIFY → LICENSE CHECK → TEST → REUSE → ADAPT → COMPOSE → BUILD ONLY THE GAP.**
