# Reuse Matrix

Strategy vocabulary: **REUSE** (use as-is), **FORK** (take the codebase and maintain changes),
**ADAPT** (change an existing project's code), **COMPOSE** (combine existing services/APIs),
**BUILD** (write new code — only for gaps), **REJECT** (not doing it / not available legitimately).

"NF" = `pandich93/youtube-niche-finder` (fork target). Evidence for each NF capability is the code
path or endpoint verified in [REPOSITORY_DEEP_AUDIT.md](REPOSITORY_DEEP_AUDIT.md) and
[LOCAL_TEST_RESULTS.md](LOCAL_TEST_RESULTS.md).

| Requirement | Existing project | Existing capability | Missing capability | Reuse strategy |
|---|---|---|---|---|
| YouTube viral videos | NF | `/api/viral`: outlier multiple vs channel median, age-adjusted, subs/views funnel (verified) | Real-data validation; derived-metric approval from Google | **FORK** (NF as-is) |
| YouTube Shorts | NF (also yuben, open-outlier) | `is_short` ≤ 180 s, separate Shorts baselines (verified) | API has no Shorts flag, so this is a heuristic everywhere | **FORK** (NF); accept the heuristic, label it |
| Instagram Reels | — (instaloader, w-avw skill, Apify: all fail the compliance gate) | Official: Business Discovery returns `view_count` and likes for **named professional accounts**; Hashtag Search 30 tags/7 days | Global Reels discovery: **NOT AVAILABLE** officially | **COMPOSE** (Meta Graph API: watchlist of pro creators + limited hashtag search) + **BUILD** a thin adapter; **REJECT** global discovery claims |
| TikTok videos | — (TikTok-Api, Douyin API: fail the compliance gate) | Official APIs give only own-account (Display) or academic (Research) data | Commercial discovery: **NOT AVAILABLE** officially | **REJECT** for launch; re-open as **COMPOSE** (licensed vendor) only after legal approval |
| Video playback | YouTube IFrame / oEmbed; IG oEmbed; TikTok oEmbed/player | Official embeds; YouTube oEmbed tested (200) | None of the candidates embeds a player (they link out) | **COMPOSE** (official embeds) + **BUILD** a small player component in the NF frontend |
| Trending topics | NF | `/api/keywords` n-gram momentum + outlier lift; niche trend states; language gaps (verified on demo) | Cross-platform topics | **FORK** (NF) for YouTube; **BUILD** only if IG data is added |
| Trending audio | — | None on any official API (YT none; IG none; TikTok Creative Center UI only) | Everything | **REJECT** (report "NOT AVAILABLE through this source") |
| View velocity | NF | `vph_from_history`, `acceleration`, `/api/channels/{id}/velocity` (verified) | — | **FORK** (NF) |
| Historical metrics | NF | `video_stats_history`, `channel_stats_history` snapshots | Retention enforcement (30 days, or 36 months once approved) | **ADAPT** NF: add a retention/purge job tied to the approval status |
| Outlier detection | NF (yuben, open-outlier as alternatives) | Median-baseline outlier, fitted maturity curve (verified) | — | **FORK** (NF) |
| Creator discovery | NF | `/api/outlier-channels`, collabs, competitor tracking | IG creators: watchlist only (Business Discovery) | **FORK** (NF) for YT; **COMPOSE** Meta Graph API for IG |
| Country filtering | NF | `regionCode` + channel country | API semantics are soft ("viewable in") | **FORK** (NF); document the semantics in the UI |
| Language filtering | NF | `relevanceLanguage` + langdetect on titles | — | **FORK** (NF) |
| Niche filtering | NF | Niches, niche clusters (pgvector embeddings), ranking, saturation | — | **FORK** (NF) |
| Saved videos | NF (open-outlier collections as an alternative) | `saved_items` + folders, `/api/saved` | IG/TikTok items | **FORK** (NF) |
| Watchlists | NF | `tracked_channels`, alerts on new outlier/acceleration | IG creators | **FORK** (NF); **ADAPT** to accept an IG source |
| Alerts | NF | `events` + dashboard + Telegram + e-mail digest + extension | — | **FORK** (NF) |
| Cross-platform ranking | — | — | No project does it. YouTube policy bars merging YouTube API data with other data in derived metrics unless approved | **BUILD** (thin), **side-by-side only** at launch; blended score **REJECTED** until Google's audit response |

## Overall reuse estimate

| Scope | Requirements | Covered by an existing project (verified) | Share |
|---|---:|---:|---:|
| YouTube (YT-1…YT-13) | 13 | 13 (NF) | **100 %** of requirements; ~90 % of implementation (playback and retention are the gaps) |
| Cross-platform (X-1…X-11) | 11 | 9 (NF, YouTube-only today: dashboard, viral/trend/creator/topic ranking, bookmarks, watchlists, alerts, historical trends) | ~80 %. X-2 comparison and X-11 playback are thin builds |
| Instagram (IG-1…IG-9) | 9 | 0 reusable OSS that passes the compliance gate. 5 rows feasible via the official API (IG-3 for known accounts, IG-4, IG-5, IG-8 limited, IG-9) | Feasible rows need a **new adapter** |
| TikTok (TT-1…TT-7) | 7 | 0 legitimately | **NOT AVAILABLE** at launch |
| **Whole product** | 40 | 22 reusable (NF) + 7 thin builds (5 IG adapter rows, X-2, X-11) + 11 unavailable (IG-1, IG-2, IG-6, IG-7, TT-1…TT-7) | **55 % of the full wish-list reusable today (22/40); ~90 % of the legitimately buildable scope (22/29 rows reused, the rest thin builds)** |
