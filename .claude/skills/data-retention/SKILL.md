---
name: data-retention
description: Review how ViralTrack (or its foundation) stores externally sourced platform data, classify every stored item, and keep the retention policy and job in sync. Use whenever a change persists, caches or exports provider data, adds a table or column, or moves the foundation pin.
---

# data-retention

Don't make legal conclusions. State what the platform terms say (quote and link them), what the code does, and
the gap between the two. Flag open questions for human or legal review.

## Classify every stored item

| Class | Meaning |
|---|---|
| RAW_PROVIDER_DATA | Values as returned by the platform API (counts, titles, descriptions, thumbnails) |
| DERIVED_DATA | Computed from provider data (scores, velocity, embeddings, LLM output) |
| IDENTIFIER | Platform ids (video id, channel id) |
| CACHE | Stored to avoid recomputation or refetching |
| TEMPORARY_DATA | Bookkeeping with a short life |
| USER_GENERATED_DATA | Created by the user (notes, watchlists, drafts) |

## For each stored data type, record

- **Purpose:** why it is stored.
- **Retention:** how long, and which rule applies.
- **Deletion:** how and when it is deleted, and by what.
- **Recomputation:** can it be recomputed or refetched, and at what cost (quota, LLM)?
- **Risk:** LOW / MEDIUM / HIGH and why.

## Current rules (YouTube)

- Non-authorized statistics: at most 30 days. Other API data: delete or refresh within 30 days. Re-verify
  that deleted videos are gone (Developer Policies III.E.4).
- With an accepted Analytics & Reporting amendment, statistics may be kept 36 months. Titles, names,
  descriptions and comments stay at 30 days.
- The upstream foundation deletes nothing. ViralTrack's `viraltrack/retention` enforces the rules.

## When something changes

1. Update `viraltrack/retention/policy.py` (`TABLES`, `AGE_RULES`, dependents).
   `tests/test_retention_policy.py` fails on an unclassified upstream table.
2. Add or extend tests in `tests/test_retention_job.py` (real upstream DDL).
3. Update `docs/phase-1/DATA_RETENTION_POLICY.md`.
4. Never weaken a window or disable the job without explicit approval. Deletion is irreversible: test with
   report mode (`python -m viraltrack.retention` without `--apply`) first.

## Output

Table: `Store | Fields | Class | Purpose | Retention | Deletion | Recomputable | Risk`, followed by open
questions for human or legal review.
