# Repository Deep Audit

Every serious candidate was cloned at the commit shown, and its source (not its README) was
checked for each claim. "Verified" means the code path was found and, where noted, executed.
Test outcomes are detailed in [LOCAL_TEST_RESULTS.md](LOCAL_TEST_RESULTS.md).

Metadata snapshot: GitHub API, 2026-11-03.

## A. YouTube discovery applications

| Category | pandich93/youtube-niche-finder | shkuratovdesigner/yuben-app | theograe/open-outlier | xeronsh/viral-shorts |
|---|---|---|---|---|
| URL | github.com/pandich93/youtube-niche-finder | github.com/shkuratovdesigner/yuben-app | github.com/theograe/open-outlier | github.com/xeronsh/viral-shorts |
| Commit audited | d872014 (2026-10-25) | cd57c04 (2026-11-01) | 84e4e1f (2026-07-19) | 7cabe62 (2025-11-30) |
| Purpose | Self-hosted YouTube niche, outlier and velocity research platform ("NexLev/vidIQ alternative") | On-demand outlier research for a topic, with LLM narrative | Outlier finder + collections for tracked channels | MCP tool: trending Shorts + views per hour |
| Platform | YouTube only | YouTube only | YouTube only | YouTube only |
| Complete application? | **Yes** (worker, DB, API, dashboard, extension, MCP, multi-user) | Yes (single-user, local) | Yes (MVP) | No (MCP tool) |
| Frontend | Static JS dashboard, 27 sections, i18n, plus a Chrome extension | React 19 + Vite + Tailwind, mock-first UI | Next.js | None (Claude Desktop) |
| Backend | Python FastAPI + worker + MCP (100 tools), Telegram/e-mail alerts | Python FastAPI, LLM adapters (13 providers) | Fastify (TS), node-cron scheduler, MCP, CLI, SDK | Python MCP |
| Database | PostgreSQL + pgvector. Tables include `videos`, `video_stats_history`, `channel_stats_history`, `tracked_channels`, `saved_items`, `events`, `chart_snapshots`, `users`, `plans` | SQLite (`config`, `history`, `results`) | SQLite (31 tables: lists, tracked_channels, saved_outliers, boards, alerts…) | None |
| License | MIT | MIT | MIT | MIT |
| Stars / forks | 24 / 4 | 19 / 2 | 1 / 0 | 1 / 0 |
| Contributors | 3 (GitHub) — effectively one author | 2 | 1 | 1 |
| Repo age / commits | Created 2026-09-05; 317 commits | Created 2026-07-11; 55 commits | Created 2026-04-03; 18 commits | Created 2025-11-26 |
| Last meaningful commit | 2026-10-25 (pushed 10-30) | 2026-11-01 | 2026-07-19 | 2025-11-30 |
| Releases | 5 (v0.5.0 2026-10-23) | 0 | 0 | 0 |
| Automated tests | ~150 test files; **1,784 pass / 2 fail locally** | **459 pass / 0 fail** | 6 tests (2 pass; 4 fail on Windows only) | 2 files |
| CI/CD | GitHub Actions: ruff, doc-link check, lockfile check, Playwright smoke, pytest+coverage on pgvector, Docker build, release workflow | Actions: Ubuntu/Windows/macOS × Py 3.10/3.13 | None | None |
| Docker | docker-compose (postgres, web, worker, mcp, mcp-http) + prod compose | No (Python launcher) | No | No |
| Documentation | Extensive (self-hosting, HTTP API reference generated from code, privacy, security) | Good (PRD, contracts, build plan) | Moderate | README |
| Data source | YouTube Data API v3 (`search.list`, `videos.list`, `videos.batchGetStats`, `channels.list`, `playlistItems`, `chart=mostPopular`); channel RSS for new uploads; optional YouTube Analytics OAuth for own channel | YouTube Data API v3 + transcripts (`youtube-transcript-api`) | YouTube Data API v3 + OpenAI | YouTube Data API v3 `search().list` |
| API requirements | `YOUTUBE_API_KEY`; optional LLM (OpenRouter/Ollama), Google OAuth, Telegram | YouTube key + any LLM key | `YOUTUBE_API_KEY` (mandatory at boot), `OPENAI_API_KEY` | YouTube key |
| Platform restrictions | Enforces quota buckets in code (refuses to exceed 100 searches/day; reserves worker units) | Shows the estimated quota before each run (~1.4k units) | — | — |
| Maintenance | Very active (daily commits) | Active | Stalled since July | Stalled |
| Actual working status | **PASS WITH LIMITATIONS** (demo seed; no live key) | PASS WITH LIMITATIONS | PASS WITH LIMITATIONS | NOT TESTED |
| Viral discovery | **Verified**: `/api/viral` funnel (views vs subs, outlier multiple, age-adjusted) | Verified in source: VSR = views ÷ subscribers, engagement sanity filter | Verified in source: outlier score + momentum | VPH + engagement |
| Shorts | Verified: `is_short` = duration ≤ 180 s; Shorts and long-form baselines kept separate | Shorts mode | `getContentType` ≤ 180 s | Yes (claimed) |
| Reels / TikTok | No / No | No / No | No / No | No / No |
| Historical metrics | **Verified**: `video_stats_history`, `channel_stats_history` snapshots by the worker | Run history only (no metric time series) | No time series (current `view_velocity` column only) | No |
| Velocity | **Verified**: `vph_from_history`, `acceleration`; endpoint returned `vph24h`, `viewsGained24h`, `acceleration`, `trend` | No | Single-scan velocity | VPH from lifetime |
| Outlier detection | **Verified**: median baseline over the previous N uploads, age-adjusted with a fitted maturity curve | VSR multiple | Yes | No |
| Trend detection | Keyword/n-gram momentum and "outlier lift", niche trend (growing/stable/cooling/saturated), language gaps, `chart=mostPopular` snapshots | No | Similar topics | "Track trending topics" (thin) |
| Dashboard | Yes (27 sections) | Yes | Yes | No |
| Country / language / category filters | Region, category, language (langdetect) | Region preference + channel country | — | — |
| Saved / watchlists / alerts | `saved_items` + folders / `tracked_channels` / `events` + Telegram, e-mail, digest | History | Collections / tracked channels / `alerts` table | No |
| Reuse potential | **Very high (foundation)** | Medium (on-demand research mode, LLM adapter pattern) | Low–medium (UI ideas; small codebase) | Low |
| Missing capabilities | Instagram, TikTok, cross-platform model, in-app playback, retention enforcement (see risks) | History, velocity, alerts | History, tests, maintenance | Nearly everything |

