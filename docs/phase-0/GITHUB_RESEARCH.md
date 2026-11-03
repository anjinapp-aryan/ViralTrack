# GitHub Research Log

Date: 2026-11-03. Method: `gh search repos` (GitHub REST search) plus `gh api` for per-repo
metadata (contributors, releases, workflows, tree scan for tests, Docker and license files).
Raw search output is kept outside the repo, in the Phase 0 sandbox
(`D:\WORK_SPACE\_vt_phase0_sandbox\search\`, `all.json`, `meta.txt`).

## Counts

| Stage | Count |
|---|---:|
| Search queries run | 42 (33 best-match + 9 star-sorted) |
| Unique repositories surfaced by the 33 best-match queries | 408 |
| Additional repositories from the 9 star-sorted queries | ~75 |
| Repositories screened by README/description (relevant, recent, non-clipper) | ~245 |
| Repositories with full metadata pulled (stars, forks, contributors, releases, CI, tests, Docker, license) | 43 |
| Repositories cloned and source-inspected | 25 |
| Repositories installed and test-run locally | 7 |

## Queries

Best-match (30 results each): viral video finder · viral video discovery · viral shorts ·
youtube outlier finder · youtube outlier · youtube niche finder · youtube shorts analytics ·
instagram viral reels · reels discovery · reels scraper · tiktok viral finder · tiktok trends ·
tiktok trending dashboard · social media trend dashboard · social media intelligence ·
creator intelligence · content intelligence · trend intelligence · breakout video detection ·
outlier video detection · social trend monitoring · viral content dashboard ·
cross-platform trend dashboard · youtube trending tracker · youtube view velocity ·
trending videos aggregator · social listening open source · influencer discovery platform ·
viral content research · youtube analytics self-hosted · tiktok scraper · instagram scraper ·
yt-dlp social media scraper dashboard.

Star-sorted: MediaCrawler · TrendRadar · topic:youtube-analytics · topic:social-listening ·
topic:trend-analysis social · viral reels tiktok youtube dashboard ·
tiktok instagram youtube trending videos · tiktok creative center · youtube trending api history.

## What the search landscape looks like

1. **No complete cross-platform viral-discovery product exists in open source.** Every
   "social media trend dashboard" hit (about 20 repos) is a student or Power BI project on a static
   CSV with 0–1 stars and no license.
2. **YouTube is the only platform with mature, licensed, complete applications.** At least six
   2026 projects implement "outlier" discovery on the official YouTube Data API. One of them
   (`pandich93/youtube-niche-finder`) is a full product: worker, Postgres history, velocity, alerts,
   dashboard, MCP, extension, CI.
3. **Instagram and TikTok projects are scrapers or agent skills, not products.** They depend on
   unofficial endpoints, logged-in browser sessions, or paid scraping vendors (Apify,
   ScrapeCreators, RapidAPI, EnsembleData).
4. **"Viral shorts" mostly means AI clippers.** Hits like `mutonby/shortcast`,
   `NaufalRizqullah/opensource-clipping` and `SamurAIGPT/ai-clipping-generator` cut long videos into
   shorts. They are out of scope (video editing / generation).
5. **The most on-target projects have licenses that block reuse.** Veyra ("accelerating videos,
   breakout topics") is proprietary. MediaCrawler (70k stars) is non-commercial. DashPersona is BUSL.

## Screened repositories (relevant set)

Legend for Verdict: **DEEP** = cloned and audited in [REPOSITORY_DEEP_AUDIT.md](REPOSITORY_DEEP_AUDIT.md);
**META** = metadata and README screened; **REJ-L** = rejected on license; **REJ-S** = rejected on scope or quality.

| # | Repository | Stars | License | Last push | Platform | What it is | Verdict |
|---|---|---:|---|---|---|---|---|
| 1 | pandich93/youtube-niche-finder | 24 | MIT | 2026-10-30 | YT | Full self-hosted outlier/velocity/niche product | DEEP (top) |
| 2 | shkuratovdesigner/yuben-app | 19 | MIT | 2026-11-01 | YT | Local-first on-demand outlier research (VSR) + LLM narrative | DEEP |
| 3 | theograe/open-outlier | 1 | MIT | 2026-07-19 | YT | Fastify+Next.js+SQLite outlier finder, collections | DEEP |
| 4 | xeronsh/viral-shorts | 1 | MIT | 2025-12-02 | YT | MCP server: Shorts + VPH from YouTube API | DEEP |
| 5 | saawezali/youtube-trends-analyser | 0 | MIT | 2025-08-13 | YT | Streamlit over `chart=mostPopular` | DEEP |
| 6 | slaavass/youtube-outlier-finder | 6 | MIT | 2026-07-25 | YT | CLI: Shorts outlier channels | DEEP |
| 7 | eisenjimmy/Veyra | 14 | Proprietary | 2026-08-08 | YT | Electron "accelerating videos, breakout topics" | REJ-L |
| 8 | lukejbyrne/viral-reels-scout | 0 | None | 2026-05-16 | IG/TT/YT | Apify-backed local dashboard | REJ-L |
| 9 | w-avw/instagram-viral-reels-research-claude-skill | 6 | MIT | 2026-08-19 | IG | Agent skill using IG web endpoints via logged-in session | DEEP |
| 10 | Jakeschincariol/instagram-agent-skill | 4,513 | MIT | 2026-09-13 | IG | 13 Claude skills; `ig-viral` ranks captured reels | DEEP |
| 11 | instaloader/instaloader | 13,762 | MIT | 2026-11-01 | IG | Mature IG downloader/metadata library | DEEP |
| 12 | cadenburleson/social-dash | 4 | MIT | 2026-03-19 | YT/IG/TT | Own-account analytics UI over RapidAPI | DEEP |
| 13 | tenfoldmarc/content-dashboard | 2 | MIT | 2026-06-03 | IG (+comp.) | Next.js+Supabase creator command center | DEEP |
| 14 | Zivsteve/trendgetter-app | 16 | MIT | 2022-12-11 | YT/TT | React Native trending viewer (abandoned) | DEEP |
| 15 | davidteather/TikTok-Api | 6,726 | MIT | 2026-08-24 | TT | Unofficial TikTok wrapper (Playwright, ms_token) | DEEP |
| 16 | Evil0ctal/Douyin_TikTok_Download_API | 21,112 | Apache-2.0 | 2026-11-02 | TT/Douyin/Bili | Self-hosted scraping data API, identity pool | DEEP |
| 17 | NanmiCoder/MediaCrawler | 69,915 | Non-commercial | 2026-10-27 | CN platforms | Crawler for XHS/Douyin/Kuaishou/Bili | REJ-L |
| 18 | sansan0/TrendRadar | 63,369 | GPL-3.0 | 2026-10-29 | CN hot lists | Hot-list aggregator + alerts | DEEP (REJ-S) |
| 19 | socai-io/jev-social | 195 | MIT | 2026-11-01 | IG/TT/LinkedIn | LLM-directed research through user's Chrome | DEEP |
| 20 | knma78/creator-intelligence-core | 5 | Apache-2.0 | 2026-10-21 | YT/CN | Single-video research desktop app | DEEP (REJ-S) |
| 21 | Fearvox/dash-persona | 7 | BUSL-1.1 | 2026-05-14 | multi | Creator analytics engine | REJ-L |
| 22 | earlyaidopters/signal-room-starter | 10 | MIT | 2026-08-22 | generic | Creator-intelligence UI starter, synthetic data | DEEP |
| 23 | obris-dev/openmagpie | 83 | Apache-2.0 | 2026-10-14 | X/YT/Reddit/HN | Social listening (text) | DEEP (REJ-S) |
| 24 | miku/ttarc | 2 | MIT | 2026-09-30 | TT | Trending archiver; endpoint dead since 2020 | DEEP (REJ-S) |
| 25 | princepal9120/tkt-cli | 2 | None (README claims MIT) | 2026-06-17 | TT | TikTok CLI with fingerprint/region-block evasion | REJ-L |
| 26 | drawrowfly/tiktok-scraper | 5,243 | None | 2023-05-19 | TT | Abandoned scraper | REJ-L |
| 27 | naseif/tiktok-scraper | 115 | MIT | 2026-06-20 | TT | Scraper library | META |
| 28 | omkarcloud/tiktok-scraper | 18 | MIT | 2026-10-23 | TT | Scraper (vendor funnel) | META |
| 29 | yt-dlp/yt-dlp | 204,790 | Unlicense | 2026-10-29 | all | Per-URL metadata/downloader | META |
| 30 | JangHyuckYun/mcp-youtube-intelligence | 53 | Apache-2.0 | 2026-10-29 | YT | Transcripts/channel monitoring MCP | META (REJ-S) |
| 31 | nickpending/prismis | 14 | MIT | 2026-11-01 | RSS/Reddit/YT | Personal content-priority daemon | META (REJ-S) |
| 32 | james-see/spry | 44 | GPL-3.0 | 2026-10-30 | multi | Username OSINT CLI | META (REJ-S) |
| 33 | obsei/obsei | 1,444 | Apache-2.0 | 2026-11-01 | text | Voice-of-customer pipeline | META (REJ-S) |
| 34 | noikur/youtube-outlier-tracker | 0 | None | 2026-07-05 | YT | Full-stack outlier tracker | REJ-L |
| 35 | VigneshSM79/content-intelligence | 0 | MIT | 2026-05-19 | YT | Next.js+Hono outlier finder | META |
| 36 | anismabaziz/youtube-trending-tracker | 2 | None | 2026-10-22 | YT | Airflow+Postgres daily mostPopular | REJ-L |
| 37 | UrMacroGuy/Youtube-Trend-Tracker | 0 | None | 2026-04-06 | YT | Trend engine | REJ-L |
| 38 | DerickBeckwith/youtube-outlier-scan | 0 | MIT | 2026-09-08 | YT | 5-file script | META (REJ-S) |
| 39 | killua15/outly | 0 | None | 2026-04-07 | YT | Outlier finder + AI | REJ-L |
| 40 | BrandonChin827/youtube-outliers-claude-code | 2 | MIT | 2026-09-28 | YT | Skill on ScrapeCreators | META |
| 41 | StevenBuglione/creator-intelligence | 0 | MIT | 2026-10-16 | YT | MCP research server | META |
| 42 | Uzairdharejo/CreatorMania- | 1 | None | 2026-05-08 | multi | AI viral research (15 files) | REJ-L |
| 43 | Ikenna-Iheanaetu/trendpulse | 1 | None | 2026-05-06 | YT | Daily trend agent | REJ-L |
| 44 | lenichols/creator-intelligence | 0 | None | 2026-08-19 | TT | TikTok opportunity analysis | REJ-L |
| 45 | muqeing/phone-viral-radar | 0 | Apache-2.0 | 2026-09-02 | Android apps | Phone-automation research | META (REJ-S) |
| 46 | h296025733-sys/tiktok-creator-intelligence | 57 | None | 2026-10-08 | TT | Creator vetting for e-commerce | REJ-L |
| 47 | crieck2010/survey-trends | 0 | MIT | 2026-10-10 | TT | Creative Center sounds digest (keyless scrape) | META |
| 48 | souravjain540/tiktok-trends | 7 | None | 2024-10-07 | TT | Creative Center hashtag scrape | REJ-L |
| 49 | Avnsh1111/Instagram-Reels-Scraper-Auto-Poster | 315 | GPL-3.0 | 2026-08-16 | IG | Scrape + repost reels | REJ-S |
| 50 | XPOZpublic/xpoz-agent-skills | 16 | MIT | 2026-09-09 | multi | Skills over the Xpoz commercial API | META |
| 51 | pandich93 alternatives: johanfortus/Niche-Finder | 22 | MIT | 2025-06-04 | YT | Notebook | META (REJ-S) |
| 52 | ~20 "social-media-trends-dashboard" repos | 0–1 | None | 2025–2026 | — | Static CSV / Power BI student projects | REJ-S |

## Observations on evidence quality

- Star counts are a poor signal here. `Jakeschincariol/instagram-agent-skill` has 4.5k stars and
  941 forks within two months but is 44 files of prompts, with one author and no tests.
  `pandich93/youtube-niche-finder` has 24 stars and is the most complete engineering in the set
  (317 commits, about 150 test files, CI with coverage, Docker, releases).
- Many 2026 repositories in this space are AI-agent-generated (AGENTS.md / CLAUDE.md, single
  author, fast commit bursts). That is not disqualifying, but it makes bus-factor and long-term
  maintenance the main risk even for the best candidates.
