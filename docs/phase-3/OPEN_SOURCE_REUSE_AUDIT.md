# Open-source reuse audit for YouTube discovery (Task C)

Date: 2026-11-05. Read-only. Facts below come from `gh api repos/<repo>` and `gh search repos` run on this date
(licence field, last push, archived flag, stars). Nothing was cloned, installed or executed. Source-level review was
done only for the adopted foundation; for every other project the verdict rests on **listing-level evidence plus
general knowledge of the project (INFERENCE)** and must be re-verified (source, tests, licence file) before adoption.

## 1. Search result

**VERIFIED FACT:** repository searches for "youtube outlier", "youtube viral", "youtube niche finder", "youtube trend
detection" and similar terms return no maintained, permissively licensed *YouTube discovery engine* other than the
already adopted `pandich93/youtube-niche-finder`. The other "niche finder" repositories found are small (0 to 22 stars),
several have no licence, and none was reviewed in depth. Results for "youtube viral" are video-clipping tools
(Shorts generators), not discovery.

**Conclusion:** the discovery engine itself is already reused (the foundation). The open-source question is therefore
about the *missing pieces* (trend statistics, change-point detection, ranking evaluation), not about a replacement engine.

## 2. Comparison

| Project | Licence | Maintenance (last push, stars) | Relevant capability | Integration approach | Verdict |
|---|---|---|---|---|---|
| `pandich93/youtube-niche-finder` (adopted foundation) | MIT | 2026-10-30, 27 | Collection, discovery sections, snapshots, velocity, niches, embeddings, worker, alerts | Already composed over HTTP | **REUSE** (in place) |
| `googleapis/google-api-python-client` | Apache-2.0 | 2026-11-03, 8,968 | Official YouTube Data API client | Not needed: the foundation already calls the API; ViralTrack never calls YouTube directly | **REFERENCE** (do not add) |
| `youtube/api-samples` | none declared (GitHub reports no licence) | 2024-06-09, 6,029 | Official code samples | Read for API behaviour only | **REFERENCE** |
| `parafoxia/analytix` | BSD-3-Clause | 2026-05-06, 45 | YouTube **Analytics** API SDK (owner-authorised channel data, OAuth) | Different data class (Authorized Data of own channels), not discovery | **REJECT for discovery** |
| `pauling-ai/youtube-mcp-server` | MIT | 2026-10-23, 31 | MCP wrapper over Data/Analytics APIs | Duplicates the foundation's MCP; small project | **REFERENCE** |
| `scipy/scipy` | BSD-3-Clause | 2026-11-04, 15,185 | Robust statistics (median, MAD, `scipy.stats`), signal tools | Optional, only inside a ViralTrack scoring module that is policy-cleared | **COMPOSE** (later, if needed) |
| `statsmodels/statsmodels` | BSD-3-Clause | 2026-11-04, 11,737 | Time-series tests, robust regression | Offline evaluation of trend claims | **REFERENCE** (validation use) |
| `deepcharles/ruptures` | BSD-2-Clause | 2026-10-06, 2,108 | Change-point detection | Candidate for "momentum change" once there is enough snapshot history | **REFERENCE** (not before D6) |
| `yzhao062/pyod` | BSD-2-Clause | 2026-10-28, 10,076 | Outlier/anomaly detection | Heavy; per-niche distributions are small, a median/MAD rule is simpler and explainable | **REFERENCE** (do not add) |
| `unit8co/darts` | Apache-2.0 | 2026-11-04, 9,574 | Forecasting | Forecasts are projections; the policy prohibits projecting performance without the amendment | **REJECT now** |
| `Nixtla/statsforecast` | Apache-2.0 | 2026-11-04, 4,961 | Fast statistical forecasting | Same as above | **REJECT now** |
| `meta/prophet` | MIT | 2026-11-05, 20,473 | Forecasting | Same as above; also heavy | **REJECT now** |
| `pgvector/pgvector` | PostgreSQL licence (GitHub reports NOASSERTION; reviewed in Phase 0/1) | 2026-11-03, 23,584 | Vector search | Already used by the foundation | **REUSE** (in place) |
| `pgvector/pgvector-python` | MIT | 2026-10-28, 1,542 | Python bindings | Not needed (foundation owns DB access) | **REFERENCE** |
| `timescale/timescaledb` | NOASSERTION (Apache-2 core plus Timescale License components) | 2026-11-04, 23,803 | Time-series storage | A second database extension and a mixed licence for a table that is small; flag for licence review if ever considered | **REJECT now** |
| `recommenders-team/recommenders` | MIT | 2026-11-04, 21,976 | Recommender algorithms | Needs user interaction data ViralTrack does not have | **REFERENCE** |
| `qdrant/qdrant` | Apache-2.0 | 2026-11-04, 35,429 | Vector database | A second datastore; pgvector already does the job | **REJECT** |
| `yt-dlp/yt-dlp` | Unlicense | 2026-11-04, 205,276 | Extraction by scraping YouTube pages | Unofficial, restriction-circumventing: prohibited by project rules | **REJECT** |
| `iv-org/invidious` | AGPL-3.0 | 2026-11-05, 25,882 | Alternative YouTube front end (scraping) | Unofficial source and AGPL | **REJECT** |
| `LuanRT/YouTube.js` | MIT | 2026-11-04, 5,408 | Client for YouTube's **private** InnerTube API | Undocumented endpoints: prohibited | **REJECT** |

## 3. What this means

1. **No replacement for the foundation** was found, so nothing in the discovery pipeline should be rebuilt in ViralTrack.
2. **Ranking and trend maths needed for the approved metrics are arithmetic** (division, comparison, medians). The
   policy permits "simple mathematical calculations" on YouTube API data. Adding a statistics dependency is not
   justified until there is a defined need; if one arises, `scipy` (BSD-3, already ubiquitous) is the first choice.
3. **Forecasting libraries are rejected for now** because projecting performance is on the policy's "Don't" list
   without the Analytics & Reporting amendment (`docs/phase-1/DERIVED_METRIC_POLICY.md`).
4. **Anomaly and change-point libraries are future references.** They only make sense with enough snapshot history
   (stage D6) and after the owner decides whether a statistical "breakout" label counts as a custom score.
5. **No new dependency is recommended for D1 to D5.**

## 4. Limits of this audit

- Only licence, last push, archive flag and star count were read for non-adopted projects. Maintenance quality, test
  coverage, dependency trees and security posture were **not** reviewed (UNKNOWN).
- GitHub search is keyword-based and can miss projects that describe themselves differently, or that are not on GitHub.
- A permissive licence does not make a data source legitimate: only official API use is acceptable.
