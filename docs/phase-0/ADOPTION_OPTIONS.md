# Adoption Options

Evaluated only after the research. Each option is judged on the evidence in the other Phase 0
documents.

## Option A — Adopt an existing complete application unchanged

**Candidate:** `pandich93/youtube-niche-finder` (the only complete, licensed, tested product found).

- ✅ Covers all 13 YouTube requirements and most platform-neutral features. Docker-ready; 1,784
  tests passing.
- ❌ YouTube-only, so no Instagram or TikTok surface.
- ❌ Its default retention behavior ("nothing is deleted") conflicts with YouTube's 30-day rule
  unless Google approves the derived-metrics amendment.
- ❌ Its branding and product direction belong to someone else (upstream is launching its own SaaS).

**Verdict:** the right *engine*, but not enough as the whole product. Rejected as a *complete* answer.

## Option B — Fork an existing application

**Candidate:** fork `youtube-niche-finder` into the ViralTrack organization.

- ✅ Keeps all verified capability, so original code is limited to the gaps.
- ✅ MIT lets us rebrand, change retention, and add a platform-adapter seam.
- ⚠️ Upstream is very active (daily commits). The fork should stay close to upstream (rebase
  regularly; upstream generic fixes as PRs) to avoid inheriting maintenance alone.
- ⚠️ One-author bus factor: plan to own the code.

**Verdict:** **selected as the base.**

## Option C — Combine multiple mature open-source projects

**Candidates:** niche-finder (YouTube) plus instaloader / TikTok-Api /
Douyin_TikTok_Download_API (IG/TikTok).

- ✅ On paper this reaches all three platforms quickly.
- ❌ Every IG/TikTok project audited collects data through unofficial routes that violate Meta's or
  TikTok's terms. A permissive code license does not cure that.
- ❌ TikTok is not reachable from the development machine at all.

**Verdict:** **rejected for launch.** Re-open only with written legal sign-off on a specific
licensed data vendor.

## Option D — Build a thin ViralTrack integration layer around existing projects

Keep the fork's YouTube engine as the system of record. Add a small adapter seam for other
sources: an Instagram adapter on the **official** Meta Graph API (Business Discovery watchlist +
limited Hashtag Search), and later a vendor adapter if legal approves. Add a side-by-side
cross-platform view.

- ✅ Original code limited to: retention job, IG adapter, player embeds, source labeling,
  side-by-side view.
- ✅ Honest labeling: "tracked creators" for Instagram, "NOT AVAILABLE" for TikTok and trending
  audio.

**Verdict:** **selected, on top of Option B.**

## Option E — Build missing components ourselves where no wheel exists

Applies only to the gaps confirmed in [REUSE_MATRIX.md](REUSE_MATRIX.md):

| Gap | Why no wheel exists | Size |
|---|---|---|
| Retention/purge policy in the fork | NF deliberately never deletes | Small |
| In-app video player (YouTube IFrame, IG/TikTok oEmbed) | No candidate embeds; official embed APIs are the wheel | Small |
| Instagram official-API adapter (Business Discovery + Hashtag Search) | No audited project uses the official IG discovery endpoints | Medium |
| Source/provenance labeling ("not from YouTube" disclosure, "tracked creators only") | Policy requirement specific to our product | Small |
| Side-by-side cross-platform view | No project does cross-platform discovery legitimately | Small–medium |

**Verdict:** **selected, only for these five items.**

## Decision

**B + D + E (minimal):** fork `youtube-niche-finder`; add a thin adapter and labeling layer; build
only the five listed gaps. A is insufficient; C is blocked by platform terms.
