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
