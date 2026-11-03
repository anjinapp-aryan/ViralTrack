# Proposed Architecture (evidence-based, not yet implemented)

Derived from [ADOPTION_OPTIONS.md](ADOPTION_OPTIONS.md): **fork youtube-niche-finder, add a
thin source-adapter and labeling layer, and build only the gaps.** Nothing here is built in Phase 0.

## Component map

```text
                       ┌───────────────────────────────────────────────┐
                       │  ViralTrack UI  (= NF static dashboard, fork)  │
                       │  + player component (YT IFrame / IG,TT oEmbed) │  BUILD (small)
                       │  + source labels & side-by-side platform view │  BUILD (small)
                       └───────────────▲───────────────────────────────┘
                                       │ HTTP (NF FastAPI, existing)
┌──────────────────────────────────────┴───────────────────────────────────────┐
│  NF backend (FORK of pandich93/youtube-niche-finder, MIT)                      │
│  application/: discovery, outliers, velocity, trends, alerts, saved, niches   │  REUSE
│  domain/metrics.py: outlier_vs_median, vph_from_history, acceleration          │  REUSE
│  freshness.py  + NEW retention job (30 d, or 36 mo once Google approves)       │  ADAPT
│  NEW sources/ seam:  source = youtube | instagram | (tiktok: disabled)         │  ADAPT (thin)
└───────▲──────────────────────────────▲───────────────────────────▲────────────┘
        │                              │                           │
  YouTube Data API v3            Meta Graph API               TikTok
  (existing NF client:           Business Discovery +          NOT AVAILABLE at launch
   search.list 100/day,          Hashtag Search (30/7d)        (Research API academic-only;
   videos.list, batchGetStats,   via a connected IG            scraping = ToS). Vendor
   channels.list, mostPopular)   professional account          adapter only after legal OK
        REUSE                        BUILD adapter (medium)          REJECT for now
        │
  PostgreSQL + pgvector (NF schema: videos, video_stats_history, channel_stats_history,
  tracked_channels, saved_items, events, ...)  REUSE  — new rows tagged with `source`
  Worker (NF, docker-compose service)          REUSE
```

## Key decisions and the evidence behind them

| Decision | Evidence |
|---|---|
| NF is the system of record | Only complete, MIT, tested (1,784 pass) product covering 13/13 YouTube requirements |
| Keep NF's stack (Python FastAPI, Postgres+pgvector, static JS UI, docker-compose) | Rewriting the stack would discard verified code. Constitution Rule #1 |
| Add a `source` dimension instead of a new service | Keeps one database and one worker. IG data volume (30 hashtags/week, watchlist creators) is small |
| Instagram = watchlist model, not discovery | Business Discovery covers named professional accounts only; no official global Reels feed |
| TikTok disabled at launch | Research API is non-commercial; Display API is own-account; ToS bars scraping; TikTok unreachable from the dev machine |
| No blended cross-platform score at launch | YouTube compliance guide: "Merge or combine YouTube API data with any other data" is listed under *Don't*. Revisit after the Analytics & Reporting amendment review |
| Retention job is mandatory | YouTube III.E.4: non-authorized statistics ≤ 30 days; 36 months only after the amendment is accepted. NF currently never deletes |
| Official embeds for playback | YouTube IFrame / oEmbed (oEmbed tested: 200); IG oEmbed display-only; TikTok oEmbed |
| Label every derived metric | Derived-metrics policy: "You must distinguish these metrics from metrics sourced from API Data" |

## Environments

- **Local dev:** NF `docker-compose.yml` (postgres, web, worker, mcp). It needs Docker Desktop
  working, which means freeing space on C: or moving Docker's data root to D:.
- **Secrets:** `YOUTUBE_API_KEY` (Google Cloud project dedicated to ViralTrack); Meta app ID/secret
  and IG professional-account token when the IG adapter starts.

## What is explicitly NOT in this architecture

A custom scoring engine (NF has one), a new frontend framework, a new database, AI agents,
authentication from scratch (NF ships multi-user, sessions, MFA), trend algorithms beyond NF's,
and any scraper.
