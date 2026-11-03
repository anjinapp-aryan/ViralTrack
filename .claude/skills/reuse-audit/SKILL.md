---
name: reuse-audit
description: Before implementing a ViralTrack capability, decide whether an existing implementation should be reused, adapted, composed or built. Use before writing any significant new functionality, provider, algorithm, UI feature or dependency.
---

# reuse-audit

**Do not implement code until the reuse decision is made for significant functionality.**

## Steps

1. **Define the capability.** One sentence on what is needed and which requirement it serves.
2. **Search this repository.** Look in `viraltrack/` and `tests/`, and in `docs/phase-0/REUSE_MATRIX.md` and
   `docs/phase-1/`.
3. **Search the adopted foundation.** Look in `upstream/youtube-niche-finder`: its HTTP API reference
   `upstream/youtube-niche-finder/docs/http-api.md`, `backend/application/`, `backend/domain/metrics.py` and the frontend screens. Most
   YouTube features already exist there.
4. **Search dependencies.** Check what `pyproject.toml`, `requirements-dev.lock` and the foundation's
   `backend/requirements.txt` already provide.
5. **Search GitHub and open source**, when the first three steps come up empty. Use `gh search repos` and
   `gh api`, with several phrasings. Record the queries you ran.
6. **For each serious candidate**, check:
   - **Source:** read the actual code, not the README. Find the code path that implements the capability.
   - **License:** the LICENSE file at the commit, not the badge. Use the `license-audit` skill.
   - **Maintenance:** last meaningful commit, contributors, releases.
   - **Tests:** does it have tests, and do they pass? Run them when the candidate is a finalist.
   - **Deployment:** Docker, configuration, runtime requirements.
   - **Data and platform restrictions:** is its data source legitimate? A permissive license does not make
     scraping acceptable.
7. **Compare** the candidates in a table: capability fit, license, data legitimacy, tests, maintenance,
   integration effort.
8. **Recommend exactly one** of:
   - **REUSE**: use as-is.
   - **ADAPT**: change existing code, at the ViralTrack boundary, never inside `upstream/`.
   - **COMPOSE**: combine existing services or APIs.
   - **BUILD**: write new code, only for the gap no candidate fills. Say why each candidate was unsuitable.

## Output

```text
Capability:
Searched: repo / foundation / dependencies / GitHub (queries)
Candidates: table
Decision: REUSE | ADAPT | COMPOSE | BUILD
Reason:
Gap to build (if any):
Risks / open questions for the human:
```

Stop and ask for approval if the decision changes the architecture, adds a data source or adds a large
dependency.
