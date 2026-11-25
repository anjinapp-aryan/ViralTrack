# AI Content Intelligence

Date: 2026-11-25. Status: implemented and tested offline; **not committed**. It needs owner review. No live
YouTube request was made, no quota was spent and no worker was started. The submodule is unchanged at
`d872014`.

## 1. What it does

**DISCOVER → CLASSIFY → FILTER → RANK → ANALYZE → IDENTIFY OPPORTUNITIES → ORIGINAL BRIEF.** Discovery reads
the collected corpus. "Rank" means the approved raw orders only.

- **Classification.** Every collected video gets an evidence-based AI status, a content category, a format and
  separate country and language dimensions.
- **Views.** A new **AI Intelligence** page (sidebar group "AI Content Intelligence", route `/ai`) has four
  views: Overview, Discover, Countries and Opportunities. The existing Discover and Creators pages are
  unchanged.
- **Opportunities.** Groups of AI videos that share category, format, language and country. Each comes with
  its evidence and a template-written **original** creative brief.
- **Gaming.** Excluded from every AI view and count (owner instruction, 2026-11-25). The number left out is
  shown.
- **Ordinary content.** Normal and non-AI content is opt-in: select the "Not AI" or "Unclassified" status.

## 2. Open-source reuse audit (REUSE → ADAPT → COMPOSE → BUILD)

Fresh searches were run on 2026-11-25 with `gh search repos`. The queries were:

- "ai generated video detection metadata youtube"
- "ai generated content classifier youtube title"
- "youtube ai slop detector"
- "ai music detection youtube"
- "synthetic media disclosure youtube api"
- "ai slop" and "ai generated youtube"
- "detect ai generated videos"
- "ai music detector"
- "yake keyword extraction", "keybert" and "rake keyword"

| Candidate | Licence (checked) | Finding | Decision |
|---|---|---|---|
| Foundation `containsSyntheticMedia`, stored per video (`application/collecting.py:153`) and served by `GET /api/inspect/video` | MIT (pinned) | The platform's own altered/synthetic-content disclosure, set by the creator. It is the strongest legitimate signal | **REUSE**, through the documented HTTP route with `fetch=false&refresh=false`, so it is read from the database only |
| Foundation stored tags and `channels.country`, from the same route | MIT | Creator tags, and the country the creator declared on the channel | **REUSE** |
| Foundation niche labels (`POST /api/collect/niche` `label`, `GET /api/niches`, `/api/niches/{slug}/videos`) | MIT | Lets the market of a regional collection be read back | **ADAPT**: ViralTrack names its regional collections `vt-market-<cc> <query>` |
| Foundation `domain/policy_signals.py` (shock, sensitive-topic and synthetic-share signals) | MIT | Channel- and niche-level monetisation-risk signals, not a per-video AI classifier | Not reused: a different purpose |
| MauroPello/stop-the-slop | **no licence** (GitHub API: `license: null`) | Browser extension | **Rejected**: unlicensed code may not be copied |
| j3ffx/botless | **GPL-3.0** | Chrome extension that flags AI channels | **Rejected**: copyleft licence and a different runtime |
| lofcz/ai-music-detector (MIT), deezer/ismir25-ai-music-detector (custom licence), RA-Bench, ATSS, DeCoF (no licence) | various | Audio or frame models | **Rejected**: they need the audio or video file. Downloading media is outside approved data access |
| KeyBERT (MIT) | MIT | Keyword extraction with a transformer model | Not adopted: a large dependency (sentence-transformers or torch) for counting recurring terms |
| YAKE ports, RAKE implementations | mixed, mostly small or unlicensed | Keyword extraction | Not adopted |

**BUILD**, small and ViralTrack-specific, with no new dependency:

- the rule-based classifier (`viraltrack/intelligence/classifier.py`);
- the term counting for themes;
- the brief templates.

No existing project classifies AI content from metadata under a usable licence.

## 3. Architecture

```text
web /ai ──GET──► /api/v1/ai/{content,summary,countries,opportunities}   (viraltrack/api/ai.py)
                    │  discover_content() — same path, bounds and raw sorts as /discover
                    │  get_content_signals() — GET /api/inspect/video?fetch=false&refresh=false
                    │  discovery_markets()  — GET /api/niches, /api/niches/{slug}/videos
                    ▼
              viraltrack/intelligence (pure: taxonomy, classifier, country, corpus, opportunities)
```

- `viraltrack/intelligence` is platform-neutral. Its only platform words are generation-tool names and the
  Gaming category label.
- The YouTube field names stay in the provider. For example, `containsSyntheticMedia` becomes
  `ContentSignals.synthetic_disclosure`.
