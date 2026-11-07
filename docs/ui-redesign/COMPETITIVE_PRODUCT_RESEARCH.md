# Competitive product research

Date: 2026-11-07.

**Limitation, stated first:** no competitor website or product was opened in this session. This session has no browser and no logged-in accounts, and these products show most of their UI only to signed-in users. The observations below come from general product knowledge up to the model's training data and are marked **UNVERIFIED**. They must be checked by the owner (screenshots of the current products) before any design decision depends on them. No proprietary code, branding or assets were used.

## 1. Patterns (UNVERIFIED)

| Product | Pattern worth learning | Pattern to avoid for ViralTrack |
|---|---|---|
| YouTube Studio | Calm, neutral surfaces; one accent; large KPI numbers with small comparison text; charts with clear time axes; strong empty states | Its private analytics (watch time, retention) are not available to ViralTrack |
| vidIQ | Search-first discovery; keyword pages with a few headline numbers; browser-extension overlays | Proprietary "scores" presented as facts; ViralTrack cannot copy score badges |
| TubeBuddy | Tool-per-task navigation | Many tools in a long menu feel cluttered |
| Social Blade | Public, dense tables of channel stats over time; grades | Letter grades and projections are derived claims ViralTrack does not make |
| 1of10 / outlier-style tools | Big thumbnails first, video grid like YouTube itself, outlier multiplier as the hero number | The hero number is a restricted metric for ViralTrack |
| Viewstats | Polished charts, strong typography, editorial feel | Projections |

## 2. What makes these products feel professional

1. **Thumbnail-first video cards** at a correct 16:9 ratio, duration chip in the corner, two lines of title, one line of creator, one line of numbers.
2. **One hero number per card**, everything else in a detail view.
3. **Consistent type scale** with tabular numbers.
4. **Search as the main entry point**, filters as chips beside it.
5. **Explained metrics**: an info icon or hover text next to every derived value.
6. **Skeleton loading** in the shape of the final content.
7. **Restraint**: few colours, semantic use of green and red.

## 3. How ViralTrack can be distinct

ViralTrack's honest position is "observed, not predicted": provenance, freshness, RAW and DERIVED labels and an explicit "hidden by creator" instead of a zero. No competitor reviewed here (UNVERIFIED) makes data provenance a visible design element. That is the identity proposed in `VIRALTRACK_DESIGN_SYSTEM.md`.
