# F-6 investigation: the `short_form` (Shorts duration) filter

Date: 2026-11-06. Status: **implemented after the owner's decisions (section 8).** Sections 1 to 7 are the investigation as it was presented, kept as the record; section 8 is what was done.
Offline throughout; no YouTube request, no quota. The behaviour in section 3 was measured on the real pinned upstream route (`d872014`) over a synthetic corpus.

## 1. The original finding

| Where | Text |
|---|---|
| [YOUTUBE_DISCOVERY_AUDIT.md](YOUTUBE_DISCOVERY_AUDIT.md), findings table | **F-6**: "`short_form` filter uses the Shorts duration inference, which is a restricted *label*" (kind: **policy question**) |
| [DISCOVERY_REQUIREMENTS.md](DISCOVERY_REQUIREMENTS.md), duration row | "Shorts rule is a restricted label (F-6)"; duration itself is raw |
| [DISCOVERY_EXECUTION_ROADMAP.md](DISCOVERY_EXECUTION_ROADMAP.md) owner decision 4, and [D1_CLOSURE_REPORT.md](D1_CLOSURE_REPORT.md) question 4 | "Whether the Shorts duration filter may stay in the discovery request / be offered (audit F-6)" |

**Root cause (of the question):** upstream decides "Short" as `duration_seconds <= 180` (`SHORTS_MAX_SECONDS`), a heuristic, because the YouTube Data API has no Shorts flag. ViralTrack treats
the resulting **label** as RESTRICTED (`short_form_label`, Phase 1: "the guide says to use only the content type returned by the API"). `short_form=True/False` asks the foundation to partition
results by that same rule, so a restricted classification could decide which videos are listed even though the label itself is never shown.

**Scope / acceptance criteria as written:** the audit gives no acceptance criteria for F-6; it only asks for a decision. D1 recorded it as "tests do not claim the filter is acceptable".

## 2. What the project has already decided

| Source | Decision |
|---|---|
| [phase-1/OWNER_DECISIONS.md](../phase-1/OWNER_DECISIONS.md) section C | "Recommended policy (current behaviour, unchanged): keep the label RESTRICTED, every YouTube item is `VIDEO`; **keep the duration filter (<= 180 s): it filters raw data and claims nothing**; after the amendment show it as '<= 3 min (ViralTrack tag)', never as 'YouTube Short'." |
| [phase-1/DERIVED_METRIC_POLICY.md](../phase-1/DERIVED_METRIC_POLICY.md) | "Filtering by duration (<= 180 s) remains possible, because it filters raw data" |
| [phase-2/PHASE_2_EXECUTION_PLAN.md](../phase-2/PHASE_2_EXECUTION_PLAN.md) decision C | "Shorts label stays restricted. Unchanged. The duration filter stays" |
| Earlier owner instruction in this project (not recorded in the repository) | the Shorts duration filter stays; as remembered it is a *content-type filter*, wording the repository does not use |

So the repository already contains an answer, but D0/D1 and the roadmap still list it as an **open** question, and only the phrase "recommended policy" appears in Phase 1. The two descriptions differ in kind:
"filters raw data (a duration test)" versus "content-type filter" (which would claim a classification the policy forbids as a label). This needs the owner's explicit wording (question 1 below).

## 3. Current implementation (traced)

| Step | Behaviour | Evidence |
|---|---|---|
| Query | `DiscoveryQuery.short_form` / `SearchQuery.short_form`: `True` = only short-form, `False` = exclude, `None` = both | `viraltrack/providers/base.py` |
| Request | `_shorts_params`: `True` gives `only_shorts=true&exclude_shorts=false`; `False` gives `only_shorts=false&exclude_shorts=true`; `None` gives both `false`. Always sent, so upstream's own default (`exclude_shorts=True` on `/api/viral`) never applies | `provider.py`, `tests/test_youtube_provider.py` (`test_shorts_filter_is_allowed_but_label_is_restricted`), D1 request-parameter tests |
| Upstream rule | stored `is_short` (set at collection as `1 if duration <= 180`), falling back to the same duration test when NULL; then `exclude_shorts` / `only_shorts` filter the rows **before** the first funnel count | `application/collecting.py:149`, `application/discovery.py:124-130`, `domain/metrics.py:286` |
| Label | `isShort` becomes `ContentType.SHORT` only when `short_form_label` is exposable (needs the amendment); otherwise every item is `VIDEO` | `mapping.map_video`, test above |
| Capability text | "Filter by duration <= 180 s; the 'short' label itself is RESTRICTED (the API has no Shorts flag)" | `provider.CAPABILITIES` |

**Measured on the real route** (adapter query for `short_form` None / True / False over videos of 0, 1, 59, 60, 179, 180, 181, 240 and 599 seconds, all otherwise eligible):

| `short_form` | Durations returned |
|---|---|
| `None` | all nine |
| `True` | 1, 59, 60, 179, 180 |
| `False` | **0**, 181, 240, 599 |

Consequences: the boundary is inclusive at 180 s; a video of unknown or zero duration is **never** "short", so `True` leaves it out and `False` keeps it; the funnel does not show the Shorts
step (it is applied before the first count); the partition is the restricted rule, applied by upstream.

## 4. Comparison with the approved policy

