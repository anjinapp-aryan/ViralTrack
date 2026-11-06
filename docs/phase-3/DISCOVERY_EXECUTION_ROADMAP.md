# Discovery execution roadmap (Task I)

Date: 2026-11-05. PROPOSAL. Nothing is started. Every stage needs the owner's explicit approval before work begins.

## Recommended minimum sequence

**D0 (this audit) -> D1 -> D2 -> D3 -> D7 -> D8.** D4 (explanation and confidence labels) is small and should ride with D3
if approved. D5 (dashboard/API) and D6 (history and tracking) are optional and should not start until D8 shows the
base works. Rationale: the zero-result problem is an adapter defect plus a keyword-collection default; fixing and
proving those is cheap and offline. Everything else builds on that.

Quota budget overview: D1 to D6 spend **0** YouTube quota. D7 spends at most **15 units and 1 search call** and needs a
separate approval. All other limits of earlier phases stay: thumbnails, transcripts, LLM and restricted metrics off.

## D0: diagnosis and audit (done)

Deliverables: the six documents in `docs/phase-3/`. Open owner decisions are listed at the end.

## D1: offline discovery correctness tests

**Status (2026-11-05): implemented, awaiting owner review. Not committed.** Report:
[D1_OFFLINE_DISCOVERY_TEST_REPORT.md](D1_OFFLINE_DISCOVERY_TEST_REPORT.md). Delivered: adapter-parameter,
upstream-semantics, funnel, failure-case and restricted-metric tests; a synthetic corpus; an offline runner for the
real upstream API; the corrected Phase 2 discovery test plan. **Production code was not changed.** Nine verified
defects and gaps were recorded as strict `xfail` tests that D2 and D3 must turn green (list in the report).
Update: D3 and the F-1/F-2 fix turned all nine green (see the D3 section); none remains.

| | |
|---|---|
| Objective | Prove, offline, that every discovery call sends an explicit, non-restrictive filter set, and reproduce the zero-result mechanism and its fix |
| Reusable | `tests/fixtures/niche_finder/`, `httpx.MockTransport`, the local demo-seeded foundation (no key, zero quota) for upstream-behaviour checks |
| Files likely to change | `tests/test_discovery_*.py` (new), `tests/fixtures/niche_finder/` (new synthetic corpus), `docs/phase-2/DISCOVERY_TEST_PLAN.md` (fix case D1) |
| Dependencies | None new |
| Tests | Section 3 of [DISCOVERY_VALIDATION_STRATEGY.md](DISCOVERY_VALIDATION_STRATEGY.md): the failing test first (omitted parameter), upstream `max_subscribers=0` behaviour, filter combinations |
| Acceptance | The new tests fail on the current adapter for the reasons in the audit and are documented as such; the corrected plan is reviewed |
| Risks | Upstream behaviour is inferred from source until run against the demo foundation |
| Dependencies | Owner approval of Phase 3 |
| Quota | 0 |
| Approval | Owner approves D1 scope |

## D2: candidate generation and source integration

**Status (2026-11-05): implemented as the keyword-collection `period` only, awaiting owner review. Not committed.**
Report: [D2_IMPLEMENTATION_REPORT.md](D2_IMPLEMENTATION_REPORT.md). The dedicated CI job for the upstream-backed
offline tests is implemented and has run green on GitHub: [D2_CI_IMPLEMENTATION_REPORT.md](D2_CI_IMPLEMENTATION_REPORT.md),
[CI_HARDENING_REPORT.md](CI_HARDENING_REPORT.md).

| | |
|---|---|
| Objective | Keyword and channel collection produce candidates inside the intended window |
| Reusable | `collect_niche` (`period`), `collect_channel`, worker `WORKER_QUERIES` / `WORKER_QUERY_PERIOD`, RSS novelty detection |
| Files | `viraltrack/providers/youtube/provider.py` (`collect_query` sends `period`), `viraltrack/providers/base.py`, `tests/test_ingestion.py`, `docs/phase-2/INGESTION_PROFILE.md` |
| New dependencies | None |
| Tests | Recorded-transport test that `period` reaches `/api/collect/niche`; `period` validated against the allowed set; no change to quota floors or the single-attempt rule |
| Acceptance | The request body carries `period`; documentation states the foundation orders by all-time views within the window |
| Risks | The route has no `order`, `category_id` or `video_duration`; accepting that limit is the cost of not modifying upstream |
| Quota | 0 for development (mock transport) |
| Approval | Owner approves the `collect_query` signature change |

## D3: configurable eligibility filters

