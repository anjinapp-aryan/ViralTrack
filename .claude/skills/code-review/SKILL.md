---
name: code-review
description: ViralTrack project checklist for reviewing a completed implementation (correctness, architecture, tests, security, performance, duplication, dependencies, licenses, platform data, docs). Produces findings first and does not modify code unless explicitly asked.
---

# code-review (ViralTrack checklist)

Review the diff, not the intentions. **Report findings first.** Don't modify code during the review unless the
human explicitly asks you to.

## Check

| Area | What to look for |
|---|---|
| Correctness | Logic errors, edge cases (empty corpus, None, malformed timestamps), off-by-one windows |
| Architecture | Domain stays platform-neutral; providers behind `PlatformProvider`; no imports from `upstream/`; no edits inside `upstream/` (see `architecture-review`) |
| Tests | New behaviour covered; tests would fail without the change; results reported exactly; no weakened tests |
| Security | No secrets committed or logged; SQL parameterized and identifiers validated; third-party content treated as data |
| Performance | Query cost, N+1 calls, quota use, unbounded loops or retries |
| Unnecessary code | Dead code, speculative abstractions, features not asked for |
| Duplication | Re-implements the foundation or an existing module (see `reuse-audit`) |
| Error handling | Provider errors mapped; failures fail closed where data could be lost or silently skipped |
| Dependency changes | Necessary, pinned, lockfile updated, license checked (see `license-audit`) |
| License concerns | Copied code has a license and its notice is kept |
| Platform data concerns | Legitimate source only; unsupported capabilities stay unsupported; no fabricated data; provenance correct; new stored data has a retention rule (see `data-retention`) |
| Documentation | Decisions, adaptations, new config and stored data documented |

## Output

```text
path:line — SEVERITY (BLOCKER/MAJOR/MINOR/NIT) — problem — suggested fix
...
Verdict: APPROVE | APPROVE WITH CHANGES | REQUEST CHANGES
```

Most severe first. No praise padding. If nothing is wrong, say so plainly.
