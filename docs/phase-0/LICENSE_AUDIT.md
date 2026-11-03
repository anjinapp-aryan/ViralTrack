# License Audit

Method: read the actual `LICENSE` file at the cloned commit (not the GitHub badge), compared it
against the README and package metadata, and ran `pip-licenses` on the installed dependency trees
of the two Python finalists. This is an engineering screen, not legal advice. Anything marked
"legal review" needs counsel before it ships.

## Policy applied

- **Approved:** MIT, Apache-2.0, BSD-2/3-Clause, ISC, 0BSD, Unlicense.
- **Conditional:** LGPL and MPL dependencies used unmodified as libraries (normal for psycopg2,
  certifi, tqdm).
- **Not approved for code reuse:** GPL/AGPL (forces ViralTrack's license), non-commercial,
  source-available (BUSL), proprietary, and **no license file**.
- **Separate hard gate:** a permissive code license does **not** make the data a project collects
  legitimate. Platform terms are judged separately in [PLATFORM_DATA_AUDIT.md](PLATFORM_DATA_AUDIT.md).

## Repository licenses (verified from the LICENSE file at the inspected commit)

| Repository | Commit | LICENSE file says | Code reuse | Platform/data gate | Notes |
|---|---|---|---|---|---|
| pandich93/youtube-niche-finder | d872014 | MIT (c) 2026 Fozil Umarov | **APPROVED** | PASS (official YouTube API), with a retention caveat | README says the author plans a hosted SaaS; MIT still allows a fork |
| shkuratovdesigner/yuben-app | cd57c04 | MIT | **APPROVED** | PASS (official YouTube API) | |
| theograe/open-outlier | 84e4e1f | MIT | **APPROVED** | PASS (official YouTube API) | Root `package.json` also says MIT |
| xeronsh/viral-shorts | 7cabe62 | MIT | APPROVED | PASS | Tiny |
| saawezali/youtube-trends-analyser | fcf4596 | MIT | APPROVED | PASS | Tiny |
| slaavass/youtube-outlier-finder | 73b3fd7 | MIT | APPROVED | PASS | |
| earlyaidopters/signal-room-starter | 37deeb0 | MIT | APPROVED | n/a (synthetic data) | |
| cadenburleson/social-dash | c1e99c5 | MIT | APPROVED | Depends on the RapidAPI provider chosen (unofficial for TikTok/IG) | |
| tenfoldmarc/content-dashboard | d75bdd2 | MIT | APPROVED | Mixed: IG Graph API (own account) plus Apify competitor scraping | README contains an instruction block aimed at AI agents (see deep audit) |
| instaloader/instaloader | 7acd1b6 | MIT | APPROVED (code) | **FAIL**: automated collection from Instagram outside Meta APIs | |
| davidteather/TikTok-Api | 9963059 | MIT | APPROVED (code) | **FAIL**: TikTok ToS bars automated extraction without written approval | |
| Evil0ctal/Douyin_TikTok_Download_API | 5aa0352 | Apache-2.0 (+NOTICE) | APPROVED (code) | **FAIL** (same ToS issue); README puts compliance on the operator | |
| socai-io/jev-social | 2f02e6f | MIT | Conditional | **FAIL** for a hosted product: drives the end user's logged-in Chrome | Needs the separate `socai CLI` binary; its license was not verified |
| w-avw/instagram-viral-reels-research-claude-skill | a6d8475 | MIT | APPROVED (method) | **FAIL**: calls IG private web endpoints with a session | |
| Jakeschincariol/instagram-agent-skill | d03c56b | MIT | APPROVED | Depends on how data is captured | Prompts only |
| knma78/creator-intelligence-core | 8ddea8d | Apache-2.0 (+THIRD_PARTY_NOTICES) | APPROVED | Mixed (CN platform logins) | Out of scope |
| obris-dev/openmagpie | 9967975 | Apache-2.0 | APPROVED | Mixed | Out of scope (text listening) |
| Zivsteve/trendgetter-app | c528678 | MIT | APPROVED | Dead endpoints | Abandoned 2022 |
| miku/ttarc | 3dfecdb | MIT | APPROVED | Endpoint dead since 2020 | |
| yt-dlp/yt-dlp | — | Unlicense | APPROVED (code) | Per-URL extraction; not a discovery source; ToS-sensitive | |
| sansan0/TrendRadar | 946f52a | **GPL-3.0** | NOT APPROVED for embedding | n/a | Out of scope anyway (CN hot lists) |
| james-see/spry | — | **GPL-3.0** | NOT APPROVED | — | Out of scope |
| NanmiCoder/MediaCrawler | 68d9ef1 | **NON-COMMERCIAL LEARNING LICENSE 1.1** | **REJECTED** | — | Commercial use prohibited |
| eisenjimmy/Veyra | 1a811ef | **VEYRA PROPRIETARY SOFTWARE LICENSE**, "All rights reserved" | **REJECTED** | — | GitHub reports `NOASSERTION`; most on-target YouTube project, but no rights granted |
| Fearvox/dash-persona | d200b78 | **Business Source License 1.1** (production use needs a commercial license; becomes Apache-2.0 on 2030-03-24) | **REJECTED** | — | |
| lukejbyrne/viral-reels-scout | 596437c | **No license file** | **REJECTED** | — | Only the idea (Apify actors for Reels) may be referenced |
| princepal9120/tkt-cli | 15164b4 | **No license file** (README badge claims MIT) | **REJECTED** | Also implements fingerprint spoofing and region-block evasion | Badge ≠ license |
| drawrowfly/tiktok-scraper | — | No license | REJECTED | — | Abandoned 2023 |
| noikur/youtube-outlier-tracker, anismabaziz/youtube-trending-tracker, UrMacroGuy/Youtube-Trend-Tracker, killua15/outly, Uzairdharejo/CreatorMania-, Ikenna-Iheanaetu/trendpulse, lenichols/creator-intelligence, h296025733-sys/tiktok-creator-intelligence | — | No license | REJECTED | — | |

## Dependency licenses of the finalists

### youtube-niche-finder backend (79 installed packages, `backend/requirements.txt`)

| License family | Count |
|---|---:|
| MIT / MIT-0 / MIT-CMU | 39 |
| BSD-2/3-Clause and BSD variants | 18 |
| Apache-2.0 (and dual Apache/BSD) | 14 |
| PSF, ISC, Zlib/CC0 combo | 4 |
| **LGPL**: psycopg2-binary | 1 |
| **MPL-2.0**: certifi, tqdm (MPL+MIT) | 2 |
| **UNKNOWN metadata**: py_rust_stemmers (via fastembed) | 1 |

`pgserver` was also reported as UNKNOWN. It is not a project dependency: the audit installed it
only to provide Postgres for the test run.

Verdict: **acceptable.** LGPL and MPL libraries used unmodified are standard. Before a
production release, check `py_rust_stemmers` by hand (upstream repo states MIT; the wheel
metadata does not), and check the `fastembed` model weights that the worker downloads
(model licenses are separate from code licenses).

Frontend: plain static JavaScript (no npm dependency tree). Browser extension: plain JavaScript.

### yuben-app backend (68 packages)

Only non-permissive entry: certifi (MPL-2.0, unmodified). **Acceptable.** The frontend (React 19,
Vite, shadcn-style components) was installed with `npm ci`. Its transitive tree was not
license-scanned in this phase.

### open-outlier (npm workspaces)

`license-checker --production` reports only the root workspace as `UNLICENSED`, because the
private root `package.json` has no license field even though the LICENSE file is MIT. No GPL
packages were reported. **Acceptable.**

## Platform and API terms (summary — details in PLATFORM_DATA_AUDIT.md)

| Source | Terms verdict |
|---|---|
| YouTube Data API v3 | Allowed under YouTube API Services Terms and Developer Policies. Storage is limited to 30 days unless the project is approved for the "Analytics & Reporting" derived-metrics amendment (then up to 36 months for statistics). |
| Instagram Graph API (Business Discovery, Hashtag Search) | Allowed after Meta App Review. Data scope is narrow. |
| Instagram scraping (instaloader, private web endpoints, Apify) | Not permitted by Meta's terms without permission. *Meta v. Bright Data* (N.D. Cal. 2024) covered only logged-off public data and Meta's own ToS theory. **Legal review required.** |
| TikTok Research API | Non-commercial academic use only. **Not available** to ViralTrack. |
| TikTok Display API | Only the authorizing user's own videos. |
| TikTok scraping (TikTok-Api, Douyin_TikTok_Download_API, Apify, ScrapeCreators) | US ToS: no automated extraction "except as approved in writing". **Legal review required.** |
| TikTok / YouTube / Instagram embeds (oEmbed, IFrame) | Allowed for front-end display, under each platform's embed terms. |
