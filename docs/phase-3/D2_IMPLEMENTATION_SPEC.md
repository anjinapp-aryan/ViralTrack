# D2 implementation specification: explicit publication period for keyword collection

Date: 2026-11-05. SPECIFICATION ONLY. D2 is not started and needs the owner's explicit approval. No code, schema, Compose file,
workflow or upstream file was changed; no YouTube request was made.

Labels: **VERIFIED** (source read; where stated, also run offline), **INFERRED**, **PROPOSED**, **UNKNOWN**, **BLOCKED**.
Upstream paths are relative to `upstream/youtube-niche-finder/backend/`. Context: [YOUTUBE_DISCOVERY_AUDIT.md](YOUTUBE_DISCOVERY_AUDIT.md),
[D1_CLOSURE_REPORT.md](D1_CLOSURE_REPORT.md).

## 1. Objective and boundary

Let `YouTubeProvider.collect_query` pass an explicit publication period to the foundation, so a keyword collection can target
recent videos instead of the all-time most viewed ones, with predictable, testable behaviour.

D2 **reuses** the foundation's `POST /api/collect/niche` and its existing `period` field. It adds no YouTube client, scheduler,
quota manager or database abstraction. It does **not** change discovery filtering (`discover_content`, `search_content`):
those are D3, so the three root-cause xfail tests stay xfail after D2.

## 2. What the upstream does today (VERIFIED by source)

| Question | Behaviour | Source |
|---|---|---|
| Route | `POST /api/collect/niche` reads `query`, `label`, `language`, `period`, `region`, `pages` only. It does **not** accept `order`, `category_id`, `video_duration` or `min_upload_date` | `interfaces/http/api.py:2193-2204` |
| Period omitted, `null` or `""` | `payload.get("period") or None` makes all three **None**: no `publishedAfter` | `api.py:2202` |
| Period `all` / `alltime` | `if period and not min_upload_date:` runs, `P.cutoff` returns None, so `min_upload_date` stays None: **same as omitted** | `application/collecting.py:190-193`; `domain/periods.py:46-52` |
| Period `24h`, `7d`, `30d`, any `\d+[hdwm]` | `min_upload_date = (now_utc - delta)` formatted `%Y-%m-%dT%H:%M:%SZ`; `d` = days, `w` = 7 days, `m` = **30 days**, `h` = hours | `domain/periods.py:22-41, 99-101` |
| Aliases | `day`, `today`, `week`, `month`, `quarter`, `2d`, and Russian words map to canonical values; matching is **case-insensitive** and trims spaces | `periods.py:9-19, 26` |
| Invalid period (for example `garbage`) | `P.cutoff` raises `ValueError` **before** the niche row, the quota check and any search call; the route has no handler for it, so it ends in the generic handler as HTTP 500 `{"error":"ValueError",...}`; no quota is spent | `collecting.py:190` (first statements of `collect_niche`); `api.py:596-599` |
| Zero period (`0h`, `0d`) | **Valid** upstream: cutoff = now, so `publishedAfter` is the current time. A search call is spent and almost nothing can match | `periods.py` regex `\d+` accepts 0 (INFERRED from the code; not executed against `collect_niche`) |
| Ordering | `search_videos` default `order="viewCount"` and the route cannot change it: inside the window, most-viewed first | `infrastructure/youtube/client.py:279-296`; `collecting.py:170-174` |
| Boundaries and time zone | UTC. The cutoff uses the foundation server's clock, truncated to whole seconds. Whether YouTube treats `publishedAfter` as inclusive is **INFERRED** "at or after" from the API reference (not verified here). Pacific time is used only for the daily quota reset (`periods.py:104`) |
| Pagination | `pages` search calls of up to 50 results (`max_results` is capped at 50); `nextPageToken` followed; stops when none. The foundation notes a cap of about 500 results per query | `client.py:279-296`; `collecting.py:206-226` |
| Duplicates | ids are de-duplicated across pages with `dict.fromkeys` | `collecting.py:228` |
| Niche identity | `slug = slugify(label or query)`: **the same query with different periods writes into the same niche** | `collecting.py:196-198` |
| Quota | 1 search call per page (own 100/day bucket) + about 1 unit per 50 videos and per 50 channels; reported in `quota` | `collecting.py:_quota` |
| Response | includes `min_upload_date` (the cutoff actually used, or None), `videos_found`, `videos_stored`, `channels_stored`, `quota` | `collecting.py:247-253` |

## 3. What ViralTrack does today (VERIFIED)

`viraltrack/providers/youtube/provider.py` `collect_query(text, pages=1, region=None, language=None)` (line 216):
`_require_ingestion` -> `_ref(text)` -> `_cap(pages)` -> region and language checks -> `_preflight` (one `GET /api/health`)
-> `POST /api/collect/niche` with `{query, pages, region, language}`; `FoundationClient.post` drops `None` values
(`client.py:65-66`) and makes **one** attempt (`ProviderTimeout` semantics from Batch 5). It sends **no `period`**: this is the
cause of the all-time most-viewed sample in Batch 5. ViralTrack already has a period validator, `_PERIOD =
^(all|\d{1,4}[hd])$` and `_check_period` (lines 35, 94), used by discovery and refresh; it accepts `0h`/`0d` and rejects
uppercase, spaces, `w`, `m` and aliases.

