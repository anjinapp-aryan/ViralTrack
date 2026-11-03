# Real-Data Validation

**Status: `REAL_DATA_VALIDATION_BLOCKED — YOUTUBE_API_KEY_NOT_CONFIGURED`**

Checked 2026-11-03, without printing any value: `YOUTUBE_API_KEY` is unset in the process, user and machine
environments, and no `.env` exists in the repository root, `upstream/youtube-niche-finder/` or its `backend/`.
No key was invented or hard-coded, and no YouTube API call was made.

## What was validated instead

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | YouTube request succeeds | **NOT RUN** | No key |
| 2 | Adapter receives a real response | **Partly**: real foundation HTTP responses (demo corpus, :3903) | `test_live_foundation` |
| 3 | Normalization succeeds | Yes, on foundation responses | provider tests, live test |
| 4 | Provenance populated | Yes: platform, provider, external id, adapter, origin, kind, `retrieved_at`. `collected_at` is `None` (the foundation does not expose it) | `test_every_record_answers_the_provenance_questions` |
| 5 | Supported capabilities work | Yes, on the demo corpus | provider and live tests |
| 6 | Unsupported capabilities blocked | Yes, with no network call | `test_unsupported_raises_and_makes_no_call` |
| 7 | Error handling | Yes (unreachable, 404, 401, 5xx, non-JSON) | provider tests |
| 8 | Rate and quota behaviour | **NOT RUN against YouTube.** The adapter uses only no-quota endpoints. The foundation enforces 100 searches and 10,000 units a day (its own tests: 1,786 pass) | `/api/health` quota fields |
| 9 | Persistence follows retention | Yes, on the real upstream DDL and the demo database (report: 9 rows) | retention tests |
| — | Demo data cannot pass as real | Yes. With `VT_YOUTUBE_DATA_ORIGIN=real`, the live demo foundation is rejected: `'bvid008' is not a YouTube video id` | `test_demo_corpus_cannot_pass_as_real_provider_data` + live check |

## Plan once a key exists (minimum calls)

1. Put the key in `upstream/youtube-niche-finder/.env` (`YOUTUBE_API_KEY=`), never in git, and set
   `NF_DEFAULT_LOCALE=en`.
2. `docker compose up -d postgres web retention` (no `worker` yet).
3. One collection call: `POST /api/collect/channel` for one public channel, about 2–3 units, no `search.list`.
4. Through the adapter: `discover_content(period="30d")`, `search_content()`, `get_creator()`,
   `get_creator_history()` with `VT_YOUTUBE_DATA_ORIGIN=real`.
5. Record into this file: endpoint, purpose, success, normalized fields, raw and derived names, provenance,
   quota used (`/api/health` before and after), and the retention report.
6. Leave `VT_TEST_FOUNDATION_ORIGIN=real` set when running `pytest -m live_foundation`, so the real-id check runs.
