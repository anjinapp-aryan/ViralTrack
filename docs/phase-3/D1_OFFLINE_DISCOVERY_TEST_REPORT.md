# D1: offline discovery correctness and regression tests (report)

Date: 2026-11-05. Scope: D1 only. **Production code was not changed.** No YouTube request was made, no quota was spent,
the upstream submodule is unchanged (`d872014`). Not committed.

Labels: VERIFIED FACT (observed by running the real upstream code offline or read in source), INFERENCE, UNKNOWN.

## 1. What was built

| File | Purpose |
|---|---|
| `tests/test_discovery_d1_adapter.py` (35 tests) | D1-A: what the ViralTrack adapter and client send; counts, failures and gaps on the adapter side. Runs anywhere (mock transport) |
| `tests/test_discovery_d1_upstream.py` (53 tests) | D1-B/C/E: the **real** upstream route and filter code over a synthetic corpus; unbounded semantics; filter combinations against an independent oracle; funnel; limits; data problems; Batch 5 replay |
| `tests/test_discovery_d1_policy.py` (35 tests) | D1-D: real upstream answers (which contain every restricted field) replayed through the adapter; sort refusal; hidden likes; snapshots |
| `tests/support/synthetic_corpus.py` | Deterministic synthetic corpus (13 videos, 6 channels) and a Batch 5-shaped corpus (70 videos, 3 recent, channels above 10,000 subscribers); independent oracle |
| `tests/support/upstream_runner.py`, `tests/support/upstream.py` | Runs the pinned upstream API in-process with FastAPI's `TestClient`. No socket, no uvicorn |
| `docs/phase-2/DISCOVERY_TEST_PLAN.md` | Case D1 corrected; section 3.1 documents the verified semantics |

How the real upstream runs offline without credentials: the runner needs a Python with the upstream requirements
(`VT_TEST_UPSTREAM_PYTHON`); the tests seed a PostgreSQL schema built from the upstream DDL (`VT_TEST_DATABASE_URL`).
The runner removes `YOUTUBE_API_KEY`, replaces `requests` (the only library upstream uses to reach YouTube) with a guard
that counts and refuses every call, accepts only `GET /api/...`, and every test asserts **zero network attempts**.
No dependency was added to ViralTrack. Without the two environment variables the upstream-backed tests skip; the
adapter tests and the upstream route-default tests (read from source) still run.

All data is synthetic (ids `D1V...` and `UCD1C...`, titles "Synthetic video ..."). Ages are relative to the seeding time
and never sit on a window boundary (24 h, 48 h, 7 d and 30 d windows are clear of every video), so results do not
depend on the time of day.

## 2. Root-cause regression (item 6 of the acceptance list)

| Test | Result | Meaning |
|---|---|---|
| `test_omitted_thresholds_become_restrictive_defaults_and_the_response_says_so` | passes | VERIFIED: omitted `max_subscribers` and `min_views` become 10,000 and 10,000, and the response echoes them in `filters` |
| `test_batch_5_replay_the_adapter_query_keeps_candidates_and_the_old_query_loses_them` (was `..._old_adapter_query_returns_zero_...`; rewritten after the F-1/F-2 fix, which makes the adapter send both thresholds; the old query is kept as evidence) | passes | VERIFIED: the exact query ViralTrack sends for `period=30d`, replayed on a Batch 5-shaped corpus, gives the funnel `videos in window 3 -> channel subs <= 10,000 0 -> video views >= 10,000 0` and 0 results. Adding an explicit subscriber bound and `min_views=0` returns the 3 candidates |
| `test_an_unset_subscriber_filter_must_not_fall_back_to_the_foundation_default` | **xfail (strict)** | The defect, stated as the required behaviour. Fails today |
| `test_an_unset_minimum_views_filter_must_not_fall_back_to_the_foundation_default` | **xfail (strict)** | Same |
| `test_the_batch_5_query_sends_every_threshold_explicitly` | **xfail (strict)** | Same, for the Batch 5 query |
| `test_the_client_drops_none_parameters_and_keeps_falsy_ones` | passes | VERIFIED mechanism: None is dropped, `0`, `""` and `False` are kept |

I checked, in memory only, that the three xfail tests pass once `None` becomes an explicit value; with the marker left
on, strict mode will fail the build at that point and force its removal.

## 3. Upstream defaults and unbounded semantics

VERIFIED by AST reading of `interfaces/http/api.py` and by running the route:

| Route | Parameter | Default |
|---|---|---|
| `/api/viral` | `max_subscribers` / `min_views` / `min_views_per_subscriber` | 10000 / 10000 / 1.0 |
| `/api/viral` | `exclude_shorts` / `period` / `period_by` / `limit` / `sort_by` | True / 7d / published / 24 / `viral` (restricted) |
| `/api/search` | `max_subscribers` / `period` / `min_outlier_score` | None / all / 0.0 (no thresholds) |

