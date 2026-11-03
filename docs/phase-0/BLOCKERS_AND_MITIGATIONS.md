# Blockers and Mitigations

Severity: **CRITICAL** (blocks a promised feature or creates legal or policy exposure),
**HIGH** (limits quality or scale), **MEDIUM** (needs work, no exposure).

| # | Blocker | Severity | Root cause | Existing project that helps | Possible alternative | Mitigable? | Remaining limitation | Cost | Complexity |
|---|---|---|---|---|---|---|---|---|---|
| B-1 | Global YouTube discovery | HIGH | No API lists all new or rising videos. `chart=mostPopular` is limited to Music/Movies/Gaming charts since 2025-07-21. `search.list` is capped at 100 calls/day (own bucket since 2026-06-01) | NF: seeded collection by niche queries, tracked channels, category charts; quota guardrails | Request a higher quota via API Compliance Audit; spread seeds across niches; RSS for new uploads (currently 404 here) | **Partly** | Coverage = tracked corpus, not all of YouTube | Free (audit is free) | Low (exists in NF) |
| B-2 | YouTube Shorts discovery | MEDIUM | API has no Shorts flag; `videoDuration=short` means < 4 min | NF, yuben, open-outlier: ≤ 180 s heuristic | Add an aspect-ratio check from thumbnails or the player; `#shorts` in title | **Mostly** | Some misclassification | Free | Low |
| B-3 | Instagram global Reels discovery | **CRITICAL** | No official endpoint for trending or viral Reels. Hashtag Search capped at 30 tags/7 days; Business Discovery needs known pro accounts | None that passes compliance (instaloader, w-avw, jev-social, Apify all scrape) | (a) Official: curated watchlist of professional creators via Business Discovery + limited hashtag search. (b) Licensed vendor data after legal review | **Partly** (watchlist model) | Not "global". Must be labeled "tracked creators". Personal accounts are invisible | Free API; vendor ~$1–2.6 per 1k reels | Medium (new adapter + Meta App Review) |
| B-4 | TikTok global discovery | **CRITICAL** | Research API is academic-only; Display API is own-account only; ToS bars automated extraction without written approval; TikTok unreachable from this machine (likely a national block) | None legitimately (TikTok-Api, Douyin API: ToS; trending unsupported in Douyin API) | (a) Licensed vendor (Apify, ScrapeCreators, EnsembleData) after legal review. (b) A TikTok partnership/approval in writing | **Not at launch** | Feature shown as "NOT AVAILABLE" | Vendor ~$1–1.9 per 1k results; legal review cost | Medium (adapter) once approved |
| B-5 | View velocity | MEDIUM | No API gives views over time; it must come from our own snapshots | NF: worker snapshots + `vph_from_history` + `acceleration` | `videos.batchGetStats` (own 10k-unit bucket) makes frequent refresh cheap | **Yes** | Resolution = snapshot interval; only for tracked videos | Free | Low (exists) |
| B-6 | Historical snapshots and retention | **CRITICAL** (policy) | YouTube: non-authorized statistics ≤ 30 days; derived metrics barred unless the Analytics & Reporting amendment is accepted (then 36 months for statistics; titles still 30 days). NF keeps history and never deletes | NF freshness job (refresh at 25 days) | Apply for the amendment during Phase 1; until approved, enforce 30-day purge of stats history | **Yes** | Until approval: velocity/history windows ≤ 30 days | Free | Low–medium (retention job in the NF fork) |
| B-7 | Trending audio | **CRITICAL** (feature unavailable) | No official API on any of the three platforms | None | TikTok Creative Center (UI only; scraping = ToS issue); vendor data after legal review | **No** (at launch) | Feature marked NOT AVAILABLE | — | — |
| B-8 | Trending topics | MEDIUM | No platform trend-topics API; Google Trends has no generally available public API (alpha access only, unverified this session) | NF keyword momentum + outlier lift over our own corpus | Add a Google Trends source if alpha access is granted | **Yes** (corpus-relative) | Topics reflect our corpus, not the whole platform | Free | Low (exists) |
| B-9 | Country filtering | MEDIUM | `regionCode` means "viewable in", not "popular in"; channel country is self-declared | NF uses both | Label clearly; per-region `chart=mostPopular` for the 3 chart categories | **Partly** | Approximate | Free | Low |
| B-10 | Language filtering | MEDIUM | `relevanceLanguage` is only a hint | NF: langdetect on title/description | — | **Yes** | Short titles misdetect | Free | Low |
| B-11 | API quotas | HIGH | 10,000 units/day + 100 searches/day per project; sharding across projects for the same use is prohibited | NF enforces buckets, reserves worker units, uses `batchGetStats` | Compliance audit → quota extension | **Yes** (with audit) | Audit timeline unknown | Free | Low |
| B-12 | API cost | MEDIUM | YouTube free; IG Graph free; TikTok/IG scraping vendors are paid | — | Budget vendor data only if legal approves | **Yes** | — | Vendor-dependent | — |
| B-13 | Platform restrictions (ToS) | **CRITICAL** | Meta and TikTok terms prohibit unauthorized automated collection | — | Official APIs only at launch; legal opinion before any vendor | **Yes** (by scoping) | IG/TikTok coverage is thin | Legal review | — |
| B-14 | Embedding restrictions | MEDIUM | YouTube: don't modify the player, check status, Made-for-Kids. IG oEmbed: display-only use of metadata. TikTok embeds fail where TikTok is blocked | — (no candidate embeds today) | Official embeds; fall back to a link-out | **Yes** | TikTok playback unavailable in blocked countries | Free | Low (small UI component) |
| B-15 | Data retention restrictions | HIGH | YouTube 30-day / 36-month rules; Meta platform terms (not fully verified this session) | NF freshness job (partial) | Central retention policy in the fork, per source | **Yes** | Must be maintained as policies change | Free | Low–medium |
| B-16 | Local Docker environment | MEDIUM (dev only) | C: drive full → Docker Desktop could not start during Phase 0 | NF has docker-compose ready | Free disk space on C:, or move Docker's WSL data to D: | **Yes** | — | — | Low |

## Blockers mitigated by existing projects

B-1 (partly), B-2, B-5, B-6 (partly — refresh exists, purge does not), B-8, B-9, B-10, B-11 — all
by `youtube-niche-finder`.

## Blockers no open-source project can remove

B-3, B-4, B-7, B-13. These are platform-policy limits, not engineering gaps. Code cannot fix them
legitimately.
