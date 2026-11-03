---
name: architecture-review
description: Review a proposed or in-progress ViralTrack change for architectural correctness (domain/platform coupling, provider abstraction, dependency direction, duplication, upgradeability). Use before significant implementation and when a change touches more than one layer.
---

# architecture-review

Return findings **before** modifying any code. Change code only after the human agrees.

## Reference architecture

```text
viraltrack/domain  <-  viraltrack/providers/base  <-  viraltrack/providers/<platform>  ->  foundation / API
                                                       viraltrack/retention  ->  foundation database
upstream/  (never edited)
```

Sources: `docs/phase-1/ARCHITECTURE.md`, `PROVIDER_BOUNDARY.md`, `DEPENDENCY_BOUNDARIES.md`.

## Checklist

| Area | Question |
|---|---|
| Domain/platform coupling | Does `viraltrack/domain` stay free of platform names, fields and imports? |
| Provider abstraction | Does platform access go through `PlatformProvider`? Are capabilities declared honestly? |
| Dependency direction | Do imports point inward? Does any ViralTrack code import from `upstream/`? |
| Duplication | Does this reimplement something the foundation or an existing module already does? Run `reuse-audit` if unsure |
| Dependencies | Is every new dependency necessary, licensed acceptably and small? Large ones need approval |
| Scalability | Quota, request volume, query cost, data growth |
| Testability | Can it be tested without a live platform: fixtures, mock transport, real DDL? |
| Future platforms | Would Instagram or TikTok fit without changing the domain? |
| Maintainability | Is it small and clear, and does it follow existing patterns? |
| Upstream upgradeability | Does it rely on upstream internals instead of documented contracts? Is the coupling guarded by a test? |
| Data | Does it persist provider data? If yes, run `data-retention` |

## Output

One line per finding: `severity (BLOCKER/MAJOR/MINOR) — location — problem — suggested direction`.
End with a verdict: **APPROVE / APPROVE WITH CHANGES / RETHINK**. Architecture or adoption-strategy changes
always need explicit human approval.
