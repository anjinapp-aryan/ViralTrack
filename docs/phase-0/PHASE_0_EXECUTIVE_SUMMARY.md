# ViralTrack — Phase 0 Executive Summary

Date: 2026-11-03 · Scope: research, validation and adoption decision only. **No application code
was written, nothing was committed or pushed.**

## Bottom line

1. **Someone has already built most of the YouTube half of ViralTrack.**
   `pandich93/youtube-niche-finder` (MIT) is a complete self-hosted product. It has a worker,
   Postgres history, outlier detection, view velocity and acceleration, Shorts, niches, trends,
   alerts, saved items, watchlists, a dashboard, multi-user auth, a Chrome extension and an MCP
   server. Locally **1,784 of 1,786 tests passed**, and its viral, outlier-channel, keyword and
   velocity endpoints worked on seeded demo data.
2. **Nobody has legitimately built the Instagram or TikTok half, and nobody can yet.**
   - Instagram has no official global Reels discovery. The official API gives only a
     professional-creator watchlist (Business Discovery) and 30 hashtags per week.
   - TikTok's discovery API is academic-only. Its terms bar scraping, and TikTok was unreachable
     from this machine (likely a national block).
   - Every open-source IG/TikTok tool audited scrapes.
3. **Trending audio is not available from any official API** on any of the three platforms.
4. **YouTube policy is the main design constraint.** Velocity, outlier scores, leaderboards and
   stored history are *derived metrics*. Since 2026-06-01 they are allowed only after Google
   accepts the "Analytics & Reporting" amendment (then statistics can be kept 36 months). Until
   then: 30-day storage and simple-math metrics only.

## Recommendation

**FORK** youtube-niche-finder. **COMPOSE** official APIs (YouTube Data API, Meta Graph API, official
embeds). **BUILD** only five small gaps: retention job, player, Instagram official-API adapter,
provenance labels, side-by-side cross-platform view. **REJECT** unofficial IG/TikTok data until a
legal opinion approves a specific vendor.

## Numbers

| Item | Value |
|---|---|
| Repositories surfaced by search | ~480 (408 unique from 33 queries + ~75 star-sorted) |
| Repositories screened (relevant set) | ~245; 52 catalogued in GITHUB_RESEARCH.md |
| Repositories deeply audited (cloned + source) | 25 |
| Repositories installed and tested | 7 |
| Reusable share of requirements | 22/40 (55 %) as-is; ~90 % of the legitimately buildable scope by effort |
| Requirements not legitimately available | 11/40 (global IG Reels, IG audio/topics, all TikTok) |

## Things that went wrong or are unverified

- **Docker was not tested.** The C: drive was full (0 MB free at the start) and Docker Desktop
  would not start.
- **No live data was tested on any platform:**
  - YouTube: no API key in the environment.
  - TikTok: unreachable from this machine.
  - Instagram: scraping deliberately not attempted.
- TikTok's own developer and ToS pages could not be loaded from this machine. TikTok facts come
  from search-indexed copies of TikTok pages and consistent third-party sources.
- YouTube channel RSS feeds returned 404 from this machine. niche-finder uses RSS to detect new
  uploads without spending quota.
- `tenfoldmarc/content-dashboard` contains an instruction block aimed at AI agents in its README.
  It was ignored.
- Meta's general terms page (automated-collection clause) did not render for the fetch tool. The
  Instagram ToS position relies on Meta's API docs and court reporting.

## Documents

[PRODUCT_REQUIREMENTS](PRODUCT_REQUIREMENTS.md) · [GITHUB_RESEARCH](GITHUB_RESEARCH.md) ·
[TOP_10_CANDIDATES](TOP_10_CANDIDATES.md) · [REPOSITORY_DEEP_AUDIT](REPOSITORY_DEEP_AUDIT.md) ·
[LICENSE_AUDIT](LICENSE_AUDIT.md) · [PLATFORM_DATA_AUDIT](PLATFORM_DATA_AUDIT.md) ·
[LOCAL_TEST_RESULTS](LOCAL_TEST_RESULTS.md) · [REUSE_MATRIX](REUSE_MATRIX.md) ·
[BLOCKERS_AND_MITIGATIONS](BLOCKERS_AND_MITIGATIONS.md) · [ADOPTION_OPTIONS](ADOPTION_OPTIONS.md) ·
[PROPOSED_ARCHITECTURE](PROPOSED_ARCHITECTURE.md) · [FINAL_ADOPTION_DECISION](FINAL_ADOPTION_DECISION.md)