- Two capabilities were added: `CONTENT_SIGNALS` and `DISCOVERY_MARKETS`. Providers without them raise
  `UnsupportedCapability`.
- No second YouTube client and no quota logic: the only new write path is `collect_market`, which uses the
  existing guards (see section 9).
- **No schema change and no migration.** Classification is computed at request time from stored metadata, so
  it is always recomputable and there is nothing new to retain. The provider keeps the per-video signals in
  memory for 10 minutes and persists nothing.

## 4. AI classification

The status is decided from evidence, and each piece of evidence is recorded in words.

**Evidence used:**
- the platform's synthetic-content disclosure;
- a creator statement ("AI generated", "made with AI") in the title or tags;
- a named generation tool;
- labels such as `#aimusic` or "AI animation".

**Tool names that are also ordinary words** ("Suno" means "listen" in Hindi; "Sora", "Luma", "Veo", "Kling")
count only in an unambiguous form: a hashtag or tag, "<tool> AI", a version ("Veo 3"), or "made with <tool>".

| Evidence | Status, confidence |
|---|---|
| Platform disclosure set | CONFIRMED_AI, high |
| A creator denial ("no AI used") together with AI evidence | UNKNOWN (contradictory) |
| A creator denial alone | NOT_AI, medium |
| A creator statement plus a tool or label | CONFIRMED_AI, high |
| A creator statement alone | LIKELY_AI, high |
| Tools or labels in a tutorial, review or news context | POSSIBLY_AI, low |
| A tool plus a label, or two different labels | LIKELY_AI, medium |
| A tool alone | LIKELY_AI, medium |
| One label | POSSIBLY_AI, low |
| Only the word "AI", or nothing | UNKNOWN |

- **Confidence is a label, not a probability.** No calibrated model exists.
- **The platform flag being off is not evidence of human-made content**, because it is off by default. It is
  recorded as such.
- **Every result carries:** status, confidence, reason, category reason, evidence sources, evidence,
  `classifier_version` (`ai-content-rules/1.0.0`) and `classified_at`.
- **AI confidence and views never mix.** Neither influences the other.

**Content category.** It is assigned only for CONFIRMED, LIKELY and POSSIBLY:

- Music is primary when one of these holds:
  - the platform category is Music;
  - music words appear, including Kannada, Hindi, Tamil, Telugu, Malayalam, Bengali, Korean and Japanese
    words for "song";
  - there are music labels;
  - a music generator is named.
- Within music:
  - **AI_MUSIC_VIDEO**: visual evidence ("music video", "cinematic", a video generator);
  - **AI_MUSIC_AUDIO**: audio-first evidence ("official audio", "lyrical", "lo-fi", "1 hour", a music
    generator with no visual generator);
  - **UNKNOWN**: neither kind of evidence.
- Otherwise:
  - **AI_VIDEO_WITH_MUSIC**: supporting music ("BGM", "background music", "soundtrack");
  - **AI_NORMAL_VIDEO**: anything else.
- NOT_AI gives NORMAL_NON_AI; UNKNOWN gives UNKNOWN.

**Known limits:**
- Video descriptions are not available: the foundation's read routes do not return them (see section 11).
- The lexicon is mostly English, plus "song" in several scripts.
- The rules see only what creators write, so undisclosed AI content stays UNKNOWN. That is the intended
  failure mode.

## 5. Format (Shorts and long-form)

Format is a dimension of its own, separate from the category.

| Rule | Format, confidence |
|---|---|
| Broadcast status `live` or `upcoming` | `live`, high |
| No usable length | `unknown` |
| More than 180 s | `long_form`, high (a Short cannot be longer than 3 minutes) |
| 1 to 180 s and tagged `#shorts` by the creator | `short_form`, medium |
| 1 to 180 s with no tag | `short_form`, low |

- **The YouTube Data API has no Shorts flag.** `short_form` is a ViralTrack length tag. The UI shows it as
  "Short-form (≤ 3 min)" and never as "YouTube Short".
- This keeps to Phase 1 decision C: the duration filter stays and the Shorts label stays restricted.

## 6. Countries and language

The three dimensions are kept apart:

| Dimension | Source | Notes |
|---|---|---|
| `creator_country` | The channel's declared country | Self-reported and unverified, so confidence is medium |
| `discovery_countries` | Markets of ViralTrack's own regional collections | Empty for every other collection |
| `language_code` | The language the foundation stores | The creator's declared audio or metadata language, otherwise its own text detection. It cannot tell which; the response says so |

- **Nothing is inferred from language, names, descriptions or hashtags.** An unknown value is "Unknown", and
  it can be selected as a filter value.
- **The foundation's `region` filter is not used.** It matches the stored search region OR the channel
  country, which would merge two dimensions.