| Policy point | Current behaviour | Verdict |
|---|---|---|
| The `short` label stays restricted | Every item is `VIDEO`; label only with the amendment | **Meets** |
| The duration filter stays | Offered, explicit values always sent | **Meets** |
| It filters raw data and claims nothing | Upstream applies a stored/derived classification, not a visible duration range; the caller cannot see or choose the 180 s threshold, and unknown duration is treated as "not short" | **Partly**: the effect is a duration test, the interface names a *format* (`short_form`) |
| After the amendment show "<= 3 min (ViralTrack tag)" | Not implemented (amendment not filed) | n.a. |

## 5. Missing tests and documentation

Tests missing:
1. No test pins upstream's threshold (`SHORTS_MAX_SECONDS == 180`); a submodule move could change the filter silently.
2. No real-route boundary test (179, 180, 181, zero/unknown duration) and no test of the `True` / `False` / `None` partition.
3. No test that a stored `is_short` value which disagrees with the duration decides the row (upstream uses the stored flag first).
4. No test that the Shorts step is absent from the funnel.
5. The Phase 2 test-plan case D5 ("results differ only by the filter") is documented but not automated against the real route.

Documentation missing or stale: D0/D1/roadmap still show F-6 as open; the `short_form` comment in `base.py` and the capability text do not say "duration <= 180 s, inclusive, unknown
duration is not short"; the stored-flag-first rule is nowhere recorded.

## 6. Smallest correction proposed (not implemented)

1. **No behaviour change.** Keep `short_form` and the explicit parameters.
2. **Record the decision**: replace the open question in the roadmap and D1 closure with the owner's confirmed wording (question 1), citing Phase 1 decision C and Phase 2 decision C.
3. **Comments and capability text only**: say "duration <= 180 s (inclusive); a video with unknown or zero duration is not counted as short" in `base.py` and `CAPABILITIES`.
4. **Tests** (offline): pin `SHORTS_MAX_SECONDS == 180` by reading the upstream source with `ast`; one real-route test of the boundary and of the three partitions; one test that a stored flag
   overrides the duration; one that the funnel has no Shorts step.
5. **Docs**: add the measured table above to the Phase 2 test plan (case D5).

Alternatives the owner may prefer: (a) rename the parameter to a duration limit (`max_duration_seconds`), which matches "filters raw data" literally but changes the public query type; (b) remove the filter until the
amendment is accepted (loses the `short_form` capability that Phase 1 documented as supported).

## 7. Questions for the owner

1. Confirm the wording: is the filter approved as **"a duration test (<= 180 s) on raw data"** (the repository's wording), or as a "content-type filter"? The second would contradict the restricted label.
2. Confirm that unknown or zero duration should stay "not short" (upstream behaviour; `True` excludes such videos, `False` includes them).
3. Keep the name `short_form`, or rename (alternative a)?

## 8. Owner decisions and implementation (2026-11-06)

Decisions: (1) `short_form` is a duration filter on raw metadata, not YouTube's Shorts classification; (2) inclusive threshold, at most 180 s; (3) zero is not short; (4) unknown, null or invalid
duration is not short; (5) the name `short_form` stays; (6) upstream `is_short` must not override the policy.

**Why more than comments and tests were needed.** Decision 6 cannot be met while the foundation does the filtering: it decides from its stored `is_short` flag first (a conflicting flag was proven to flip the result on the real route), and it treats zero
and unknown duration as "not short" only by accident of its fallback. So the filter moved into ViralTrack:

| Aspect | Behaviour now |
|---|---|
| Request | `only_shorts=false&exclude_shorts=false` always, for `/api/viral` and `/api/search` |
| Filter | after mapping: short = known duration with `0 < d <= 180`; `True` keeps those, `False` keeps the rest, `None` keeps all; the foundation's `isShort` is ignored |
| Duration reading | finite, non-negative number; anything else (missing, null, text, boolean, negative) is "unknown" and **not malformed** (an exception to the strict field typing of D3-02, per decision 4); `Content.duration_seconds` is then `None` |
| Limit | with a filter set, the foundation is asked for 1000 candidates (it has no cap) in the requested order and the caller gets at most `limit`; `limit` must be a whole number of 1 or more, and `short_form` a real boolean, else `ValueError` before any request |
| Page | `total` is `None` (the foundation's total counts every duration); a note states the rule; a second note says when the filter saw only the first 1000 candidates |
| Funnel | unchanged and without a Shorts stage; because the foundation no longer filters Shorts, its first count now includes them, and the page note says so |
| Label | unchanged: every item is `VIDEO` unless the amendment is approved |

Limitations: a filtered page is chosen from the first 1000 candidates of the requested order (flagged in a note when reached); the funnel counts videos of every duration.

Tests: unit tests in `tests/test_d3_discovery_fixes.py` (0, 1, 179, 180, 181 s, fractions, missing, null, invalid durations, conflicting `isShort`, true/false/None, no upstream filter, limit, funnel, label) and four real-route tests in
`tests/test_discovery_d1_upstream.py` (threshold pinned to upstream's `SHORTS_MAX_SECONDS == 180`, the partition = Phase 2 case D5, a conflicting stored flag, no Shorts funnel stage).

