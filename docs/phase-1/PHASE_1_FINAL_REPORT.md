# VIRALTRACK — PHASE 1 FINAL REPORT (after Phase 1.1 hardening)

Date: 2026-11-03. Phase 1 was committed and pushed by the owner (`aba23d6`, `355cd19`). The Phase 1.1 changes
are in the working tree: **not committed, not pushed**.

## Foundation

`pandich93/youtube-niche-finder` @ `d872014` (MIT), an unmodified git submodule at `upstream/youtube-niche-finder`.
Verified clean.

## Adoption

Composition (Option E). The foundation runs as a service. ViralTrack uses an adapter over its documented HTTP
API, and its retention job uses the foundation's database. No upstream code is copied or modified.
See FOUNDATION_ADOPTION_DECISION.md.

## Architecture

```text
ViralTrack domain (Content/Creator/Metric/Provenance, DataOrigin, Exposure, MetricPolicy)
  -> PlatformProvider + PlatformCapabilities (registry)
      -> YouTube adapter: GET-only, documented no-quota endpoints, policy-gated mapping and sorting
          -> niche-finder (submodule) -> YouTube Data API
Retention job (daily, Docker) -> niche-finder Postgres
```

The read-only review (FINAL_ARCHITECTURE_REVIEW.md) passes every area. Open: the foundation UI is
INTERNAL_ONLY, and `collected_at` is unknown for list items.

## Retention

**B-6: PARTIALLY RESOLVED.**

- Every upstream table is classified, and the four open groups are decided:
  - `meta`: keep with retention; the derived curve expires after 30 days.
  - `own_*`: keep with retention; deleted 30 days after the last successful sync.
  - `drafts`: keep; `review` stripped after 30 days.
  - `transcripts`: **REVIEW REQUIRED** (legal); meanwhile deleted with their video.
- All are implemented, tested on the real DDL, and run in Docker.
- Remaining: Google approval for derived metrics, the transcripts legal question, the identifier rule, and
  deployments must run the retention service.

## Derived metrics

Enforced policy boundary (DERIVED_METRIC_POLICY.md):

- **6 ALLOWED** (simple arithmetic): engagement rate, views per hour (lifetime / 24 h), views gained 24 h,
  acceleration, views per follower. Two of them are flagged for review.
- **8 RESTRICTED** until the amendment is accepted:
  - outlier scores (3 variants) and the outlier band
  - viral score
  - 30-day projection
  - RPM
  - the Shorts label
- **2 INTERNAL_ONLY**.
- Restricted values cannot enter `Content`. Allow-list mapping, a policy check, a model invariant and a sort
  gate all enforce this, and contract tests cover new upstream fields.
- **Not coverable by ViralTrack:** the foundation's own dashboard, API and MCP. They are INTERNAL_ONLY
  (localhost) and must not reach end users.

## License

- ViralTrack: **no license yet. The owner must decide.** Recommendation in VIRALTRACK_LICENSE_DECISION.md:
  proprietary + private repository for a commercial SaaS, or Apache-2.0 if open source. The repository is
  public today.
- Upstream: MIT, notice kept.

## Dependencies

- Final classification (OPEN_SOURCE_ADOPTION_AUDIT.md): nothing BLOCKED.
- NOTICE REQUIRED on distribution: MIT foundation, LGPL psycopg2-binary, MPL certifi/tqdm,
  Apache-2.0 MiniLM weights, the Debian-based `python:3.12-slim`.
- `py_rust_stemmers` resolved: MIT (plus permissive Rust crates).

## Real-data validation

**`REAL_DATA_VALIDATION_BLOCKED — YOUTUBE_API_KEY_NOT_CONFIGURED`**. No key in any environment scope or
`.env`, and nothing was invented. Validated against the foundation's demo corpus instead: normalization,
provenance, capabilities, errors, the policy, the demo-as-real guard and retention. The minimum-call plan is in
REAL_DATA_VALIDATION.md.

## Tests

- **Upstream:** Passed 1,786 · Failed 0 · Skipped 0 · 136 s (Linux Docker, pgvector).
- **ViralTrack (all):** Passed 65 · Failed 0 · Skipped 0 · 4.2 s.
- **ViralTrack (no database):** Passed 57 · Skipped 8.
- **Lint:** clean.

## CI

- GitHub Actions run 41671578970 on `355cd19`: **success** (43 passed, 1 skipped; upstream suite skipped by
  design).
- Phase 1.1 changes: **`GITHUB_CI_NOT_YET_EXECUTED`** (not pushed).

## Remaining blockers

| # | Blocker | Severity |
|---|---|---|
| 1 | No YouTube API key: real-data validation blocked | HIGH |
| 2 | Analytics & Reporting amendment not filed; 8 metrics RESTRICTED; foundation UI internal-only | CRITICAL for production / user-facing UI |
| 3 | ViralTrack license undecided while the repository is public | HIGH (owner decision) |
| 4 | Transcripts: legal review | MEDIUM |
| 5 | Review of `acceleration`, `views_per_follower` and the Shorts label classification | MEDIUM |
| 6 | Phase 1.1 not yet run in GitHub CI | LOW |
| 7 | `collected_at` unknown for list items (needs an upstream change) | LOW |
| 8 | Instagram, TikTok and audio unavailable (Phase 0) | CRITICAL for those features, not for Phase 2 YouTube work |
| 9 | Single-author upstream | MEDIUM |

## Final gate

**READY_FOR_PHASE_2_WITH_LIMITATIONS**

Evidence:

- The foundation is unmodified and fully green.
- The boundary, provenance, origin, retention and derived-metric policy are enforced and tested (65/65), and
  CI passed on GitHub for the pushed Phase 1.
- Phase 2 may build on the ALLOWED metric set and the provider layer.

Limits:

- It may not show RESTRICTED metrics to users, nor offer the foundation UI to users, before the amendment.
- It cannot claim real-data quality until a YouTube key is configured and REAL_DATA_VALIDATION.md is completed.
