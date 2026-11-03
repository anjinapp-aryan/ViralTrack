# ViralTrack License Decision

**Status: recommendation; the owner's decision is needed.** No license file was added: choosing a license is
hard to reverse once others rely on it. This is not legal advice.

## Facts

| Item | Finding |
|---|---|
| ViralTrack code | ~1,500 lines in `viraltrack/` plus ~760 lines of tests and the docs, all original |
| Repository visibility | **Public** on GitHub (`anjinapp-aryan/ViralTrack`), currently with **no license**, which means all rights reserved: others may read it but not use, copy or modify it |
| Foundation | youtube-niche-finder, MIT, an unmodified submodule. MIT is compatible with any outbound license, including proprietary. Its notice must be kept (done: `THIRD_PARTY_NOTICES.md`) |
| Dependencies | Permissive, plus LGPL psycopg2-binary and MPL certifi/tqdm used unmodified. None of these forces a copyleft license on ViralTrack's own code |
| Distribution model | The phase documents describe a commercial product ("commercial ViralTrack"). Whether it is open source, source-available or closed is not stated anywhere |

Nothing in the dependency tree constrains the choice. It is purely a business decision.

## Options

| Option | Effect | Fits if |
|---|---|---|
| **A. Proprietary, private repository** | Code stays exclusive. Make the repo private and add a short "All rights reserved" `LICENSE` | The business value is the code (a hosted SaaS competing with vidIQ and the foundation's own upcoming SaaS) |
| **B. Apache-2.0** | Open source with an explicit patent grant and a NOTICE convention, which matches `THIRD_PARTY_NOTICES.md`. Anyone, including competitors, may reuse the code | The value is data, operations and brand, and community contributions matter |
| C. MIT | Like B without the patent grant | Simplicity matters most |
| D. AGPL-3.0 | Anyone who runs a modified copy as a service must publish it | You want openness but to stop closed SaaS forks. It deters some contributors |

## Recommendation

1. **Decide the business model first.** For a commercial hosted product, choose **A**: make the repository
   private now (it is public today) and add an all-rights-reserved notice.
2. If ViralTrack should be open source, choose **B (Apache-2.0)**. It is the safest permissive choice and fits
   the existing notices.

Either way, keep `THIRD_PARTY_NOTICES.md`, the submodule's `LICENSE`, and the obligations listed in
OPEN_SOURCE_ADOPTION_AUDIT.md.

**Owner action:** reply with A, B, C or D. The license file and `pyproject.toml` `license` field will be added
in a separate, reviewed change.
