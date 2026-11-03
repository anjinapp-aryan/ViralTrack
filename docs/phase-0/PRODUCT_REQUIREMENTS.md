# ViralTrack — Product Requirements (Phase 0 baseline)

Status: research baseline, 2026-11-03. No application code exists. This file restates the
requirements that the Phase 0 audit measured existing projects against.

## Product definition

ViralTrack is a **viral-content discovery and trend-intelligence platform** for creators.

Core workflow: **DISCOVER → FILTER → WATCH → ANALYZE → TRACK → IDENTIFY OPPORTUNITIES**

Out of scope as a primary goal: publishing/scheduling, video editing, news aggregation, plain
hashtag tracking, own-account analytics dashboards, AI content generation.

## Requirement inventory

Each requirement has an ID used by [REUSE_MATRIX.md](REUSE_MATRIX.md) and
[BLOCKERS_AND_MITIGATIONS.md](BLOCKERS_AND_MITIGATIONS.md).

### YouTube

| ID | Requirement |
|---|---|
| YT-1 | Viral video discovery (outperforming videos, not just most-viewed) |
| YT-2 | Trending video discovery |
| YT-3 | Recently published popular videos |
| YT-4 | Fast-growing videos (velocity / acceleration) |
| YT-5 | YouTube Shorts discovery |
| YT-6 | Channel discovery |
| YT-7 | Creator outlier detection |
| YT-8 | View velocity |
| YT-9 | Historical metrics |
| YT-10 | Category filtering |
| YT-11 | Country filtering |
| YT-12 | Language filtering |
| YT-13 | Niche filtering |

### Instagram

| ID | Requirement |
|---|---|
| IG-1 | Reels discovery |
| IG-2 | Viral Reels discovery |
| IG-3 | Creator discovery |
| IG-4 | Reels metrics (views/plays) |
| IG-5 | Engagement metrics |
| IG-6 | Trending audio |
| IG-7 | Trending topics |
| IG-8 | Hashtag discovery |
| IG-9 | Historical metrics |

### TikTok

| ID | Requirement |
|---|---|
| TT-1 | Viral video discovery |
| TT-2 | Trending video discovery |
| TT-3 | Creator discovery |
| TT-4 | Engagement metrics |
| TT-5 | Topic discovery |
| TT-6 | Trending sounds |
| TT-7 | Historical metrics |

### Cross-platform

| ID | Requirement |
|---|---|
| X-1 | Unified dashboard |
| X-2 | Cross-platform comparison |
| X-3 | Viral ranking |
| X-4 | Trend ranking |
| X-5 | Creator ranking |
| X-6 | Topic ranking |
| X-7 | Video bookmarking |
| X-8 | Watchlists |
| X-9 | Alerts |
| X-10 | Historical trend tracking |
| X-11 | In-app video playback (embed) |

## Non-functional requirements

| ID | Requirement |
|---|---|
| NF-1 | Every data source must be legitimately obtainable (platform terms, API policy) |
| NF-2 | Every reused component must carry an approved license (MIT, Apache-2.0, BSD, ISC, 0BSD preferred) |
| NF-3 | "Global discovery" may only be claimed where the source actually provides it |
| NF-4 | Stored platform data must respect each platform's retention rules |
| NF-5 | Local/self-hosted deployment (Docker) for development |

## Accuracy rule (from the project constitution)

If a platform does not provide a capability, ViralTrack reports it as **NOT AVAILABLE through
this source**. Connected-account analytics are never relabeled as global discovery.
