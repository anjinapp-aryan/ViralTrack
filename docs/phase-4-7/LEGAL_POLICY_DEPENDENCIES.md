# Legal and policy dependencies for phases 4 to 7

Date: 2026-11-07. This document separates technical facts from questions for counsel. It draws no legal conclusion. Sources are the repository's own policy documents (`docs/phase-1/DERIVED_METRIC_POLICY.md`, `docs/phase-1/DATA_RETENTION_POLICY.md`, `docs/phase-1/METRIC_INVENTORY_AND_APPROVAL.md`); the external terms themselves were not re-read in this audit.

## 1. Technical facts (verifiable in the repository)

- 4 metrics are ALLOWED, 10 RESTRICTED, 2 INTERNAL_ONLY. `Content` rejects any derived value not ALLOWED. Restricted names raise `RestrictedMetric` as sorts.
- The only approved sorts are raw `views` and `published_at`.
- 30-day retention is the default; 36-month statistics need the Google Analytics and Reporting amendment, which is not recorded as granted. Retention is report-only by default.
- Thumbnail download, transcript persistence and LLM providers are disabled.
- The foundation's dashboard, API and MCP are internal-only.

## 2. Questions for counsel (D4 gate)

1. What does "ranking" mean for ViralTrack: does ordering by one raw metric count?
2. Which metrics may influence ordering? Which are prohibited?
3. May results be described as popular, trending, viral, breakout or emerging, and on what evidence?
4. How must incomplete, stale or unavailable data affect results or labels?
5. How must semantic relevance be kept distinct from popularity (a relevance score must never read as popularity or breakout potential)?
6. Which explanations must be visible to users?
7. Which disclaimers and limitations are required?
8. Is any confidence indicator permissible, and if so what basis is required? (Technical position: a numeric score is not statistical confidence; no sample-based method is currently supported by the data, so none is proposed.)
9. Does presenting history or watchlists (D6) count as storing or displaying statistics beyond the 30-day rule?

## 3. Policy dependencies per phase

| Phase | Depends on | Status |
|---|---|---|
| D4 | Answers 1 to 8 above | Not approved |
| D5 | D4 wording and display policy; decision on authentication; no restricted metric in any response, filter, export or MCP tool | Not approved |
| D6 | Answer 9; retention design; Analytics and Reporting amendment for anything kept beyond 30 days | Not approved |
| D7 | Written owner authorization and quota accounting; sanitized evidence only; compliance with API terms on stored data | Not authorized |

## 4. Licensing

Recommended dependencies are limited to MIT, BSD, Apache-2.0 and 0BSD projects (see the reuse audit). Rejected for licence: Metabase (AGPL core, commercial enterprise), Grafana (AGPL), TimescaleDB (mixed licence). `psycopg2-binary` (LGPL) and `certifi` (MPL) remain the only accepted copyleft-adjacent libraries, unmodified. Any new dependency still needs the `license-audit` skill before it is added.

## 5. Not legal advice

Nothing here is a legal conclusion. The questions above must be answered by humans with the appropriate expertise.
