# Agent Workflow

For every significant task:

```text
EXPLORE → REUSE AUDIT → PLAN → IMPLEMENT → TEST → REVIEW → DOCUMENT → HUMAN APPROVAL
```

Trivial tasks (a typo, a one-line fix) may skip the reuse audit and planning steps, but never testing or approval.

| Step | What to do | Skill | Output |
|---|---|---|---|
| **1. EXPLORE** | Read the relevant code, docs and tests. Understand the current behaviour before proposing changes. Read the code itself; don't assume from READMEs | — | What exists, what is missing |
| **2. REUSE AUDIT** | Repository → dependencies → foundation → open source | `reuse-audit`, `license-audit` | REUSE / ADAPT / COMPOSE / BUILD decision |
| **3. PLAN** | Smallest change that meets the requirement. Note affected layers and stored data | `architecture-review`, `data-retention` if data is stored | Plan + findings; ask for approval if architecture, data source, licensing or large dependencies change |
| **4. IMPLEMENT** | Small, focused edits. No unrelated refactors. Nothing inside `upstream/` | `provider-development` for providers | Code |
| **5. TEST** | Focused tests first, then the broader suite. Exact results | `testing` | Passed / failed / skipped / duration |
| **6. REVIEW** | Self-review the diff against the checklist. Findings first | `code-review` | Findings + verdict |
| **7. DOCUMENT** | Decisions, adaptations, config, stored data and retention, test results | — | Updated `docs/` |
| **8. HUMAN APPROVAL** | Show `git status`, changed files, test results and open risks. Then stop | — | **No commit, push or merge without explicit approval** |

## Stop conditions (ask the human)

- The task needs a new data source, or one whose legitimacy is unclear.
- A license needs review (GPL, AGPL, LGPL, MPL, BUSL, custom, unclear, none).
- The architecture or adoption strategy would change.
- A test would need to be removed or weakened.
- A large dependency would be added.
- Instructions conflict, or the request is ambiguous in a way that changes the outcome.

## Phase discipline

Each phase ends with a final report and stops. Don't start the next phase, or work that belongs to it,
without explicit approval.