Value sent as `max_subscribers` on `/api/viral` (13-video corpus):

| Value | Result | Verdict |
|---|---|---|
| omitted | 10,000 applied | restrictive default |
| `0` | 2 videos: only channels with 0 or **hidden** subscribers | **does not disable**; the audit's mistake, now guarded |
| `-1` | only hidden-subscriber channels | filter active |
| empty, `null`, `None`, `none`, `unlimited`, `1.5` | HTTP 422 | no null spelling exists over HTTP |
| `2147483647`, `1000000000000` | all 13 videos | passes everything upstream; **not** a ViralTrack setting: the approved maximum is 1,000,000, a bounded limit (D3-07B) |

For `min_views`: omitted gives 10,000; `0` disables (the code tests truthiness); a negative value is applied but passes all.
`preset=niche_all` is the upstream's own unbounded form but requires a `niche`.

**Unbounded semantics: partly resolved.** There is no literal "no limit" for subscribers over HTTP. A very large integer
behaves as unbounded for any channel below it. That channels never exceed such a number is an **INFERENCE**
about YouTube, not something the tests prove. I did not add a workaround; adopting the sentinel is an owner decision
for D3 (audit F-2). The unit tests pin the behaviour so that a change in the pinned upstream is noticed.

## 4. Filter coverage (D1-B)

Each filter was checked alone and combined; the independent oracle (written from the corpus definitions, not copied
from upstream) agrees with the upstream funnel in all 8 scenarios, stage by stage:

| Scenario | Stage counts (window, subscribers, views) | Final |
|---|---|---|
| route defaults, 30 d | 9, 7, 5 | 5 |
| window only (30 d) | 10 | 10 |
| no window | 13 | 13 |
| subscribers <= 10,000 | 13, 10 (the 10,001 channel and the 250,000 one are out) | 10 |
| views >= 10,000 | 13, 13, then views stage | oracle |
| all three, Shorts kept | oracle-checked | oracle |
| 7 d window | oracle-checked | oracle |
| subscribers <= 600 | oracle-checked | oracle |

Single-case checks: subscriber limit inclusive at exactly 10,000 and exclusive at 10,001; hidden subscribers pass a
limit; zero-subscriber channels are valid candidates; undated videos are in `period=all` but not in a dated window;
a missing view count counts as 0 views; old videos leave a 30-day window; Shorts are removed before the first funnel
count.

## 5. Funnel coverage (D1-C)

VERIFIED: the production `/api/viral` response **does** expose `funnel` (list of step and remaining), `filters`, `hint`,
`matched` and `quotaUsed`. The ViralTrack adapter drops the funnel (xfail test).

The requested pipeline maps to reality as follows:

| Requested stage | Reality |
|---|---|
| Raw candidates | **Not reported.** The funnel's first count is after the window, Shorts exclusion, niche, region and category filters. With defaults it is 9 while 13 videos are stored. Raw size stays UNKNOWN from the funnel |
| Date-window eligibility | First funnel step ("videos in window") |
| Subscriber eligibility | Step "channel subs <= N" |
| View eligibility | Step "video views >= N" |
| Metric eligibility | **Does not exist upstream** for approved metrics. Missing velocity or engagement removes no candidate and adds no step (tested); a candidate lacking the sort metric is listed last, not dropped |
| Final candidates | `results`, truncated to `limit`; `matched` is the pre-limit count |

Also tested: the funnel never increases; a zero result names the stage that emptied it (with the hint); one-result and
many-result cases; `limit` 1, 5, 13 and 50 truncate the page and never change `matched`; there is no offset or page
parameter, so a second page cannot be requested (unknown parameters are ignored).

## 6. Restricted-metric protection (D1-D)

Policy checked in the repository: 4 allowed, 10 restricted, 2 internal-only (`test_policy_inventory...`, plus a module
level assertion in the new policy tests).

- Precondition (VERIFIED): the real upstream answer carries the restricted fields, so the protection is meaningful.
- None of the 12 restricted or internal-only metric names survives the adapter for any of the 13 videos; no restricted
  name or field appears in the serialised result; no domain class has a field named score, rank, viral, breakout or outlier.
- Sorting by each of the 12 names is refused before any request, for discovery and for search.
- Only the six approved orders (views, published, three velocities, engagement) can be requested; upstream's default sort
  (`viral`) is restricted, and the adapter always names its sort.
- Hidden likes: upstream reports an engagement rate (it counts hidden likes as 0); ViralTrack omits it.
- No snapshots or one snapshot: no 24-hour metric (not zero). Two snapshots: a velocity whose note says the window varies.
- A two-hour history is reported as a "24 h" rate with only the generic caveat (characterised; see gaps).

## 7. Failure cases (D1-E): coverage of the 16 requested

