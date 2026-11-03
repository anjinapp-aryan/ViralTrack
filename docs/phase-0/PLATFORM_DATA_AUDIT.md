# Platform Data Audit

Date: 2026-11-03. This file records what data ViralTrack can actually and legitimately obtain.
Statements marked **[official]** were read from the platform's own documentation during this audit.
**[3rd-party]** marks vendor or blog sources, which are less reliable. **[tested]** marks
something observed from this machine.

---

## 1. YouTube — FEASIBLE (official API), with quota and storage-policy limits

### Official capabilities

| Capability | Source of truth | Finding |
|---|---|---|
| Search | `search.list` **[official]** | "100 calls per day. A call to this method has a quota cost of 1 unit in the Search Queries quota bucket." Since 2026-06-01 `search.list` and `videos.insert` have **their own buckets**. The old "100 units per search" model no longer applies. Filters: `regionCode`, `relevanceLanguage`, `publishedAfter`, `order=viewCount/date`, `videoDuration` (short = < 4 min, *not* Shorts), `videoCategoryId`. Warning in the docs: non-relevance order plus date filters "might result in a smaller or incomplete result set". |
| Videos and statistics | `videos.list` (1 unit per call, up to 50 ids) **[official]**; `videos.batchGetStats` (added 2026-06-03, 1 unit, **own 10,000-unit/day bucket**) **[official]** | Views, likes, comments, duration, category, default language, publish time. `batchGetStats` makes stats refreshes almost free. |
| Channels | `channels.list` (1 unit) **[official]** | Subscribers (rounded), total views, video count, self-declared country. |
| Default quota | **[official]** | 10,000 units/day for all other endpoints, plus 100 `search.list` calls/day. Resets at midnight Pacific. More quota requires an **API Compliance Audit** (free). |
| Trending | `videos.list?chart=mostPopular` **[official]** | Since **2025-07-21** this "will feature videos from the Trending Music, Movies, and Gaming charts … in tandem with the deprecation of YouTube's Trending page". **It is no longer a general "what's trending now" feed.** |
| Shorts | **[official]** | **No Shorts flag or filter exists in the API.** Every project in the audit classifies Shorts by duration ≤ 180 s (YouTube raised the limit to 3 min in Oct 2024). This is a heuristic: it misclassifies short horizontal videos. Shorts views now count every start and replay (2025-03-31). From 2026-08-27, views for all formats count "from the first frame". |
| Categories | `videoCategories.list` **[official]** | Per region. |
| Country | `regionCode` **[official]** | Means "can be viewed in" the country, not "popular in" it. Channel `snippet.country` is self-declared and often empty. |
| Language | `relevanceLanguage` **[official]** | A soft relevance hint: other languages still appear. Needs client-side detection (niche-finder uses `langdetect`). |
| Historical metrics | — | **No history endpoint.** History exists only if we snapshot it ourselves. |
| Channel RSS | `youtube.com/feeds/videos.xml` | **[tested]** Returned **HTTP 404** for two valid channel ids from this machine (2026-11-03). niche-finder uses this feed to detect new uploads without spending quota. Treat it as unreliable until re-checked. |
| oEmbed / embed | `youtube.com/oembed` **[tested]** HTTP 200 with title, author and thumbnail, no key. IFrame player **[official policy]** | Embedding is allowed. Must not modify or obscure the player, must check video status before embedding, and must honor Made-for-Kids (tracking off). |
| Key-less API access | **[tested]** | `videos.list` without a key returns 403. An API key (Google Cloud project) is required. |

### Storage, derived metrics and ranking — the most important YouTube constraint

Verbatim from YouTube API Services Developer Policies **[official]**:

- III.E.4: "An API Client must not store statistics retrieved as Non-Authorized Data for more than
  30 days." "After 30 calendar days, the API Client must either delete or refresh the stored data."
  "API Clients may display historical API Data provided that it is presented accurately in context
  of time."
