# Top 10 Candidates — Scored

Weights: Requirement coverage 25 · License 15 · Data accessibility 20 · Stability 10 · Tests 10 ·
Deployment 5 · Maintenance 5 · Documentation 5 · Integration effort 5 = 100.

**Hard gates** (pass/fail, independent of score): (L) license approved for code reuse;
(P) the project's data route is legitimate for a commercial ViralTrack. A candidate that fails a
gate cannot be the foundation, whatever it scores.

"Requirement coverage" is measured against the **whole** ViralTrack requirement set (YouTube +
Instagram + TikTok + cross-platform), so YouTube-only tools cannot score above about 60 % on it.

| Rank | Repository | Cov 25 | Lic 15 | Data 20 | Stab 10 | Tests 10 | Deploy 5 | Maint 5 | Docs 5 | Integ 5 | **Total** | Gate L | Gate P | Role |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:-:|:-:|---|
| 1 | pandich93/youtube-niche-finder | 15 | 15 | 14 | 7 | 9 | 5 | 5 | 5 | 3 | **78** | ✅ | ✅* | **Foundation (YouTube engine)** |
| 2 | shkuratovdesigner/yuben-app | 8 | 15 | 15 | 6 | 9 | 3 | 5 | 5 | 4 | **70** | ✅ | ✅ | Reference / optional on-demand research mode |
| 3 | Evil0ctal/Douyin_TikTok_Download_API | 7 | 15 | 4 | 8 | 9 | 5 | 5 | 5 | 3 | **61** | ✅ | ❌ | Not adopted. Re-evaluate only if legal approves TikTok collection |
| 4 | theograe/open-outlier | 9 | 15 | 14 | 3 | 3 | 2 | 2 | 4 | 4 | **56** | ✅ | ✅ | UI and collections reference |
| 5 | davidteather/TikTok-Api | 5 | 15 | 3 | 7 | 4 | 4 | 4 | 4 | 4 | **50** | ✅ | ❌ | Not adopted |
| 6 | instaloader/instaloader | 4 | 15 | 3 | 9 | 3 | 3 | 5 | 5 | 3 | **50** | ✅ | ❌ | Not adopted |
| 7 | xeronsh/viral-shorts | 4 | 15 | 12 | 1 | 2 | 1 | 1 | 3 | 4 | **43** | ✅ | ✅ | Superseded by #1 |
| 8 | socai-io/jev-social | 6 | 10 | 4 | 5 | 7 | 2 | 5 | 4 | 1 | **44** | ⚠️ | ❌ | Not adopted (personal-browser automation) |
| 9 | tenfoldmarc/content-dashboard | 6 | 15 | 7 | 2 | 0 | 2 | 2 | 3 | 3 | **40** | ✅ | ⚠️ | UI ideas only |
| 10 | cadenburleson/social-dash | 5 | 15 | 6 | 2 | 0 | 4 | 2 | 3 | 4 | **41** | ✅ | ⚠️ | Unified-dashboard UI reference only |

\* Gate P passes for niche-finder **as data access**. Its default retention behavior ("nothing is
deleted") must change, or Google's derived-metrics/storage amendment must be granted, before
production. See [BLOCKERS_AND_MITIGATIONS.md](BLOCKERS_AND_MITIGATIONS.md) (B-6).

## Why each scored as it did (key evidence)

1. **youtube-niche-finder (78).**
   - Covers 13 of 13 YouTube requirements plus watchlists, saved items and alerts.
   - 1,784 tests passed locally; full CI; Docker; MIT; 317 commits.
   - Points lost: no IG/TikTok, so whole-product coverage is capped; one-author bus factor;
     two months old; large codebase to learn (Integ 3).
2. **yuben-app (70).**
   - Clean, tested (459/459), cross-OS CI, good docs.
   - Narrow scope: on-demand search, no time series, so no velocity or history.
   - Highest data score: stateless, so nothing to retain.
3. **Douyin_TikTok_Download_API (61).**
   - Strong engineering: 4.4k tests, Docker, 67 releases.
   - Its data route is scraping with cookie pools, and TikTok's trending feed is unsupported.
   - Fails Gate P.
4. **open-outlier (56).** Good product shape (collections, tracked channels, MCP, SDK) but one
   contributor, six tests, stalled since July, no history table.
5. **TikTok-Api (50).** The only OSS with a TikTok "trending" call. It needs a logged-in session
   token and a browser, and fails Gate P.
6. **instaloader (50).** Mature and maintained (75 contributors), but hashtag/explore need login
   and it fails Gate P.
7. **viral-shorts (43).** About 25 files; VPH from lifetime views only.
8. **jev-social (44).** Automates the end user's own Chrome. Unsuitable for a hosted product, and
   it depends on a separate `socai CLI` whose license was not verified.
9. **content-dashboard (40).**
   - Instagram own-account (Graph API) plus Apify competitor scraping.
   - No tests.
   - README contains an agent-targeted instruction block.
10. **social-dash (41).** A clean multi-platform UI, but own-account analytics through RapidAPI
    with no tests. Useful only as a layout reference for a unified dashboard.

## Highest-scoring projects excluded by the license gate

| Repository | Would have scored | Blocking license |
|---|---|---|
| eisenjimmy/Veyra | ~60 (most on-target YouTube "acceleration" concept) | Proprietary, all rights reserved |
| NanmiCoder/MediaCrawler | n/a (wrong platforms) | Non-commercial |
| Fearvox/dash-persona | ~45 | BUSL-1.1 |