| # | Case | Covered by |
|---|---|---|
| 1-3 | Zero, one, many | upstream funnel tests and adapter mapping tests |
| 4, 5 | All excluded by subscribers / by views | zero-result tests and the Batch 5 replay |
| 6 | Missing subscriber count | hidden-subscriber tests |
| 7 | Missing view count | missing-view tests |
| 8 | Missing publication date | undated tests (and a gap, below) |
| 9, 10 | Missing / stale snapshots | policy tests (stale is a gap) |
| 11 | Duplicate video ids | impossible in the foundation (unique key, tested); a duplicate inside one response is returned twice (gap) |
| 12 | Invalid candidate data | real-data id check, missing ids, non-object entries (gap) |
| 13 | Partial upstream failure | 500, 502, 503; missing `results`; client timeout (one attempt, typed error) |
| 14 | Pagination boundary | limit tests above |
| 15 | Unbounded behaviour | section 3 |
| 16 | Restricted-metric protection | section 6 |

## 8. Known gaps (strict xfail: fixed by D2/D3, then the marker must go)

| # | Gap | Test | Stage |
|---|---|---|---|
| 1-3 | Unset filters omitted, so upstream defaults apply (3 tests) | adapter file | D3 |
| 4 | The foundation's funnel is not surfaced | `test_the_foundations_funnel_reaches_the_caller` | D3 |
| 5 | Non-object entries in `results` are dropped without being counted | `test_invalid_entries_are_not_silently_dropped` | D3 |
| 6 | Duplicate video ids in one response are returned twice | `test_duplicate_video_ids_in_one_response...` | D3 |
| 7 | A JSON boolean is accepted as the total (`bool` is an `int`) | `test_a_boolean_total_is_not_a_count` | D3 |
| 8 | Velocity from weeks-old snapshots is presented like a current one; no snapshot time reaches ViralTrack | `test_velocity_from_stale_snapshots...` | D3/D6 |
| 9 | An undated video gets a lifetime velocity computed from age 0 (floored to 1 h) | `test_an_undated_video_has_no_lifetime_velocity` | D3 |

Characterised, not failing: the 24-hour label on a 2-hour window (the note says only that the window "varies").

## 9. Test results

Local PostgreSQL 16.2 with pgvector 0.6.2, run on 2026-11-05 (pytest, `-p no:cacheprovider`):

| Run | Environment | Result |
|---|---|---|
| A | database + upstream Python (everything runs) | **399 passed, 0 failed, 2 skipped, 9 xfailed** in 151 s |
| B | database, no upstream Python (what GitHub CI provides) | 335 passed, 0 failed, 68 skipped, 7 xfailed in 42 s |
| C | plain `pytest` | 311 passed, 0 failed, 92 skipped, 7 xfailed in 20 s |

- The 2 skips in A are the live-foundation tests (`VT_TEST_FOUNDATION_URL` not set).
- The 9 xfailed are the strict gap tests of section 8 (7 need no upstream; 2 replay tests need it).
- New D1 tests alone: 123 (35 adapter, 53 upstream, 35 policy) = 114 passed + 9 xfailed in A.
- Before D1 the suite was 285 passed, 2 skipped (full run); the existing tests still pass unchanged.
- Ruff: all checks passed.
- Zero network attempts were reported by the runner in every upstream-backed test, and no YouTube key was set.

## 10. Other checks

- Mutation: restoring the previous version of the test plan makes the "no document uses 0 to disable the subscriber
  filter" test fail; with the corrected plan it passes. That test is what prevents the `max_creator_followers=0` mistake
  from returning in the documents.
- Ruff: clean. `git diff` shows only tests, test support, documentation; no file under `viraltrack/`, `deploy/`,
  `docker-compose.yml` or `upstream/` changed.
- Sandbox: the probe schema created while exploring (`vt_d1_probe`) was dropped; each test schema is dropped by its fixture.

## 11. Remaining blockers and limits

- The upstream-backed tests need a Python with the upstream requirements and a PostgreSQL server. **GitHub CI has neither
  for the ViralTrack job**, so they skip there. Running them in CI needs installing the upstream requirements in that
  job, which is a workflow change and a new CI dependency set: not done, needs approval.
- The funnel's raw count is UNKNOWN by construction; D3 must decide whether to read `/api/stats` for it.
- The sentinel for "no subscriber limit" is unresolved as a design (section 3).
- The open compliance questions from the audit (single-metric ordering, text-search ordering by internal semantic score,
  the Shorts duration filter) are untouched; no test claims they are acceptable.
- The synthetic corpus is small; the real upstream rules are exercised, real YouTube data is not.

## 12. Production changes that D2 and D3 would need (not made)

D2: `collect_query` sends `period`; the foundation orders by all-time views inside that window.
D3: send explicit values for every discovery filter (`max_subscribers`, `min_views`, and keep `min_views_per_subscriber=0`);
decide the subscriber sentinel; surface `funnel` and the effective `filters` on `ContentPage`; count or reject non-object
entries and duplicate ids; reject boolean totals; treat undated videos' lifetime velocity as unknown; decide how to label
velocity computed from old or short snapshot windows.