**Status (2026-11-06): the seven discovery defect fixes and the F-1/F-2 threshold fix are implemented, awaiting owner review.
Not committed.** Report: [D3_DISCOVERY_DEFECT_FIX_REPORT.md](D3_DISCOVERY_DEFECT_FIX_REPORT.md). Done: funnel surfaced
(`ContentPage.funnel`), malformed entries refuse the whole page (owner decision), duplicate ids collapsed, boolean totals
rejected, both 24-hour velocity values and sorts removed while snapshot recency is unknown (owner decision), no lifetime
velocity without a publication date, one sort allowlist, the 1,000,000 subscriber bound enforced and documented, and
unset thresholds sent explicitly (`max_subscribers=1000000`, `min_views=0`; owner decision: **bounded, never unlimited**).
No strict xfail remains. Owner decision: the lifetime-velocity sort is removed (upstream ranks an undated video first), so the approved sorts
are `views` and `published_at` only (the engagement-rate sort was removed too: the foundation orders hidden likes as zero). F-6 is implemented: `short_form` is a duration filter (<= 180 s inclusive; zero, missing or
invalid duration is not short) applied by ViralTrack, not YouTube's Shorts classification ([F6_SHORT_FORM_INVESTIGATION.md](F6_SHORT_FORM_INVESTIGATION.md)).
Period, limit and region are validated before any request. **D3 is complete for the approved offline scope**; see
[PHASE_3_FINAL_COMPLETION_REPORT.md](PHASE_3_FINAL_COMPLETION_REPORT.md). D4 to D8 are not started (section "Remaining stages" of that report).

| | |
|---|---|
| Objective | Fix the zero-result defect and make filters explicit, visible and safe |
| Reusable | `/api/viral` filters, `/api/search` filters |
| Files | `provider.py` (`discover_content`, `search_content`), `base.py` (`DiscoveryQuery`, `ContentPage.funnel`), `domain/models.py` (funnel type), `mapping.py` untouched, tests |
| New dependencies | None |
| Tests | Every filter parameter present in every request; restricted metric never a filter or sort; `max_subscribers` sentinel works against upstream semantics; funnel surfaced; defaults documented |
| Acceptance | With the Batch 5-shaped fixture, discovery with unbounded subscribers and `min_views=0` returns the stored candidates and the funnel explains any reduction |
| Risks | Sentinel semantics (audit F-2); `short_form` filter policy question (F-6) |
| Quota | 0 |
| Approval | Owner approves the "unset means unbounded" rule, which differs from the foundation's defaults |

## D4: explainable ranking and confidence

| | |
|---|---|
| Objective | Order by one approved metric and explain each result |
| Reusable | `MetricRule.basis`, `Provenance`, `MetricPolicy` |
| Files | `viraltrack/discovery/explain.py` (new, pure functions), tests |
| New dependencies | None |
| Tests | Explanation coverage 100%; hidden likes, no history, stale and low-sample labels; no composite score; restricted sorts refused |
| Acceptance | Every returned item has an explanation; no numeric blended score exists anywhere |
| Risks | Whether single-metric ordering counts as "ranking" under the policy (requirements section 2.6) |
| Quota | 0 |
| Approval | Owner and counsel answer the ranking question |

## D5: discovery dashboard or API (optional)

Equals the deferred Batch 4. Needs a decision on FastAPI (already an upstream dependency, not a ViralTrack one), on
authentication, and on the rule that restricted data is never served. Do not start before D8. Quota 0.

## D6: historical discovery and tracking (optional)

| | |
|---|---|
| Objective | Read snapshot series and add candidates to the foundation watchlist |
| Reusable | `video_stats_history`, `/api/channels/track`, `/api/videos/trajectory`, `/api/channels/{id}/velocity`, worker refresh |
| Files | `provider.py`, `base.py` (new capability), tests, `DATA_RETENTION_POLICY.md` if anything is persisted (it should not be) |
| Tests | Series mapping; velocity labelled with its real window; watchlist add is a spending call and follows the ingestion switch |
| Quota | Refresh passes cost about 1 unit per 50 videos; budget set per run |
| Approval | Owner approves refresh schedule and quota ceiling |

## D7: controlled real-data validation

| | |
|---|---|
| Objective | Show that discovery returns real, explainable results from a fresh sample |
| Plan | The corrected discovery test plan on a new empty database |
| Budget | **At most 15 units and 1 search call**: one keyword with `period` (about 3 units), one channel capped at 20 videos (about 3), one refresh pass for a second snapshot (about 1 to 2), reads free |
| Stop conditions | Quota accounting uncertain; budget would be exceeded; any restricted metric appears; foundation hint reports a filter that removed all items without being explained |
| Tests | Section 5 of the validation strategy |
| Acceptance | Non-empty result under explicit filters, funnel recorded, quota within budget, sample database dropped afterwards, aggregate evidence kept |
| Risks | A single keyword and a single channel are a small sample; a second snapshot needs waiting time for a meaningful velocity |
| Approval | Separate, explicit, with the budget written in |

## D8: discovery release gate

Offline suite green; D7 evidence reviewed; open compliance questions answered or recorded as limits; readiness
document updated. Output: PASS / PASS_WITH_LIMITATIONS / BLOCKED.

## Owner decisions needed before D1

1. Approve Phase 3 scope D1 to D4 (and D7 separately later).
2. Approve the principle "an unset filter is sent as unbounded".
3. Single-metric ordering and text-search similarity ordering: acceptable under the derived-metric policy?
4. Whether the Shorts duration filter may be offered (F-6).
5. Whether Batch 4 (API) belongs in Phase 3.