- "Your API Clients must not … (ii) access or use API Data to create new or derived data or metrics."
- Compliance guide, *Don't* list: "Merge or combine YouTube API data with any other data."
  "Gamify channel performance by ranking or tracking views between different channels." "Calculate
  and assign custom 'scores' to channels based on independently calculated averages or ratios."
- Acceptable without approval: "simple mathematical calculations (… addition, subtraction,
  averages, multiplication, division)" over YouTube data only.

**The 2026 exception that makes ViralTrack viable** (Additional policies for derived metrics and data
storage, effective 2026-06-01) **[official]**. Developers can opt in through the quota-extension or
audit form ("Section 5: Use Cases … → Analytics & Reporting"). Once accepted:

- Custom channel scores and ratios are allowed, explicitly including "Ranking channels on a
  leaderboard".
- "Gamification and Leaderboards": "A website displaying a daily or weekly 'Top YouTuber by View
  Growth' leaderboard" is an allowed example.
- Storage: metrics such as views, likes, subscriber count and comment count "for up to 36 calendar
  months". Derived metrics can also be kept 36 months. **Titles, creator names, descriptions and
  comment text stay on the 30-day refresh/delete rule.**
- ViralTrack's own metrics must be visibly distinguished from YouTube API data.

**Implication.** Outlier scores, velocity, acceleration, leaderboards and multi-month history are
all allowed **only after** the Analytics & Reporting amendment is accepted. Until then, keep data
for at most 30 days and stick to simple-math metrics. The "Merge or combine YouTube API data with
any other data" rule also means **a single cross-platform score that blends YouTube with
TikTok/Instagram data needs explicit review**. Side-by-side display is the safe default.

### Can we identify "going viral now" rather than "most viewed"?

**Yes, within the corpus we track.** **No, not as a global firehose.**

- No API lists all new uploads or all fast-risers. Discovery has to be seeded by searches (100 per
  day), tracked channels, categories and related channels.
- "Viral now" = our own snapshots: views gained per hour over 24 h, acceleration, and outlier
  multiple against the channel's median. niche-finder implements exactly this
  (`domain/metrics.py: vph_from_history, acceleration, outlier_vs_median, age_adjusted_outlier`).
  It was **[tested]** on seeded demo data: `/api/channels/{id}/velocity` returned `vph24h`,
  `viewsGained24h`, `acceleration` and `trend`.
- Coverage scales with quota. 100 searches/day × 50 results gives about 5,000 candidate videos/day
  per Google project, and stats refresh through `batchGetStats` costs 1 unit per call. That is
  enough for dozens of niches, not for "all of YouTube".

### Cost

The API itself is **free**. More quota costs nothing, but needs an approved compliance audit
(Google reviews the use case; timelines are not published). Sharding quota across multiple
projects for the same use case is explicitly prohibited.

---

## 2. Instagram — global public Reels discovery: NOT AVAILABLE through official APIs

| Capability | Official route | Finding |
|---|---|---|
| Global public Reels discovery | — | **NOT AVAILABLE through this source.** No official endpoint lists trending or viral Reels across Instagram. |
| Hashtag discovery | Hashtag Search (`ig_hashtag_search`, `top_media`, `recent_media`) **[official]** | Requires App Review, the **Instagram Public Content Access** feature, and a connected Instagram professional account. Limit: **"a maximum of 30 unique hashtags within a 7 day period"** per account. Stories are not supported. The docs do not promise view or play counts on hashtag media. Reels appear in results (the docs mention reels in the `media_url` note). |
| Creator metrics (other accounts) | Business Discovery **[official]** | "Get basic metadata and metrics about other Instagram **professional** accounts" (not personal accounts; not age-gated accounts). The sample returns `followers_count`, `media_count`, and per-media `like_count`, `comments_count`, `view_count` ("view_count includes both paid and organic metrics"). **Usable for watchlist-style tracking of named professional creators**, including our own outlier calculation, but it cannot *discover* unknown creators. |
| Own-account analytics | Instagram Graph API insights | Available. This is **connected-account analytics, not discovery**, and must not be labeled as discovery. |
| Trending audio | — | **NOT AVAILABLE** through any verified official API. Third-party blogs mention an audio API for publishing with cleared tracks, but nothing documents trend discovery. The Trending Audio tab is app-only. |
| Trending topics | — | NOT AVAILABLE officially. Could be derived from our own tracked-creator corpus (captions, hashtags). |
| Historical metrics | — | Only through our own snapshots. Meta platform terms also limit retention (not fully verified this session). |
| Embedding | Instagram oEmbed **[official]** | "Only meant to be used for embedding Instagram content." Using the metadata "for any purpose other than providing a front-end view" (including analytics) "is strictly prohibited". Limit: 1,000 requests/hour. Excludes private, age-restricted and embed-disabled accounts. |

