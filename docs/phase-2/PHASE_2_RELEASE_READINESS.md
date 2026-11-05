# Phase 2 release-readiness assessment

Date: 2026-11-05. Reviewed head: `5ed12ec`. Commit map: [PHASE_2_COMMIT_MAP.md](PHASE_2_COMMIT_MAP.md).

## Verdict

**Phase 2 is ready as an internal engineering release, with limitations (PASS_WITH_LIMITATIONS).**
**It is not ready for production use or any user-facing exposure.** The blockers are mostly owner decisions and legal
reviews, not code.

"Internal engineering release" means: an operator can run the stack locally or on a private host, switch ingestion on
deliberately, collect a bounded amount of YouTube data, and the retention job keeps the stored data within the 30-day
rule, all without exposing any restricted metric. No ViralTrack API, UI or MCP serves this data to anyone.

## 1. What Phase 2 set out to deliver, and the result

| Goal | Result | Evidence |
|---|---|---|
| Metric policy reconciled with what the foundation computes | **Done.** 4 allowed, 10 restricted, 2 internal-only; restricted sorts refused | Batch 1; real-data check found no restricted metric in 30 items |
| On-demand ingestion interface, off by default | **Done.** Zero requests while disabled; quota pre-flight; cooldown; single attempt per collection POST | Batch 2; 46 offline ingestion tests; Batch 5 live use |
| Provider-agnostic database configuration | **Done for configuration, tested on one server.** PostgreSQL 16.2 + pgvector 0.6.2 only; Neon, Supabase and Aiven are documentation-based | `DATABASE_PROVIDER_COMPATIBILITY.md` |
| Ingestion profile: no thumbnails, no LLM | **Done.** Applied by default through the Compose `include`; retention deletes any stored images and image vectors | F2, rendered-config tests |
| Retention verified on real DDL, 30-day clock | **Done.** Boundaries, time zones, report-only mode and rollback tested; interval configurable | Batch 3 review, interval tests |
| Retention container isolated from the API key | **Done** | F1, rendered-config tests |
| Controlled real-data validation | **Done with limitations** (6 of 50 units, one channel, one keyword) | Batch 5 report and evidence |
| Internal read API (Batch 4) | **Deferred by owner decision.** Not part of this release | Plan |

## 2. Quality gates

| Gate | Status |
|---|---|
| Full suite (local PostgreSQL 16.2 + pgvector) | 285 passed, 0 failed, 2 skipped |
| Plain `pytest` | 262 passed, 25 skipped |
| Ruff | clean |
| GitHub CI on `5ed12ec` | success. **CI runs the offline suite only.** The live-foundation tests skip, and the upstream suite runs only on schedule or manual dispatch |
| Compose configuration | `docker compose config` validates; services rendered for local and managed-database setups |
| Upstream submodule | unmodified at `d872014` |
| Secrets | the real key is in no commit, is gitignored (`.env`, `.env_*`) and was not found in any tracked file |
| Dependency licences | unchanged since Phase 1; no dependency added in Phase 2 |

## 3. Blockers for production or user-facing use (BLOCKED)

| # | Blocker | Owner |
|---|---|---|
| B1 | **Licence not decided.** The owner prefers proprietary and private; the repository is still public and unlicensed by choice pending confirmation | Owner |
| B2 | **Google Analytics & Reporting amendment not filed.** The 10 restricted metrics (acceleration, views per follower, outlier scores, viral score, projections, RPM estimate, Shorts label) stay off. Without them most "viral" ranking cannot be offered | Owner / Google |
| B3 | **Provider backups keep deleted rows beyond 30 days.** Counsel has not reviewed whether that is acceptable. Run retention after every restore | Owner / counsel |
| B4 | **Transcripts: legal review pending.** Nothing collects them and retention deletes any that appear | Owner / counsel |
| B5 | **No user-facing surface.** Batch 4 was deferred, so there is no way to serve `Content` safely to users | Owner decision |
| B6 | **No alerting on retention failures.** Only exit codes and container logs exist | Engineering |
| B7 | **Docker stack never run end to end.** The real-data run was native on Windows. Compose was only rendered and tested; the `retention` container and the managed-database path were never started | Engineering |

## 4. Known limitations (not blockers for internal use)

- **Not a hard 30-day maximum.** A row can outlive 30 days by about one retention interval plus run time (about an
  hour by default; up to six hours with the Neon setting), and for as long as the retention container is stopped or
  failing.
- **`collected_at` is unknown for every metric.** The foundation does not return a statistics-capture time.
  `foundation_first_seen_at` records when the foundation first stored the item; ViralTrack's receive time is
  `Content.retrieved_at`.
- **Discovery has never returned a real item.** The foundation's default filters removed the Batch 5 sample. A test
  plan exists and was not run.
- **Validation was small:** one channel (probably not small, bounded by a 20-video cap) and one keyword. Shorts
  classification, large result sets and the freshness job were not examined.
- **Quota figures come from the foundation's counters,** not Google's console.
- **The 120-second collection timeout and `ProviderTimeout` were tested against mocks only,** not the live foundation.
- **Thumbnail downloads can still be triggered manually** through the foundation's `POST /api/thumbnails/embed` route
  and MCP tool (internal surfaces). Retention removes the result on its next run.
- **Text embeddings are stored** (50 vectors in Batch 5) and the embedding model is downloaded from Hugging Face on
  first use. They follow their video row's 30-day window.
- **Managed providers are untested.** Neon, Supabase and Aiven are documentation-based. The foundation opens up to 20
  connections per process, which exceeds the smallest Aiven and Supabase plans.
- **Platform coverage is YouTube only.** Instagram is limited to the official Graph API and TikTok has no legitimate
  discovery source; neither is built.
- **The `.vscode/settings.json` file** in history is an editor setting, not part of the product.

## 5. What an operator may do today

Allowed (internal, private network): run the Compose stack, set `VT_YOUTUBE_INGESTION_ENABLED=true` for a deliberate
collection, read the allowed metrics through the provider, run retention in report mode or apply mode.

Not allowed: expose the foundation's dashboard, API or MCP to users or the internet (they are internal-only and carry
restricted metrics); turn on transcripts, thumbnail archiving, LLM features or any restricted metric; collect Instagram or
TikTok data; deploy for external users.

## 6. Recommended order before Phase 3

1. Owner decisions: licence and repository visibility (B1); whether to file the Google amendment (B2).
2. Counsel: backup retention (B3) and transcripts (B4).
3. Run the Docker stack end to end once, including the `retention` container (B7), and add retention-failure
   alerting (B6).
4. Run the discovery plan on a fresh test database within its 15-unit budget, with explicit approval.
5. Decide whether Phase 3 includes the internal read API (B5).

Phase 3 has not been started and will wait for the owner's approval.
