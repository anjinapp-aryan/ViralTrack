# Making `discovery-offline` a required check

Date: 2026-11-07. Inspection only; no repository or GitHub setting was changed.

## Verified facts

* Workflow `CI` (`.github/workflows/ci.yml`) runs on push to `main`, on every pull request, on manual dispatch and weekly. Jobs: `viraltrack`, `discovery-offline`, `upstream-suite` (only on schedule or manual dispatch, so it is skipped otherwise). The jobs have no `name:`, so the check names are the job ids.
* For commit `907c601` the check runs are `viraltrack` success, `discovery-offline` success, `upstream-suite` skipped (`gh api .../commits/907c601/check-runs`). The same job passed on `b51498d` and earlier hosted runs failed only for the already-fixed stub-permission defect.
* Caveat: every hosted run so far was a **push** event. The job has no event restriction, so it should run on pull requests, but that has not been observed. Open one pull request before relying on it.
* `main` has no branch protection (`GET .../branches/main/protection` returns 404) and there are no rulesets (`GET .../rulesets` returns `[]`). So no existing required check can be weakened. The caller has admin permission on the repository.

## Recommendation

Require `viraltrack` and `discovery-offline`. Do not require `upstream-suite` (skipped on normal runs; GitHub treats a skipped required check as passing, so requiring it adds nothing).

Consequence to decide: a required check blocks direct pushes to `main` unless bypassed. The current workflow pushes straight to `main`, so either switch to pull requests, or add the owner as a bypass actor, or leave "do not allow bypassing" off. Do not enable "require branches to be up to date" until the job duration (about a few minutes) is acceptable.

## Steps (owner, in the GitHub web interface)

Settings, Rules, Rulesets, New branch ruleset: target branch `main`; enable "Require status checks to pass"; add `viraltrack` and `discovery-offline` (the names appear in the picker only after they have run on the repository); add the owner as bypass actor if direct pushes should continue; save as Active.

Equivalent command (needs admin; not run):

```bash
gh api -X POST repos/anjinapp-aryan/ViralTrack/rulesets --input - <<'JSON'
{"name": "main requires CI", "target": "branch", "enforcement": "active",
 "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
 "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}],
 "rules": [{"type": "required_status_checks",
            "parameters": {"strict_required_status_checks_policy": false,
                           "required_status_checks": [{"context": "viraltrack"},
                                                      {"context": "discovery-offline"}]}}]}
JSON
```

(`actor_id` 5 is the repository Admin role.) Verify afterwards with `gh api repos/anjinapp-aryan/ViralTrack/rulesets` and one pull request showing both checks as required.
