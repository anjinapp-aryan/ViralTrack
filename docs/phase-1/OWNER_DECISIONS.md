# Owner Decisions (Phase 1.2)

Each item needs an explicit answer from the owner. Nothing below has been applied. This is not legal advice.

---

## A. Repository license

Current state: the repository is **PUBLIC** with **no license** (GitHub: `visibility=PUBLIC`, `license=none`).
That means anyone can read and clone the code, but nobody may legally reuse it.

| | Proprietary + private repository | Apache-2.0 + public repository |
|---|---|---|
| Commercial | Code is an exclusive asset; competitors can't reuse it. Fits a paid hosted SaaS | Anyone, including competitors and upstream's own planned SaaS, may run or fork it. The value must come from data, operations and brand |
| Distribution | You decide terms per customer. Third-party notices still apply when shipping images (OPEN_SOURCE_ADOPTION_AUDIT.md) | Recipients must keep notices; NOTICE file convention. Patent grant from contributors |
| Contributions | Only people you invite, under your terms (consider a contributor agreement) | Open contributions under Apache-2.0 (inbound = outbound) |
| Already public | **The current public history stays visible to anyone who cloned it.** Going private stops further exposure but doesn't recall copies | Nothing to undo |
| Compatibility | MIT foundation, LGPL/MPL libraries: fine | Fine |

**Recommendation: proprietary + private.** The phase documents describe a commercial product, and the
differentiators (policy-safe metrics, provider layer, future platforms) are code. Switch to Apache-2.0 only if
you decide to build in the open.

**Owner action:** choose. After approval, a separate change would make the repository private (GitHub settings)
and add `LICENSE` plus the `pyproject.toml` license field.

---

## B. The two "allowed with review" metrics

| Metric | Exact formula (upstream) | Dependencies | Rationale for ALLOWED | Risk | Recommendation |
|---|---|---|---|---|---|
| **acceleration** | `vph24 / max(vph_prev24, 0.01)` with `vph_prev24 = 2·vph48 − vph24` (`discovery.py:235`, `metrics.acceleration`) | Two or more stored view snapshots ≤ 30 days old | Only division and subtraction of YouTube view counts over time, which is within the guide's "simple mathematical calculations" | Upstream also turns it into labels ("heating up" > 1.5, "cooling" < 0.7), which look more like a score. The 0.01 floor can produce large values for near-zero prior rates | **Keep ALLOWED for the numeric value only.** Don't map or show the labels. Confirm in the Google audit filing |
| **views_per_follower** | `views / max(subscribers, 1)` (`metrics.views_per_subscriber`) | Video viewCount, channel subscriberCount (rounded by YouTube) | A single division of two YouTube values. It is the core "small channel, big views" discovery signal (upstream `/api/viral` filters `≥ 1.0`) | Comparing a video with its own channel could be read as channel comparison. Rounded subscriber counts distort small channels | **Keep ALLOWED**, labelled "views ÷ subscribers (not a YouTube metric)". Confirm in the audit filing |

The policy is unchanged; both remain ALLOWED. If you prefer the conservative route, make either RESTRICTED by
changing one line in `metric_policy.py`. Discovery would then have to be ordered by raw views only.

---

## C. Shorts label

| Question | Answer |
|---|---|
| What it represents | niche-finder marks a video "Short" when `duration ≤ 180 s` (YouTube raised the Shorts limit to 3 min in Oct 2024) |
| Source data | `contentDetails.duration` only. **The YouTube Data API has no Shorts flag** (`videoDuration=short` means < 4 min) |
| Reliability | Heuristic: a horizontal 2-minute video is labelled Short; a Short over 180 s is impossible, so false negatives are rare and false positives common. No aspect-ratio check |
| Permitted? | The guide says "you may only use the content type returned by the YouTube API". A duration-based label infers content type, so it is **likely not permitted without the amendment**. The amendment's "Content Categorization and Tagging" allows our own tags if disclosed as ours |

**Recommended policy (current behaviour, unchanged):**

- Keep the label RESTRICTED. Every YouTube item is `VIDEO`.
- Keep the **duration filter** (≤ 180 s): it filters raw data and claims nothing.
- After the amendment, show it as "≤ 3 min (ViralTrack tag)", never as "YouTube Short".

---

## D. Transcript storage

**Status: storage disabled by ViralTrack (Phase 1.2).** While `VT_TRANSCRIPTS_APPROVED=false` (the default),
every retention run deletes all rows in `transcripts`, `transcript_chunks` and `transcript_requests`.

Limits of this control:

- niche-finder still accepts **manual pastes** through `POST /api/transcripts/{video_id}/save` and the
  dashboard. It never fetches transcripts automatically (upstream `PRIVACY.md`). A pasted transcript can exist
  until the next daily run, which can be run more often.
- Hook scores and content gaps from transcripts live only in the foundation. The ViralTrack adapter maps none
  of them.
- No scraping or unofficial transcript collection exists in ViralTrack, and none will be added.

Open questions for counsel:

1. Copyright: may ViralTrack store creators' spoken text (transcripts are the creator's work)?
2. YouTube Terms of Service: is copying transcript text from YouTube's UI into a third-party product allowed?
3. If allowed: retention period, deletion when the video is deleted or private, and whether embeddings derived
   from transcripts are "derived data" under the API policies, even though the text is not API data.
4. User responsibility: should users confirm they have the rights to paste?

**Owner action:** obtain the review. Set `VT_TRANSCRIPTS_APPROVED=true` only with a written decision.

---

## E. Foundation surfaces that show restricted metrics

niche-finder's dashboard, HTTP API, export, MCP server, Chrome extension and alert channels display RESTRICTED
values (outlier scores, viral score, RPM, niche scores and rankings). ViralTrack can't filter them without
modifying upstream.

Options:

1. **Internal-only (current):** keep them on `127.0.0.1` for the operator and research; never expose them to
   users; leave `NOTIFY_*`/`SMTP_*` unset.
2. Production hardening: a compose override that publishes no foundation ports, so only the ViralTrack
   service network can reach it.
3. Contribute an upstream option to hide estimate-type metrics.

**Recommendation:** 1 now; 2 before any public deployment.

---

## F. Already decided by the owner

You committed and pushed Phase 1 (`aba23d6`, `355cd19`) and Phase 1.1 (`e035b11`); GitHub CI passed on all of
them. The Phase 1.2 changes are not committed.
