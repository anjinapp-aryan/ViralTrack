# AI Content Intelligence: live-validation plan

Status: the owner approved and the collection ran on 2026-11-25 (30 units, 10 searches). The aggregate result is in
`evidence/2026-11-25-live-validation.md`. The manual review of 20 classifications is still open. Any further
collection spends YouTube quota and needs the owner's explicit approval.

## Goal

Confirm on real data that the AI views fill with AI content across countries and languages:

- the classifier's statuses and categories are sensible;
- regional collections are read back as discovery markets;
- the opportunities have real evidence;
- no restricted value leaks and nothing is stored beyond the existing retention rules.

## Setup

| Item | Value |
|---|---|
| Database | The local throwaway `vt_real` (PostgreSQL 16, pgvector), never Neon production |
| Foundation | Unmodified at `d872014`, API only, `WORKER_THUMBS=0`, `WORKER_THUMB_EMBED=0`, `LLM_PROVIDER=none`, no worker |
| Key | `YOUTUBE_API_KEY` from the root `.env`, never printed |
| ViralTrack | `VT_YOUTUBE_INGESTION_ENABLED=true` in the validation process only; `VT_YOUTUBE_MAX_SEARCH_PAGES=1`; data origin `real` |

## Calls

The calls are `collect_market(region, query, pages=1, period="7d")`: one `search.list` page (50 videos) each.

| # | Region | Query (language parameter) |
|---|---|---|
| 1 | IN | "kannada ai song" (`kn`) |
| 2 | IN | "ai devotional song" (`hi`) |
| 3 | IN | "tamil ai song" (`ta`) |
| 4 | IN | "telugu ai song" (`te`) |
| 5 | US | "ai music video" (`en`) |
| 6 | US | "ai animation short film" (`en`) |
| 7 | KR | "AI 노래" (`ko`) |
| 8 | JP | "AI 歌" (`ja`) |
| 9 | BR | "música feita com ia" (`pt`) |
| 10 | GB | "ai generated documentary" (`en`) |

- **Budget:** at most 10 search calls and 60 units, which covers search plus `videos.list` and
  `channels.list`. The 6 generic searches on 2026-11-25 cost 3 units each.
- **Guard:** stop before a call if the foundation's meter shows more than 60 units or 10 search calls today.
- **Retries:** none. A timeout is not retried.

## Checks after collection

All checks are free and read-only:

1. Each `vt-market-<cc>-…` niche exists, and `/api/v1/ai/countries?basis=discovery` lists every market.
2. `/api/v1/ai/summary` per market. Record the status and category counts, and inspect a sample of 20
   classifications by hand. Owner review: the evidence text must justify each status.
3. A response-key scan of all four `/api/v1/ai/*` routes: no restricted or foundation-only key.
4. `/api/v1/ai/opportunities` per basis. Confirm that no brief contains a supporting title.
5. The quota meter before and after the checks is unchanged.
6. `python -m viraltrack.retention` in report mode on `vt_real`.

## Evidence kept

Aggregates only, in `docs/ai-intelligence/evidence/`:

- counts per market, status and category;
- the units spent;
- the classifier version.

No titles, ids or tags are kept beyond the 30-day database retention.

## Stop conditions

Stop on any of these:

- a quota or credential error;
- a restricted key in a response;
- a classification that is plainly wrong in more than 5 of the 20 sampled items (tune the rules offline,
  then ask again);
- any unexpected write.
