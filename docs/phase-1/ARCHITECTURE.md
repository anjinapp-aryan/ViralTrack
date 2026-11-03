# Architecture (end of Phase 1)

Legend: **[IMPLEMENTED]** exists and is tested · **[PLANNED]** designed, not built ·
**[UNSUPPORTED]** no legitimate data source · **[EXTERNAL]** third-party code or service.

```text
                             ViralTrack
                                 |
             +-------------------+-------------------+
             |                                       |
      Platform Layer  [IMPLEMENTED]          Intelligence  [PLANNED, Phase 2+]
      viraltrack/providers                   (breakout scores, baselines, trends:
             |                                not built; Phase 1 passes niche-finder's
   +---------+-----------+                    own derived values through, labelled DERIVED)
   |         |           |                               |
 YouTube  Instagram    TikTok                            |
 [IMPL.]  [PLANNED:    [UNSUPPORTED:                     |
   |      official     no commercial                     |
   |      Graph API    discovery API;                    |
   |      watchlist]   scraping rejected]                |
   |                                                     |
   +-----------------> Normalized Model <----------------+
                       viraltrack/domain  [IMPLEMENTED]
                       Content / Creator / Metric + Provenance (RAW vs DERIVED)
                                 |
                          Persistence
                          niche-finder Postgres  [EXTERNAL, adopted]
                          + ViralTrack retention job  [IMPLEMENTED]
```

## YouTube path, in detail

```text
ViralTrack domain              viraltrack/domain                     [IMPLEMENTED]
      |
      v
Provider interface             viraltrack/providers/base.py           [IMPLEMENTED]
      |                        PlatformProvider + PlatformCapabilities
      v
YouTube adapter                viraltrack/providers/youtube/          [IMPLEMENTED]
      |   HTTP GET only, documented endpoints:
      |   /api/viral  /api/search  /api/channels/{id}  /api/channels/{id}/history
      v
Adopted foundation             upstream/youtube-niche-finder @d872014 [EXTERNAL, unmodified]
      |   web (FastAPI + dashboard), worker (collection, snapshots, alerts),
      |   postgres (pgvector), mcp
      v
YouTube Data API v3            googleapis.com                         [EXTERNAL]

Retention job                  viraltrack/retention                   [IMPLEMENTED]
      '--> SQL on the foundation's Postgres (daily, docker compose `retention`)
```

## Runtime (docker compose)

| Service | Owner | Status |
|---|---|---|
| `postgres` (pgvector/pgvector:pg16) | foundation | [IMPLEMENTED, reused] |
| `web` (API + dashboard, :8080) | foundation | [IMPLEMENTED, reused]. Tested in Docker on :8090 |
| `worker` (collection, refresh, alerts) | foundation | [IMPLEMENTED, reused]. Not started in Phase 1 because there is no YouTube key |
| `mcp`, `mcp-http`, `ollama` | foundation | Available. Not used |
| `retention` (daily) | ViralTrack | [IMPLEMENTED] |

## What is not in this architecture yet

ViralTrack has no web UI or API of its own: the foundation's dashboard is the UI (see UI_REUSE_DECISION.md).
It has no own persistence: the normalized model is built on read and not stored, so no second copy of
YouTube data needs a retention policy. Alerts, velocity and breakout logic beyond what the foundation already
provides are Phase 2+.
