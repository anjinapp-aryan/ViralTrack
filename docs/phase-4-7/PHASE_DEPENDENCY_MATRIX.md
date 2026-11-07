# Phase dependency matrix (phases 4 to 7)

Date: 2026-11-07.

| Phase | Needs (earlier work) | Needs (decisions) | May run offline | Needs legal review | Needs live authorization | New dependency expected |
|---|---|---|---|---|---|---|
| D3 (done) | none | none | yes | no | no | none |
| D4 explanations and confidence | D3 | Decisions 1 and 2 | yes (design now; code after approval) | yes (ranking and claims) | no | none |
| D5 API and dashboard | D3; D4 for display wording | Decisions 2 and 3 | yes | yes (wording, authentication, exposure) | no | FastAPI/pydantic (already in the foundation), `schemathesis` dev-only, optional htmx |
| D6 history and watchlists | D3; timestamp audit; D5 for any user-facing view | Decisions 2 and 4 | yes (audit and design); persistence needs retention approval | yes (storage beyond 30 days) | no (uses recorded foundation data) | none expected |
| D7 live validation | D3 pushed and CI green (done); harness ready | Decision 5 | preparation only | no, but API-terms check of stored data | **yes, explicit and specific** | none |

Order recommended: decisions 1 and 2, then D4 design, then D5, then D6; D7 can run after the harness is prepared and independently of D4 to D6, because it validates D3 behavior on real data. D7 should not wait for D5 or D6, and D5 or D6 should not wait for D7 unless the owner wants real-data confirmation first.

Hard gates (from the master prompt): no restricted metric in any output; no manufactured confidence; no history inferred from current values; no live call without explicit approval; no change to the submodule; no commit or push without approval.