- **Audience country is not available** from any approved source.
- **The UI:**
  - a basis toggle: Creator country or Discovery market;
  - multi-select pickers for country and language, built from the collected corpus with their counts, with
    "Worldwide / all" to clear them;
  - a Countries view with per-country category, format, language and publication-day counts;
  - a comparison of up to four countries.
- Every view states that the counts describe the collected corpus, not a country's market.

## 7. Discovery and ordering

- **Ordering:** only `views` and `published_at`. Restricted sorts are refused with 422, tested.
- **Corpus window:** each request examines at most the 500 most viewed collected videos of the period, from
  creators with up to 1,000,000 followers (the existing bound). The response reports how many were examined
  and whether the limit was reached.
- **Statuses:** CONFIRMED_AI and LIKELY_AI by default. POSSIBLY_AI, NOT_AI and UNKNOWN are opt-in.

## 8. Opportunities and briefs

- **Grouping.** An opportunity is a group of at least `min_items` (default 3) matching AI videos with the same
  category, format, language and country (creator or market basis).
- **Ordering.** Groups are ordered by the number of supporting videos, then the newest publication. There is
  no score.
- **Themes.** Creator hashtags, tags and title words that recur in at least two of the group's videos, with
  their counts. AI words, tool names, platform words and filler are left out.
- **The brief.** It is filled from fixed templates, with no language model. Its fields:
  - title, country, language, category, format;
  - an audience hypothesis, labelled as a hypothesis and not audience data;
  - theme and an original angle;
  - suggested length (from the supporting videos' lengths), hook and story outline;
  - music and visual direction, and platforms;
  - a rights and originality checklist.
- **No copying.** A test checks that no supporting title appears in the brief. No publishing and no
  generation service is connected.

## 9. API (all GET, localhost-only, unauthenticated, same boundary as D5)

| Route | Parameters |
|---|---|
| `/api/v1/ai/content` | `period`, `status[]`, `category[]`, `format[]`, `creator_country[]`, `discovery_country[]`, `language[]`, `sort` (views or published_at), `page`, `page_size` |
| `/api/v1/ai/summary` | The same filters. Counts by status, category, format, confidence, creator country, discovery market and language, plus the recent items |
| `/api/v1/ai/countries` | `basis` (creator or discovery), filters and `country[]`. One row per country |
| `/api/v1/ai/opportunities` | `basis`, filters, `min_items` (2 to 50) and `limit`. Opportunities with evidence and briefs |

- **Strict schemas** (`extra=forbid`). `GuardedJSONResponse` checks every body. No foundation payload is
  passed through: the inspect response's restricted fields are dropped in the provider, which is tested
  against fixtures that carry them.
- **Ingestion.** `YouTubeProvider.collect_market(region, text, ...)` was added for **future** regional
  collections:
  - it is off unless `VT_YOUTUBE_INGESTION_ENABLED=true`;
  - it runs the same pre-flight quota floor as `collect_query`;
  - it is never exposed over HTTP;
  - it has **not been run**.

## 10. Tests

Python, `tests/test_ai_intelligence.py`, 69 tests:
- classifier statuses, ambiguity, negation, contradictions, tutorials, categories and format boundaries;
- Gaming exclusion and country separation;
- the market label round trip through the foundation's slug rule;
- the provider's `fetch=false` reads and in-memory cache;
- market collection guards;
- combined filters and opportunities;
- API leak checks on all four routes, 422 validation before any request, and data-origin labels.

Web, `web/src/features/ai/ai.test.tsx`, 19 tests, real router in Chromium:
- every filter's request and the basis switching;
- the four views, and the empty, loading, error and retry states;
- real, demo and stale labels;
- no forbidden wording, axe-core on each view, and phone width.

Existing suites keep passing. Two route-list assertions in `tests/test_api_d5.py` were **extended** with the
four new routes; nothing was removed. Results are in the final report of this change.

## 11. Open points for the owner

1. **Descriptions.** Creator disclosures often sit in the description, which the foundation stores but does
   not serve. Options:
   - an upstream PR that adds `description` to `/api/inspect/video`;
   - an approved read-only database path.

   Either is an architecture decision.
2. **The foundation's combined `region` filter** (search region OR channel country) is still used by the
   existing `/discover?region=`. It should be reviewed, and probably relabelled or replaced.
3. **The "Short-form (≤ 3 min)" wording** follows decision C. Confirm it is acceptable before the Analytics &
   Reporting amendment.
4. **Live validation** (separate plan, `LIVE_VALIDATION_PLAN.md`) needs explicit approval. The current
   real-data corpus came from six generic keywords, so it holds almost no AI content.
