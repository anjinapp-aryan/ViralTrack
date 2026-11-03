# Reuse-First Policy

**REUSE → ADAPT → COMPOSE → BUILD**

Every meaningful feature walks this ladder from the top and stops at the first rung that works.

| Rung | Meaning in ViralTrack | Example |
|---|---|---|
| **REUSE** | Use existing code or a service as-is | The foundation's dashboard, outlier and velocity metrics, alerts |
| **ADAPT** | Change behaviour at the ViralTrack boundary; never edit `upstream/` | The adapter sends `X-NF-Locale: en`; the retention job deletes what upstream keeps |
| **COMPOSE** | Combine existing services or APIs | Foundation HTTP API + normalized model; upstream compose `include` + `retention` service |
| **BUILD** | New code, only for a real gap | Provenance model, provider interface, retention policy |

## Before writing new functionality

1. Search this repository.
2. Search existing dependencies.
3. Search the adopted foundation (`upstream/youtube-niche-finder/docs/http-api.md`).
4. Search GitHub and open source, where relevant.
5. For each candidate, inspect the source, not only the README.
6. Check the license (`license-audit`).
7. Check maintenance and activity.
8. Check its tests, and run them for finalists.
9. Check that it actually works, and that its data source is legitimate.
10. Decide, and record the decision (use the `reuse-audit` output format).

## Rules

- Never rewrite stable functionality for stylistic reasons.
- BUILD requires a written reason why each candidate was unsuitable.
- Reused code keeps its license and attribution (`THIRD_PARTY_NOTICES.md`).
- Every modification of reused behaviour is documented and isolated in ViralTrack code.
- Keep upstream upgradeable: depend on documented contracts (the HTTP API) and guard any other coupling with
  a contract test, as `tests/test_retention_policy.py` does for the schema.
- **Data legitimacy is a separate gate.** An MIT-licensed scraper is still rejected when its data route
  violates platform terms (Phase 0: TikTok-Api, instaloader, Douyin_TikTok_Download_API, jev-social).

## Record of decisions

- Phase 0: `docs/phase-0/REUSE_MATRIX.md`, `FINAL_ADOPTION_DECISION.md`
- Phase 1: `docs/phase-1/FOUNDATION_ADOPTION_DECISION.md`, `PHASE_1_FINAL_REPORT.md` (section 4 lists every
  new piece of code with its reason)
