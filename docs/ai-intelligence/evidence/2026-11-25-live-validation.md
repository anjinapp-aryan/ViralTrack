# Live validation, 2026-11-25 (aggregates only)

Run under `LIVE_VALIDATION_PLAN.md`, approved by the owner on 2026-11-25. No titles, ids or tags are kept here.

- Classifier version: `ai-content-rules/1.0.0`
- Database: local throwaway `vt_real`. Foundation at `d872014`, no worker.
- Collection: 10 `collect_market` searches, 1 page each, period 7d, no retries.
  - Markets: IN x4 (kn, hi, ta, te), US x2 (en), KR (ko), JP (ja), BR (pt), GB (en).
- Spend: 30 units, 10 search calls. Each search stored 50 videos, 500 in total.

## Classification, 7-day window

| | Videos |
|---|---|
| Examined | 500 |
| Excluded as gaming | 50 |
| Confirmed AI | 10 |
| Likely AI | 27 |
| Possibly AI | 50 |
| Unclassified | 363 |

Categories among the 37 videos in the default view (confirmed + likely): AI stories and explainers 23, AI music
or audio 6, AI music videos 4, unknown 4.

Discovery market, by videos in the default view: US 15, IN 10, GB 5, BR 4, JP 4, KR 3.
Languages: en 22, hi 5, ta 3, ja 2, ko 2, te 2, zh 1. No Kannada AI video matched.

## Checks

- Response-key scan of `/api/v1/ai/{summary,content,countries,opportunities}`: no restricted or foundation-only
  key. Passed.
- `/api/v1/ai/opportunities`: 4 groups.
- Retention report (`python -m viraltrack.retention`, report mode): 0 rows affected, 0 rows of unknown age.
- Not done: the 20-item manual review of classification evidence. It needs the owner.