### Unofficial routes found in the open-source audit (all fail the compliance gate)

| Route | Projects | What it gives | Problem |
|---|---|---|---|
| Logged-in web endpoints (`/api/v1/discover/web/explore_grid/`, `/api/v1/tags/web_info/`) | w-avw skill, jev-social | Explore grid, hashtag top 24, reel play counts | Uses a personal session; violates Meta terms; account-ban risk |
| instaloader | instaloader | Profiles, posts and Reels metadata; hashtag and explore need login | Same; rate-limited; login-required features |
| Paid scraping vendors | Apify `apify/instagram-reel-scraper` **[3rd-party]**: "$2.30 per 1,000 results" on Starter ($2.60 Free plan; returns `videoViewCount` and `videoPlayCount`). ScrapeCreators: $0.99–$1.88 per 1k requests | Reels by hashtag, keyword or profile, with plays | Legal exposure shifts but does not disappear. *Meta v. Bright Data* (N.D. Cal., Jan 2024) held that Meta's ToS did not bar **logged-off** scraping of public data. The ruling is narrow and Meta dropped the case. **Legal review required before production.** |

---

## 3. TikTok — global viral discovery: NOT AVAILABLE through any official API for a commercial product

| Capability | Official route | Finding |
|---|---|---|
| Research API (video query, user info) | **[3rd-party, consistent across 5 sources; TikTok's own pages unreachable from this machine]** | Restricted to **non-profit academic researchers** in eligible regions. "Creators, advertisers and commercial users aren't eligible." Research Terms bar commercial use. **NOT AVAILABLE to ViralTrack.** |
| Display API | **[official docs, via search snippets]** | `video.list` needs the user's OAuth consent and returns **that user's own videos** (20 per page). Connected-account only, so it is **not discovery**. |
| Commercial Content API | **[official]** | Ad library search for researchers and the public. Ads only, mostly EU (DSA). Not organic virality. |
| Creative Center (trending hashtags, songs, creators, videos) | Web UI only **[3rd-party]** | No public API. Logged-out view is truncated. Region filters exist. Programmatic scraping falls under the ToS restriction below. |
| Embedding | oEmbed (`/oembed`) and player iframe (`tiktok.com/player/v1/{id}`) **[official docs via search]** | Allowed for display. |
| Automated collection | US Terms of Service **[official, via search snippet]** | Users may not "scrape, crawl, export or otherwise extract any data or content … using any automated system or software … except as approved in writing." The Developer Terms allow automation only as described in the developer docs. |
| Third-party data | Apify `clockworks/tiktok-scraper` **[3rd-party]**: "from $1.70 / 1,000 results" (returns playCount, likes, shares, comments). ScrapeCreators, EnsembleData | Trending feeds, hashtags, sounds, search | Same ToS exposure. **Legal review required.** |

### Reachability finding (important for the target market)

**[tested]** From this machine (2026-11-03): `www.tiktok.com`, `developers.tiktok.com` and
`ads.tiktok.com` **timed out**. The fetch tool's error showed *connection refused* from an AWS
ap-south-1 IP. `youtube.com` and `instagram.com` returned 200. This matches a national-level block
(TikTok is banned in India). Consequences:

- Users in a blocked country cannot play embedded TikTok videos. In-app TikTok playback fails for
  them, whatever the data source.
- Open-source TikTok tools (TikTok-Api, tkt-cli) could not be tested live here. Proxying around a
  national block was **not** attempted and is not recommended.

### Open-source TikTok projects (code is licensed; data access is not)

- `davidteather/TikTok-Api` (MIT, 6.7k stars): `api.trending.videos()`, hashtag, sound, user and
  search. Requires a Playwright browser and an `ms_token` cookie from a logged-in tiktok.com session.
- `Evil0ctal/Douyin_TikTok_Download_API` (Apache-2.0, 21k stars): a self-hosted REST API with an
  identity (cookie) pool. **Its `/{platform}/trending` endpoint does not support TikTok**
  (`TikTok answers UNSUPPORTED_CONTENT`, verified in `src/dtk/api/routes/discovery.py`). It
  supports TikTok search, hashtag posts, sound posts and user posts.

---

## 4. Video playback feasibility

| Platform | Mechanism | Feasible? | Limits |
|---|---|---|---|
| YouTube | IFrame Player API / `youtube.com/embed/{id}` | **Yes** | Policy: don't alter the player; check status; Made-for-Kids handling. None of the three YouTube candidates embeds a player today (all link out), so this is a small UI gap. |
| Instagram | oEmbed (Meta app token) or Instagram's own embed snippet | Yes, display only | No analytics use of oEmbed metadata; embed-disabled, private and age-gated content excluded. |
| TikTok | oEmbed / player v1 iframe | Yes, outside blocked countries | Does not play where TikTok is blocked. |

## 5. Summary table

| Platform | Global discovery | Creator/watchlist tracking | Velocity | History | Trending audio |
|---|---|---|---|---|---|
| YouTube | **Partial**: seeded by search, channels and categories within quota; no global feed | Yes | Yes (own snapshots) | Yes (own snapshots; 30 days, or 36 months if approved) | NOT AVAILABLE |
| Instagram | **NOT AVAILABLE** (officially). Hashtag search: 30 tags/week | Yes, professional accounts only (Business Discovery) | Yes (own snapshots of tracked accounts) | Own snapshots | NOT AVAILABLE |
| TikTok | **NOT AVAILABLE** officially for commercial use | Own connected account only (Display API) | Only through unofficial or vendor data | Only through unofficial or vendor data | NOT AVAILABLE officially (Creative Center UI only) |

## Sources

- YouTube quota costs: https://developers.google.com/youtube/v3/determine_quota_cost
- search.list: https://developers.google.com/youtube/v3/docs/search/list
- Data API revision history: https://developers.google.com/youtube/v3/revision_history
- Developer Policies: https://developers.google.com/youtube/terms/developer-policies
- Compliance guide: https://developers.google.com/youtube/terms/developer-policies-guide
- Derived metrics policy: https://developers.google.com/youtube/terms/derived-metrics-policy
- IG Hashtag Search: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/hashtag-search
- IG Business Discovery: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery
- IG oEmbed: https://developers.facebook.com/docs/instagram-platform/oembed
- TikTok Display API / Embed: https://developers.tiktok.com/docs/en/display-api-overview , https://developers.tiktok.com/docs/en/embed-videos
- TikTok Terms of Service (US): https://www.tiktok.com/legal/page/us/terms-of-service/en
- TikTok Research API (transparency page): https://www.tiktok.com/transparency/en-us/research-api/
- Research API eligibility (3rd-party): https://apidojo.io/blog/tiktok-api/research-api/ , https://imisofts.com/blog/tiktok-api-pricing/
- Apify TikTok scraper: https://apify.com/clockworks/tiktok-scraper ; Apify Reel scraper: https://apify.com/apify/instagram-reel-scraper ; ScrapeCreators: https://scrapecreators.com
- Meta v. Bright Data: https://techcrunch.com/2024/01/24/court-rules-in-favor-of-a-web-scraper-bright-data-which-meta-had-used-and-then-sued ; https://www.mediapost.com/publications/article/393996/meta-abandons-lawsuit-against-bright-data-over-scr.html
- X Corp v. Bright Data: https://www.cnbc.com/2024/05/10/elon-musks-x-loses-lawsuit-against-bright-data-over-data-scraping.html
