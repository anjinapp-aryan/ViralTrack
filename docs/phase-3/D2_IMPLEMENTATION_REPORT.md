# D2 implementation report: publication period for keyword collection

Date: 2026-11-05. Status: implemented, tested offline, **not committed**. No live YouTube API request was made and no quota
was spent. The upstream submodule is unchanged (`d872014`). Specification: [D2_IMPLEMENTATION_SPEC.md](D2_IMPLEMENTATION_SPEC.md).
The CI workstream is reported separately: [D2_CI_IMPLEMENTATION_REPORT.md](D2_CI_IMPLEMENTATION_REPORT.md).

## 1. Scope implemented

`YouTubeProvider.collect_query` accepts an optional `period` and passes it to the foundation's existing
`POST /api/collect/niche`; `IngestionResult` gets an optional `applied_since`. Nothing else changed: no discovery filter, sort,
ranking, mapping, schema, Compose or upstream change; no new client, scheduler or quota logic; no D3 item.

Approved decisions applied exactly: default `None`; no configurable default; accepted values lowercase `all` or `N` + `h`/`d`
with N from 1 to 9999; uppercase, aliases, zero and empty string rejected; `all` omits the parameter; no niche separation by
period; optional `applied_since` copied from the echoed `min_upload_date`; period appended last; omitted-period body unchanged.

## 2. Files changed

| File | Change |
|---|---|
| `viraltrack/providers/youtube/provider.py` | `_COLLECT_PERIOD` pattern and `_check_collect_period`; `collect_query(..., period=None)`; `period` added to the body (dropped by the client when None) |
| `viraltrack/providers/base.py` | abstract `collect_query` signature gets `period`; `IngestionResult.applied_since` (last field, default None) |
| `viraltrack/providers/youtube/ingestion.py` | `_utc_time`; `collect_result` sets `applied_since` from `min_upload_date` |
| `tests/test_collect_period.py` | new, 119 tests (unit and adapter tier) |
| `tests/test_collect_period_upstream.py` | new, 35 tests (foundation-backed, offline) |
| `tests/support/upstream_collect_runner.py`, `tests/support/upstream.py` | test infrastructure: run the real `/api/collect/niche` route with every YouTube call faked |
| `docs/phase-1/PROVIDER_BOUNDARY.md`, `docs/phase-2/INGESTION_PROFILE.md`, `docs/phase-3/DISCOVERY_EXECUTION_ROADMAP.md` | documentation of the actual semantics and status |

Mixed line endings already present in `provider.py` were left as they were; inserted lines follow the surrounding style.

## 3. Public interface

```python
collect_query(self, text, pages=1, region=None, language=None, period=None) -> IngestionResult
IngestionResult(..., search_calls_reported=None, applied_since=None)      # applied_since: aware UTC datetime or None
```

Positional compatibility: `period` is last in the provider and in the abstract interface; `applied_since` is the last dataclass
field, so existing positional construction still works (tested).

## 4. Request payload for every period case (checked on the recorded POST body)

| Caller passes | Body sent to `/api/collect/niche` |
|---|---|
| nothing / `None` | `{"query","pages"[,"region"][,"language"]}`, **byte for byte** what ViralTrack sent before (compared with the JSON an old client serialises) |
| `"all"` | the same body: `period` is omitted |
| `"1h"` ... `"9999h"`, `"1d"` ... `"9999d"` | the same body plus `"period": "<value>"` verbatim |
| anything else | no request at all |

## 5. Validation behaviour

Accepted: `all`; `[1-9][0-9]{0,3}` followed by `h` or `d`, lowercase, whole string (`fullmatch`, so a trailing newline is rejected).
Rejected with `ValueError` before **any** request, the health check included (the recording transport shows zero requests):

| Class | Examples tested |
|---|---|
| zero and leading zeros | `0h`, `0d`, `00d`, `000h`, `01d`, `007d`, `0024h` |
| empty | `""` |
| upper case | `7D`, `24H`, `ALL`, `All` |
| aliases and words | `day`, `today`, `week`, `month`, `quarter`, `24hours`, `сутки` |
| other units | `1w`, `2w`, `1m`, `3m`, `1y`, `30s`, `10min` |
| out of range | `10000h`, `10000d`, `99999d` |
| whitespace, signs, decimals, fragments | ` 7d`, `7d `, `7 d`, `7d\n`, `-1d`, `+7d`, `1.5d`, `h`, `24`, `1d1h` |
| non-strings | `7`, `0`, `1.5`, `True`, `False`, `b"7d"`, lists, tuples, dicts, `object()` |

Nothing is normalised: the function returns the input, returns `None` for `all`/`None`, or raises. The check runs after the off switch
(`IngestionDisabled` still comes first), after the text and `pages` checks and before region, language and the pre-flight.

## 6. `applied_since` provenance

- Source: only the foundation's echoed `min_upload_date` in the collection answer (the cutoff it actually gave `search.list`).
- Parsing: ISO-8601 with an offset or `Z`, converted to aware UTC. A missing, `None`, empty, non-string, malformed, date-only or
  offset-less value gives `None`. It is never computed from `period`, the provider clock or the response time.
- Evidence: the foundation-backed test runs the real route, then replays the foundation's **real answer** through the adapter and
  checks `applied_since` equals the instant search received (`test_the_echoed_min_upload_date_is_what_search_received_and_feeds_applied_since`).
  Unit tests cover `Z`, `+00:00`, `+05:00` (normalised), microseconds, and 12 malformed or absent forms.
