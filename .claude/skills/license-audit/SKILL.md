---
name: license-audit
description: Audit open-source licensing for code, dependencies, Docker images, model weights and assets that ViralTrack reuses or plans to reuse. Use before adopting a project or dependency, before copying any file, and when the foundation pin changes.
---

# license-audit

This is an engineering screen, not legal advice. Flag questions for a human; don't make legal conclusions.

## Check

1. **Repository license.** Read the actual `LICENSE` file at the commit you will use; badges and package
   metadata can be wrong. A repository with no license file means all rights reserved: **DO NOT USE** its code.
2. **Copied files.** List every file copied into ViralTrack, with source, commit and license. Keep notices.
3. **Modified files.** Every modification of reused code must be documented. Code under `upstream/` is
   never modified.
4. **Dependencies.** Direct dependencies, plus transitive ones when distributing (e.g. `pip-licenses`,
   `license-checker`). Treat UNKNOWN metadata as an open item.
5. **Docker images.** Base images and service images, with tags pinned.
6. **Model weights and datasets.** These are licensed separately from code (check the Hugging Face card).
7. **Bundled assets.** Fonts, images, screenshots. Screenshots may show third-party content.
8. **Attribution.** What each license requires; update `THIRD_PARTY_NOTICES.md`.
9. **Compatibility** with ViralTrack's distribution model. ViralTrack has no license yet, which is an open
   owner decision.

## Classification

| Verdict | When |
|---|---|
| **REUSE** | MIT, Apache-2.0, BSD-2/3-Clause, ISC, 0BSD, Unlicense; notices kept |
| **REUSE WITH CONDITIONS** | LGPL/MPL used as unmodified libraries; Apache-2.0 NOTICE obligations; attribution required |
| **REVIEW REQUIRED** | GPL, AGPL, BUSL, custom, dual or unclear licenses; UNKNOWN metadata; license changes between versions |
| **DO NOT USE** | No license, proprietary, non-commercial, or terms that forbid the intended use |

Already reviewed and accepted: psycopg2-binary (LGPL), certifi and tqdm (MPL), all unmodified. See
`docs/phase-1/OPEN_SOURCE_ADOPTION_AUDIT.md`.

## Output

Table: `Component | Source@commit | License (as read) | Verdict | Conditions / notes`, followed by the
unresolved items. Remember that a permissive code license says nothing about the legitimacy of the data a
tool collects; judge that separately.