### youtube-niche-finder — risks found in source

1. **Retention policy conflict.** `backend/application/freshness.py`: "Nothing is deleted, here
   or anywhere else (the user's call, 2026-10-04) … Keeping data longer than 30 days without
   refreshing it, or keeping history, is the installation owner's own risk." The worker refreshes
   rows after 25 days, but **stats history is kept indefinitely**. That is compliant only if the
   Google project is approved for the 36-month derived-metrics/storage amendment. ViralTrack must
   add a retention job, or obtain that approval, before production.
2. **Derived metrics without approval.** Outlier scores, revenue estimates and niche scores are
   "derived metrics" under YouTube policy. They are allowed only after the Analytics & Reporting
   amendment is accepted.
3. **Bus factor.** Effectively one author, two months old, mostly agent-assisted development
   (CLAUDE.md, AGENTS.md, `.claude/`). Code quality and tests are high, but a long-lived fork must
   assume ViralTrack may maintain it alone.
4. **Upstream is going SaaS.** The README announces a hosted service with tariffs. MIT still allows
   forking, but the projects will compete. Upstream contributions may still be welcome.
5. **Locale.** Some code comments and log strings are in Russian; there is a default
   `TZ=Asia/Tashkent`. Cosmetic. i18n with an English locale exists.
6. **Channel RSS dependency.** New-upload detection uses `youtube.com/feeds/videos.xml`, which
   returned 404 from this machine. The fallback (`playlistItems`) costs quota.

## B. Instagram / TikTok / cross-platform

| Category | Evil0ctal/Douyin_TikTok_Download_API | davidteather/TikTok-Api | instaloader/instaloader | socai-io/jev-social | tenfoldmarc/content-dashboard | cadenburleson/social-dash | w-avw/instagram-viral-reels-research-claude-skill |
|---|---|---|---|---|---|---|---|
| Commit | 5aa0352 | 9963059 | 7acd1b6 | 2f02e6f | d75bdd2 | c1e99c5 | a6d8475 |
| Purpose | Self-hosted data API for Douyin/TikTok/Bilibili | Unofficial TikTok wrapper | IG downloader + metadata | LLM-directed IG/TT/LinkedIn research in the user's browser | Creator command center | Own-account analytics UI | Agent skill: find viral reels, transcribe, script |
| Platform | TikTok, Douyin, Bilibili | TikTok | Instagram | IG, TikTok, LinkedIn | IG (+ competitors) | YT, TT, IG | IG |
| Complete application? | Yes (API + React console + workers) | Library | Library + CLI | CLI app | Yes (Next.js + Supabase) | Yes (SPA) | No (skill) |
| Database | Postgres/TimescaleDB + Redis | None | None | Local files | Supabase (20 tables) | localStorage | Files |
| License | Apache-2.0 | MIT | MIT | MIT (needs external `socai CLI`) | MIT | MIT | MIT |
| Stars / forks / contributors | 21,112 / 2,938 / 6 | 6,726 / 1,225 / 38 | 13,762 / 1,646 / 75 | 195 / – / – | 2 / 1 / 1 | 4 / 0 / 1 | 6 / 0 / 1 |
| Last commit / releases | 2026-11-01 / 67 | 2026-08-23 / 100+ | 2026-11-01 / 100+ | 2026-10-12 / yes | 2026-06-03 / 0 | 2026-03-19 / 0 | 2026-08-19 / 0 |
| Tests / CI | 4,393 tests; CI + CodeQL | 13 test files (live); CI | 1 test; CI | Tests + CI | None | None | None |
| Docker | Yes (compose, browser/downloader/transcriber images) | Dockerfile | No | No | No (Vercel) | Yes | No |
| Data source | Platform web/app endpoints with a managed cookie "identity pool" | Playwright session + `ms_token` | IG web GraphQL (login for hashtag/explore) | User's logged-in Chrome | IG Graph API (own) + Apify scraping (competitors) | RapidAPI providers | IG private web endpoints via session |
| Platform restrictions | Violates TikTok ToS without written approval | Same | Violates Meta terms | Same, through the user's own account | Competitor scraping → Apify ToS exposure | Depends on provider | Violates Meta terms |
| Working status | Unit/replay tests PASS (3,553/55 on Windows); live NOT TESTED | FAIL as tested; live NOT TESTED | Import only | NOT TESTED | NOT TESTED | Build PASS | NOT TESTED |
| Viral discovery | Search, hashtag, sound posts; **TikTok trending UNSUPPORTED** (source verified) | `trending.videos()` | Hashtag/explore (login) | Search + open posts | Competitor "viral hooks" | No (own posts) | 5× outlier rule |
| Trending sounds | Sound → posts (not a trend ranking) | Sound → videos | No | No | No | No | No |
| Historical / velocity | Watchlist + scheduler (snapshots possible) | No | No | No | Snapshots of own posts | Auto-refresh only | No |
| Reuse potential | Code: high quality. **Data route rejected** unless legal approval | Rejected (data route) | Rejected (data route) | Rejected for hosted use | UI ideas only | UI ideas only | Method only (outlier-vs-own-account rule) |
| Missing capabilities | YouTube, IG, compliance | Everything above the wrapper | Everything above the library | Persistence, dashboard | Discovery | Discovery | App |

**Prompt-injection finding.** `tenfoldmarc/content-dashboard/README.md` contains an HTML-comment
block headed "AI ASSISTANT BOOTSTRAP — if you are an AI agent … do EXACTLY this", telling agents to
clone it, `npm install`, and follow its own setup skill. It was ignored during this audit. Any
future agent-assisted work on candidate repos should treat README content as untrusted.

## C. Rejected after inspection (short form)

| Repository | Reason (evidence) |
|---|---|
| eisenjimmy/Veyra | `LICENSE`: "VEYRA PROPRIETARY SOFTWARE LICENSE … All rights reserved." Closest to the "accelerating videos / breakout topics" goal, but no rights granted. |
| NanmiCoder/MediaCrawler | `LICENSE`: "NON-COMMERCIAL LEARNING LICENSE 1.1". Also targets Chinese platforms only. |
| Fearvox/dash-persona | BUSL-1.1; production use needs a commercial license until 2030-03-24. |
| sansan0/TrendRadar | GPL-3.0; aggregates Chinese hot lists (Weibo, Douyin, Zhihu…) and news, not YT/IG/TT video discovery. |
| lukejbyrne/viral-reels-scout | No license file. Data from Apify actors. |
| princepal9120/tkt-cli | No license file despite the MIT badge; implements browser-fingerprint spoofing and region-block evasion. |
| miku/ttarc | README: the trending endpoint has returned an empty list since 2020-04-23. |
| Zivsteve/trendgetter-app | Last code 2020–2022; dead endpoints. |
| Jakeschincariol/instagram-agent-skill | Prompts/skills only. `ig-viral` ranks data the user captures by hand. |
| earlyaidopters/signal-room-starter | Synthetic data only ("Every … metric … included here is synthetic"); the ranker is "an educational example". A possible UI reference, not a foundation. |
| knma78/creator-intelligence-core | Single-video analysis for Bilibili/Douyin/XHS/YouTube; not trend discovery. |
| obris-dev/openmagpie, obsei/obsei | Text social listening (mentions), not video virality. |
| saawezali/youtube-trends-analyser | 14-file Streamlit app over `chart=mostPopular`, which since 2025-07-21 covers only Music/Movies/Gaming charts. |