Existing test that pins the current body: `tests/test_ingestion.py::test_collect_query` asserts the posted JSON equals
`{"query":"cooking","pages":1,"region":"US","language":"en"}`.

## 4. Functional requirements (PROPOSED)

### 4.1 Interface

```python
def collect_query(self, text, pages=1, region=None, language=None, period=None) -> IngestionResult
```

`period` is added **last**, so every existing positional and keyword call keeps working. The abstract method in
`viraltrack/providers/base.py` gets the same optional argument.

### 4.2 Parameter semantics

| Input | Behaviour |
|---|---|
| omitted / `None` | `period` is **not sent**; request body identical to today (backward compatible); upstream collects all-time most viewed |
| `"all"` | sent as `"all"` (explicit, and documented as equal to omitted upstream) |
| `"24h"`, `"7d"`, `"30d"`, any `N` + `h` or `d`, N from 1 to 9999 | sent verbatim in canonical lowercase |
| `""` (empty) | **rejected** with `ValueError` (upstream would silently read it as "omitted") |
| `"0h"`, `"0d"`, `"00d"` | **rejected** (would spend a search call on a window that is empty by construction) |
| uppercase, padded with spaces, `"1w"`, `"1m"`, `"week"`, `"month"` and other aliases | **rejected**: the adapter accepts one canonical spelling; upstream's wider set is not used, because `m` means 30 days there and `m` reads as minutes to many callers |
| non-string (`int`, `bool`) | rejected with `ValueError` |

The validator is a new small function (for example `_check_collect_period`) built on the existing `_PERIOD` idea with the
non-zero rule, so discovery and refresh keep their current behaviour.

### 4.3 Order of checks and errors

`_require_ingestion` -> `_ref` -> `_cap(pages)` -> **period** -> region -> language -> `_preflight` -> POST. Every argument
error raises `ValueError` **before** any request, including the health call. Other errors are unchanged: `IngestionDisabled`,
`ProviderCredentialsMissing`, `QuotaExhausted`, `RateLimited` (cooldown), `ProviderTimeout` (client side, `outcome_unknown`),
`ProviderError` with the status for a confirmed foundation failure. **No retry** of the POST, as since Batch 5.

### 4.4 Safe default (owner decision, section 9)

The method default stays `None` (no behaviour change). A named configuration value `VT_YOUTUBE_COLLECT_DEFAULT_PERIOD`
(default empty = none; validated like the argument; 1 to 9999 hours or days, or `all`) is **proposed as optional** so a deployment can
opt in to a window without code changes. It must never be applied silently by default.

### 4.5 Reporting what was applied

The upstream echoes `min_upload_date`. D2 should surface it on `IngestionResult` as an optional UTC datetime
(for example `applied_since`, None when the foundation reports none), parsed with the same rules as `foundation_first_seen_at`
(aware or None). This lets a caller and a test confirm that the period reached the search call, without ViralTrack computing
quota or time itself. Additive; existing fields unchanged.

### 4.6 Quota reporting

Unchanged: the pre-flight floors (`VT_YOUTUBE_QUOTA_FLOOR_*`), `pages` cap, and the foundation's `quota` figures copied into
`quota_units_reported` and `search_calls_reported`. A period does not change the cost: still `pages` search calls plus
about 1 unit per 50 videos and channels.

### 4.7 Documentation to update

`docs/phase-1/PROVIDER_BOUNDARY.md` (signature and the check order), `docs/phase-2/INGESTION_PROFILE.md` (recommended worker
and collection settings), `.env.example` (only if the optional configuration value is adopted), and a short note that
`order=viewCount` is fixed upstream and that one query shares one niche across periods.

## 5. Request flow

```text
caller -> YouTubeProvider.collect_query(text, pages, region, language, period)
   1 _require_ingestion        raises IngestionDisabled (no request)
   2 _ref / _cap / period / region / language validation   raises ValueError (no request)
   3 _preflight                GET /api/health            (reads quota, floors, cooldown)
   4 POST /api/collect/niche   {query, pages, region, language, period}   ONE attempt
        foundation: P.cutoff(period) -> publishedAfter (UTC, seconds)
                    search.list x pages (order=viewCount) -> videos.list -> channels.list -> store
   5 IngestionResult(counts, quota_units_reported, search_calls_reported, applied_since)
```

## 6. Test strategy

Four tiers; none spends quota or touches the network.