- Channel collections never echo it, so `applied_since` is `None` there.

## 7. Acceptance criteria mapped to evidence

| # | Criterion (spec section 7) | Implementation | Evidence |
|---|---|---|---|
| 1 | Explicit period reaches the right upstream parameter; omitted body unchanged | `provider.py` `collect_query`, `_check_collect_period` | `test_omitted_period_sends_exactly_the_previous_request_body`, `..._valid_hour_periods_...`, `..._valid_day_periods_...`; foundation-backed `test_the_period_becomes_a_utc_published_after_of_now_minus_the_window` (1h, 24h, 7d, 30d, 9999h, 365d) |
| 2 | Invalid periods fail before any request | validator runs before `_preflight` | `test_invalid_periods_raise_value_error_before_any_request` (53 strings, each checked with `nf.requests == []`), `test_non_string_periods_are_rejected_before_any_request` (11 non-strings) |
| 3 | Existing collection behaviour backward compatible | `period` last, defaults None, body key dropped when None | `test_existing_positional_and_keyword_callers_still_work`, `test_period_is_the_last_parameter_with_a_none_default`, `test_ingestion_result_keeps_its_positional_field_order`; the existing `tests/test_ingestion.py::test_collect_query` passes **unmodified** |
| 4 | No duplicate YouTube client | `FoundationClient` is still the only client; no new HTTP code | diff shows no client, scheduler, quota or database code; `test_each_valid_call_makes_exactly_one_health_check_and_one_post` |
| 5 | No restricted metric introduced | no mapping, metric or sort touched | restricted-metric suites unchanged and green (D1 policy tests) |
| 6 | No quota-consuming request in offline tests | all tiers use recorded transport or faked YouTube functions | runner counts `requests` attempts and the parent asserts zero; no key; recorded transport |
| 7 | No automatic retry | no retry code | `test_no_retry_of_a_collection_with_a_period` (ReadTimeout, WriteTimeout, ConnectTimeout, PoolTimeout, ConnectError: exactly one POST) |
| 8 | Existing tests remain valid | none modified | full suite below; D1 strict xfails untouched |
| 9 | Documentation describes real period semantics | `PROVIDER_BOUNDARY.md`, `INGESTION_PROFILE.md`, this report, spec section 2 | foundation-backed pins: aliases, uppercase, `m` = 30 days, zero window, empty and `all` = no limit, invalid = HTTP 500 before search and before the niche row |
| 10 | Upstream unchanged | none | `git submodule status` `d872014`; empty diff for `upstream/` |
| 11 | Ruff clean; fast job and lock check unchanged | `ruff check .` passes; only additions under `.github/` | see test results |

Also required by the assignment: niche identity unchanged across periods: `test_different_periods_send_the_same_niche_identity`
(adapter: same `query`, no `label` or `niche` key) and `test_different_periods_write_into_the_same_niche` (real route: one niche row,
`home-espresso`, for no period, `24h` and `30d`).

## 8. Test results

Local PostgreSQL 16.2 with pgvector 0.6.2; the foundation-backed tests used the sandbox upstream Python (all upstream requirements).

| Command (abridged) | Result |
|---|---|
| `pytest tests/test_collect_period.py` | 119 passed |
| `pytest tests/test_collect_period_upstream.py` (database + upstream Python) | 35 passed |
| the five CI-selected files with `--junitxml`, then `ci_checks.py report` | 268 passed, 9 xfailed, 0 skipped, 0 failed, 154 s; report check exit 0 |
| full suite, database + upstream Python, `VT_TEST_REQUIRE_UPSTREAM=1` (CI-like) | **553 passed, 0 failed, 2 skipped, 9 xfailed** in 172 s; the 2 skips are the live-foundation tests |
| full suite, database only (the existing fast job's conditions) | 454 passed, 0 failed, 103 skipped, 7 xfailed in 46 s |
| full suite, plain `pytest` | 430 passed, 0 failed, 127 skipped, 7 xfailed in 20 s |
| `ruff check .` | All checks passed |

The 9 strict xfails of D1 are unchanged and still xfail (2 of them need the upstream Python). Live-foundation tests were not run.
Before D2 the full suite was 399 passed, 2 skipped, 9 xfailed; D2 adds 154 tests.

## 9. Known limitations

- The foundation fixes the search order at view count and the route ignores `order`, `category_id` and `video_duration`: a window means
  "most viewed inside it".
- One niche per query: collecting the same query with different periods mixes windows in one niche (approved).
- `search.list` returns about 500 results at most per query and `pages` stays capped by `VT_YOUTUBE_MAX_SEARCH_PAGES`.
- Whether YouTube treats `publishedAfter` as inclusive is inferred from its API reference, not verified here.
- `applied_since` is the foundation's cutoff, not proof of what YouTube returned.
- The root-cause defect (unset discovery filters) is **not** fixed: that is D3.
- The foundation accepts `0h`, uppercase, aliases and `m` (30 days); ViralTrack rejects them, so a direct caller of the foundation is not protected.

## 10. Statement

No live YouTube API request was made. No key was used (the offline route runner sets a placeholder that is never sent, and every
YouTube function is replaced). No quota was spent. Nothing was committed or pushed. The staged owner files are untouched.