| Tier | Where | What |
|---|---|---|
| Unit | new `tests/test_collect_period.py` | the validator alone: every row of 4.2, parametrized: omitted, `None`, `""`, `"all"`, `"1h"`, `"24h"`, `"7d"`, `"30d"`, `"9999d"`, `"0h"`, `"10000d"`, `"7D"`, `" 7d"`, `"1w"`, `"week"`, `7`, `True` |
| Adapter | same file, `httpx.MockTransport` like `tests/test_ingestion.py` | body contains `period` only when given; body unchanged when omitted (the existing `test_collect_query` stays valid and untouched); invalid period makes **zero** requests, including no `GET /api/health`; one POST per call and **no retry** for `ReadTimeout`, `WriteTimeout`, `ConnectTimeout`, `PoolTimeout`, `ConnectError` with a period set; foundation unavailable and 429/428 mapping unchanged; the `quota` figures copied unchanged; `applied_since` parsed (aware UTC, None when absent or malformed) |
| Foundation-backed, offline | `tests/support/upstream_runner.py` gains a **collect mode** (test infrastructure only) that runs the real `application.collecting.collect_niche` in the upstream interpreter with `infrastructure.youtube.client` functions replaced by deterministic fakes. It asserts: `published_after` equals `now - delta` within the call's time bounds for `24h`, `7d`, `30d`; `None` for omitted and `all`; the zero-quota failure for an invalid period happens before any fake is called; duplicates across fake pages collapse; quota report fields; the `min_upload_date` echo. It also pins `domain.periods.parse_period` for the tokens in section 2 | uses the same database and environment variables as D1; skips without `VT_TEST_UPSTREAM_PYTHON`; the existing `requests` guard stays |
| Live | existing `@pytest.mark.live_foundation` | **none added and none enabled.** A future live check needs a separate approval with an explicit budget (one keyword with one page: 1 search call and about 3 units) |

Coverage map for the requested cases: period omitted, each supported period, invalid, empty, null, case sensitivity, query
serialisation, parameter omission (adapter tier); publication-date boundary and UTC normalisation (foundation-backed tier,
asserting the echoed `min_upload_date` and its `Z` UTC form); pagination and duplicates (foundation-backed tier with a
multi-page fake); foundation timeout and unavailable, no automatic retries, quota accounting, no API key, no network access
(adapter tier plus the runner's guard). Case sensitivity is tested on **both** sides: ViralTrack rejects uppercase; upstream
accepts it (pinned so a change is noticed).

## 7. Acceptance criteria (measurable)

1. `collect_query(..., period="7d")` posts a body whose `period` equals `"7d"`; with `period` omitted the body is byte-for-byte what the existing `test_collect_query` expects.
2. Each of the rejected inputs in 4.2 raises `ValueError` and the recording transport shows **0 requests** (no health call, no POST).
3. The foundation-backed offline test shows `published_after` within the call's time window of `now - 24h`, `now - 7d`, `now - 30d`, UTC, whole seconds; `None` for omitted and `all`.
4. All existing tests pass unmodified (399 passed, 2 skipped, 9 xfailed baseline, plus the D2 tests). The nine xfails stay xfail.
5. `git diff` shows no new HTTP client, no scheduler, no quota calculation and no database code; `FoundationClient` is still the only client.
6. No metric, sort or filter is added or changed; the restricted-metric tests still pass.
7. Zero network attempts and zero quota in every D2 test; the runner's counter asserts it.
8. No retry: every transport failure type yields exactly one POST.
9. `docs/phase-1/PROVIDER_BOUNDARY.md` and the ingestion profile describe the actual semantics of section 2, including `all` = omitted, fixed `order=viewCount` and the shared niche.
10. `git diff -- upstream` is empty and the pin is `d872014`.
11. Ruff clean; the lock check and the existing CI job unchanged.

## 8. Files likely to change (when approved)

`viraltrack/providers/youtube/provider.py` (`collect_query`, validator), `viraltrack/providers/base.py` (signature),
`viraltrack/providers/youtube/ingestion.py` and `providers/base.py` (`applied_since`, optional), `viraltrack/config.py` and
`.env.example` (only if the optional default is adopted), `tests/test_collect_period.py` (new), `tests/support/upstream_runner.py`
and `tests/support/upstream.py` (collect mode, tests only), the two documents above. No change under `deploy/`,
`docker-compose.yml`, `.github/` or `upstream/`.

## 9. Owner decisions needed (cannot be settled from source)

1. **Default:** keep `period=None` as the method default (recommended, backward compatible) and optionally adopt `VT_YOUTUBE_COLLECT_DEFAULT_PERIOD`, or change the default to a window such as `30d` (changes behaviour of existing callers).
2. **Accepted spellings:** the canonical `N` + `h`/`d` set proposed here, or also `w`/`m`/aliases (`m` means 30 days upstream).
3. **`all`:** send it, or normalise it to "omitted".
4. **Niche separation:** the same query with different periods shares one niche. Accept this, or add a `label` argument in D2 (a wider change; the route already accepts `label`).
5. **Upper bound:** keep `9999` hours or days (as the existing validator), or set a tighter cap.
6. **`applied_since`:** whether the optional result field is wanted in D2.

## 10. Compliance (unchanged)

D2 touches no metric, sort or filter. No restricted metric, composite or breakout score,
cross-channel ranking, forecasting, Shorts classification, similar-video discovery, transcripts, thumbnails, LLM, Instagram or
TikTok is introduced. `order=viewCount` is the foundation's fixed search order for the API's `search.list`; it is a search
parameter, not a ViralTrack ranking. Technical feasibility is not treated as policy approval.
