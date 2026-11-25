"""Evidence-based AI-content classification from metadata. Pure: no I/O, no model, no network.

No platform marks every AI-generated video, so the status is decided from evidence, each piece recorded:

1. The platform's own altered/synthetic-content disclosure (set by the creator on upload).
2. An explicit creator statement in the title or tags ("AI generated", "made with AI").
3. A named generation tool (Suno, Udio, Sora, Kling, Veo, Runway, Midjourney ...). Tool names that are
   also ordinary words ("Suno" is Hindi for "listen", "Sora", "Luma") count only in an unambiguous form:
   a hashtag or tag, "<tool> AI", a version ("Veo 3"), or "made with <tool>".
4. Labels that describe the content as AI ("#aimusic", "AI song", "AI animation").

Rules, strongest first:

- platform disclosure set                      -> CONFIRMED_AI, high
- creator negation ("no AI used") + AI evidence -> UNKNOWN (contradictory), none
- creator negation alone                        -> NOT_AI, medium
- creator statement + (tool or label)           -> CONFIRMED_AI, high
- creator statement alone                       -> LIKELY_AI, high
- tools or labels in a tutorial, review or news
  context (the video may be ABOUT AI tools)     -> POSSIBLY_AI, low
- tool + label, or two different labels         -> LIKELY_AI, medium
- tool alone                                    -> LIKELY_AI, medium
- one label alone                               -> POSSIBLY_AI, low
- only the word "AI"                            -> UNKNOWN: never enough on its own
- nothing                                       -> UNKNOWN

The platform flag being off is not evidence of human-made content (it is off by default) and is recorded as
such. Video descriptions are not used: the data source does not expose them through its read API.
"""

from __future__ import annotations

import re
from datetime import datetime

from viraltrack.intelligence.taxonomy import (
    AIStatus,
    Classification,
    Confidence,
    ContentCategory,
    ContentSignals,
    FormatClassification,
    FormatType,
)

CLASSIFIER_VERSION = "ai-content-rules/1.0.0"
SHORT_FORM_MAX_SECONDS = 180
GAMING_CATEGORY = "Gaming"
GAMING_EXCLUSION = "Gaming content is excluded from AI Content Intelligence (owner decision)."

_F = re.IGNORECASE | re.UNICODE

_AI = r"(?:ai|a\.i\.|artificial intelligence)"
_DISCLOSURE = re.compile(
    rf"\b{_AI}[\s-]?generated\b"
    rf"|\b(?:generated|made|created|produced|animated|composed|sung|voiced|written)\s+"
    rf"(?:entirely\s+|fully\s+|completely\s+|100\s?%\s+)?(?:by|with|using|in)\s+(?:an?\s+)?{_AI}(?![\w-])"
    rf"|\b{_AI}[\s-](?:made|created|produced|animated)\b"
    rf"|\b(?:song|music|video|animation|film|movie|story|art|cover)\s+(?:made\s+|created\s+)?by\s+{_AI}(?![\w-])"
    rf"|\b100\s?%\s?{_AI}(?![\w-])|\bfully\s+{_AI}(?![\w-])",
    _F,
)
_DISCLOSURE_LABELS = frozenset({
    "aigenerated", "aigeneratedmusic", "aigeneratedvideo", "aigeneratedsong", "aigeneratedart",
    "aigeneratedimages", "madewithai", "createdwithai", "generatedbyai", "aimade", "aicreated",
})

# tool -> kind: audio (music generators), voice, visual (image and video generators)
_TOOLS_UNAMBIGUOUS = {
    "udio": "audio", "riffusion": "audio", "mubert": "audio", "soundraw": "audio",
    "elevenlabs": "voice", "eleven labs": "voice",
    "midjourney": "visual", "stable diffusion": "visual", "dall-e": "visual", "dalle": "visual",
    "heygen": "visual", "synthesia": "visual", "hailuo": "visual", "pixverse": "visual",
    "runwayml": "visual", "dream machine": "visual", "invideo ai": "visual", "leonardo ai": "visual",
    "kling ai": "visual", "sora ai": "visual", "luma ai": "visual", "pika labs": "visual",
}
_TOOLS_AMBIGUOUS = {
    "suno": "audio", "aiva": "audio", "boomy": "audio",
    "sora": "visual", "kling": "visual", "veo": "visual", "luma": "visual", "pika": "visual",
    "runway": "visual", "vidu": "visual", "viggle": "visual", "hedra": "visual", "minimax": "visual",
}


def _tool_pattern(tool: str) -> str:
    return r"\s?".join(re.escape(part) for part in tool.split(" "))


_UNAMBIGUOUS_RE = {
    t: re.compile(r"(?<![\w-])" + _tool_pattern(t) + r"(?![\w-])", _F) for t in _TOOLS_UNAMBIGUOUS
}
_AMBIGUOUS_RE = {
    t: re.compile(
        rf"(?<![\w-]){t}\s?(?:ai|v?\d(?:\.\d)?)(?![\w-])"
        rf"|\b(?:made|created|generated|produced|animated|composed)\s+(?:with|using|by|in)\s+{t}(?![\w-])",
        _F,
    )
    for t in _TOOLS_AMBIGUOUS
}

# Labels that describe the content itself as AI. "AI" alone is not one of them.
_CONTENT_TERMS = (
    "music video", "music", "songs", "song", "covers", "cover", "videos", "video", "animation", "animated",
    "art", "artwork", "short film", "film", "movie", "stories", "story", "cartoon", "cinematic", "mv",
    "singer", "vocals", "voice", "instrumental", "bhajan", "devotional", "anthem", "remix", "version",
    "shorts", "short", "clip", "reels",
)
_CONTENT_PHRASE = re.compile(
    rf"\bai\s+({'|'.join(re.escape(t) for t in _CONTENT_TERMS)})(?![\w-])", _F
)
_CONTENT_LABELS = frozenset("ai" + t.replace(" ", "") for t in _CONTENT_TERMS)

_NEGATION = re.compile(
    rf"\b(?:not|no|zero|without|never)\s+(?:an?\s+)?(?:{_AI})(?:[\s-]?generated)?(?![\w-])"
    r"|\b100\s?%\s?(?:human|real|handmade)\b|\bhuman[\s-]?made\b"
    r"|\breal\s+(?:footage|voice|singer|vocals)\b",
    _F,
)
_NEGATION_LABELS = frozenset({"noai", "notai", "nonai", "humanmade", "noaiused", "notaigenerated"})

_ABOUT_AI = re.compile(
    r"\bhow to\b|\btutorials?\b|\breviews?\b|\bexplained\b|\bnews\b|\bprompts?\b|\bvs\.?(?!\w)"
    r"|\bcomparison\b|\bguide\b|\bstep[\s-]by[\s-]step\b|\bcourse\b|\bmake money\b|\bearn\b"
    r"|\btop\s+\d+\b|\bbest\s+ai\b|\bfree\s+ai\b",
    _F,
)
_BARE_AI = re.compile(rf"(?<![\w-]){_AI}(?![\w-])", _F)

# ---- category lexicon ----
_MUSIC_SUPPORT = re.compile(
    r"\bbgm\b|\bbackground (?:music|score)\b|\bsound\s?track\b|\bwith music\b|\bmusic by\b|\bmusic\s?:",
    _F,
)
_MUSIC_PRIMARY = re.compile(
    r"\b(?:songs?|music|music video|lyrics?|lyrical|instrumental|bhajans?|kirtan|aarti|mantra|qawwali|"
    r"ghazal|lullaby|anthem|lo-?fi|remix|karaoke|official audio|audio song|video song|melody|melodies|"
    r"album|rap|jukebox|ost)\b"
    r"|ಹಾಡು|ಗೀತೆ|गाना|गीत|भजन|பாடல்|పాట|ഗാനം|গান|노래|歌",
    _F,
)
_MUSIC_LABELS = frozenset({
    "aimusic", "aisong", "aisongs", "aicover", "aicovers", "aimusicvideo", "aiinstrumental", "aibhajan",
    "aidevotional", "aimv", "aisinger", "aivocals", "airemix", "aianthem", "music", "song", "songs", "lyrics",
    "newsong", "lofi", "bhajan", "musicvideo", "instrumental",
})
_SUPPORT_LABELS = frozenset({"bgm", "backgroundmusic", "soundtrack"})
_AUDIO_PRIMARY = re.compile(
    r"\b(?:official audio|audio song|full audio|audio only|lyrics?\s+video|lyrical(?:\s+video)?|"
    r"visuali[sz]er|instrumental|lo-?fi|playlist|jukebox|\d+\s?(?:hours?|hrs?)|sleep music|"
    r"meditation music|study music|relaxing music|mp3)\b",
    _F,
)
_MUSIC_VISUAL = re.compile(
    r"\b(?:music video|video song|official (?:music )?video|mv|animated|animation|cinematic|short film|"
    r"visuals?|full video)\b",
    _F,
)
_VIDEO_LABELS = frozenset({
    "aivideo", "aivideos", "aianimation", "aianimated", "aifilm", "aimovie", "aishortfilm", "aicinematic",
    "aimusicvideo", "aimv", "aicartoon", "aistory", "aistories", "aiclip",
})

_GAMING_LABELS = frozenset({
    "gaming", "gameplay", "gamer", "videogame", "videogames", "minecraft", "fortnite", "roblox", "freefire",
    "pubg", "pubgmobile", "bgmi", "gta", "gta5", "gtav", "valorant", "callofduty", "cod", "letsplay",
})

_SHORTS_LABELS = frozenset({"shorts", "short", "youtubeshorts", "ytshorts", "shortsvideo", "shortvideo"})
_HASHTAG = re.compile(r"#([^\s#]+)", re.UNICODE)


def compact(label: str) -> str:
    """'#AI Music' -> 'aimusic': how labels are compared."""
    return re.sub(r"[\s_\-#.]+", "", label.lower())


def labels_of(title: str | None, tags: tuple[str, ...]) -> tuple[set[str], set[str]]:
    """(hashtags in the title, creator tags), both compacted."""
    hashtags = {compact(h) for h in _HASHTAG.findall(title or "")}
    return {h for h in hashtags if h}, {compact(t) for t in tags if compact(t)}


def _first(regex: re.Pattern, text: str) -> str | None:
    m = regex.search(text)
    return m.group(0).strip().lower() if m else None


def _tools(text: str, labels: set[str]) -> dict[str, str]:
    """Named generation tools -> kind."""
    found = {}
    for tool, rx in _UNAMBIGUOUS_RE.items():
        if rx.search(text) or compact(tool) in labels:
            found[compact(tool).removesuffix("ai") or tool] = _TOOLS_UNAMBIGUOUS[tool]
    for tool, rx in _AMBIGUOUS_RE.items():
        if rx.search(text) or tool in labels or f"{tool}ai" in labels:
            found[tool] = _TOOLS_AMBIGUOUS[tool]
    return found


def is_gaming(category: str | None, title: str | None, tags: tuple[str, ...]) -> bool:
    if (category or "").strip().lower() == GAMING_CATEGORY.lower():
        return True
    hashtags, tag_labels = labels_of(title, tags)
    return bool((hashtags | tag_labels) & _GAMING_LABELS)


def classify_format(
    duration_seconds: int | None, live_status: str | None, title: str | None, tags: tuple[str, ...]
) -> FormatClassification:
    if live_status in ("live", "upcoming"):
        return FormatClassification(
            FormatType.LIVE, Confidence.HIGH, f"the platform reports the broadcast status as {live_status}"
        )
    if duration_seconds is None or isinstance(duration_seconds, bool) or duration_seconds <= 0:
        return FormatClassification(FormatType.UNKNOWN, Confidence.NONE, "no known length")
    if duration_seconds > SHORT_FORM_MAX_SECONDS:
        return FormatClassification(
            FormatType.LONG_FORM,
            Confidence.HIGH,
            f"length {duration_seconds} s is above {SHORT_FORM_MAX_SECONDS} s, the longest a Short can be",
        )
    hashtags, tag_labels = labels_of(title, tags)
    if (hashtags | tag_labels) & _SHORTS_LABELS:
        return FormatClassification(
            FormatType.SHORT_FORM,
            Confidence.MEDIUM,
            f"length {duration_seconds} s (at most {SHORT_FORM_MAX_SECONDS} s) and the creator tagged it "
            "#shorts; the platform's own Shorts flag is not available",
        )
    return FormatClassification(
        FormatType.SHORT_FORM,
        Confidence.LOW,
        f"length {duration_seconds} s (at most {SHORT_FORM_MAX_SECONDS} s) only; the platform's own Shorts "
        "flag is not available",
    )


def _category(
    status: AIStatus,
    platform_category: str | None,
    text: str,
    labels: set[str],
    tools: dict[str, str],
) -> tuple[ContentCategory, str]:
    if status is AIStatus.NOT_AI:
        return ContentCategory.NORMAL_NON_AI, "the creator states that no AI was used"
    if status is AIStatus.UNKNOWN:
        return ContentCategory.UNKNOWN, "no AI classification, so no AI category"

    support = _first(_MUSIC_SUPPORT, text) or next(iter(sorted(labels & _SUPPORT_LABELS)), None)
    primary_text = _MUSIC_SUPPORT.sub(" ", text)
    primary = _first(_MUSIC_PRIMARY, primary_text) or next(iter(sorted(labels & _MUSIC_LABELS)), None)
    audio_tools = sorted(t for t, k in tools.items() if k == "audio")
    visual_tools = sorted(t for t, k in tools.items() if k == "visual")
    if (platform_category or "").strip().lower() == "music":
        primary = primary or "platform category Music"
    if not primary and audio_tools:
        primary = f"music generator {audio_tools[0]}"

    if primary:
        visual = _first(_MUSIC_VISUAL, text) or next(iter(sorted(labels & _VIDEO_LABELS)), None)
        if not visual and visual_tools:
            visual = f"video or image generator {visual_tools[0]}"
        audio = _first(_AUDIO_PRIMARY, text)
        if not audio and audio_tools and not visual_tools:
            audio = f"music generator {audio_tools[0]} and no visual generator"
        if visual and not audio:
            return ContentCategory.AI_MUSIC_VIDEO, f"music ({primary}) with AI visuals ({visual})"
        if audio and not visual:
            return ContentCategory.AI_MUSIC_AUDIO, f"music ({primary}) where audio is the product ({audio})"
        if audio and visual:
            if re.search(r"\b(?:music video|video song|official (?:music )?video)\b", text, _F):
                return ContentCategory.AI_MUSIC_VIDEO, f"music ({primary}) stated as a music video ({visual})"
            return ContentCategory.AI_MUSIC_AUDIO, f"music ({primary}); audio-first wording ({audio})"
        return (
            ContentCategory.UNKNOWN,
            f"music ({primary}), but whether video or audio is the product is not stated",
        )
    if support:
        return ContentCategory.AI_VIDEO_WITH_MUSIC, f"video with supporting music ({support})"
    return ContentCategory.AI_NORMAL_VIDEO, "no music signal"


def classify(
    *,
    title: str | None,
    tags: tuple[str, ...] = (),
    platform_category: str | None = None,
    duration_seconds: int | None = None,
    signals: ContentSignals | None = None,
    now: datetime,
) -> Classification:
    # the creator's tags as the data source reports them, plus any the caller already had
    tags = tuple(dict.fromkeys(t for t in (*tags, *(signals.tags if signals else ())) if isinstance(t, str)))
    title_text = (title or "").lower()
    tag_text = " | ".join(t.lower() for t in tags)
    hashtags, tag_labels = labels_of(title, tags)
    labels = hashtags | tag_labels
    evidence: list[str] = []
    sources: list[str] = []

    def note(source: str, text: str):
        evidence.append(text)
        if source not in sources:
            sources.append(source)

    disclosure_flag = signals.synthetic_disclosure if signals else None
    if disclosure_flag is True:
        note("platform_disclosure", "the creator disclosed altered or synthetic content to the platform")
    elif disclosure_flag is False:
        note(
            "platform_disclosure",
            "the platform's synthetic-content flag is off; it is off by default, so this is not evidence of "
            "human-made content",
        )

    statement = None
    for source, text in (("title", title_text), ("creator_tags", tag_text)):
        hit = _first(_DISCLOSURE, text)
        if hit:
            statement = hit
            note(source, f'creator statement: "{hit}"')
            break
    if not statement and labels & _DISCLOSURE_LABELS:
        statement = sorted(labels & _DISCLOSURE_LABELS)[0]
        where = "creator_tags" if tag_labels & _DISCLOSURE_LABELS else "title"
        note(where, f"creator statement: #{statement}")

    tools = _tools(f"{title_text} | {tag_text}", labels)
    in_title = _tools(title_text, hashtags)
    for t, kind in sorted(tools.items()):
        note("title" if t in in_title else "creator_tags", f"generation tool named: {t} ({kind})")

    both = f"{title_text} | {tag_text}"
    content_terms = {compact("ai" + m.group(1)) for m in _CONTENT_PHRASE.finditer(both)}
    content_terms |= labels & (_CONTENT_LABELS | {"aimusic", "aisong", "aicover"})
    for term in sorted(content_terms):
        note("title" if term in hashtags or term in compact(title_text) else "creator_tags",
             f"AI content label: {term}")

    negation = _first(_NEGATION, f"{title_text} | {tag_text}") or next(
        iter(sorted(labels & _NEGATION_LABELS)), None
    )
    if negation:
        note("title" if negation in title_text else "creator_tags", f'creator negation: "{negation}"')

    about = _first(_ABOUT_AI, title_text)
    bare = _first(_BARE_AI, f"{title_text} | {tag_text}")
    positive = bool(statement or tools or content_terms)

    if disclosure_flag is True:
        status, confidence = AIStatus.CONFIRMED_AI, Confidence.HIGH
        reason = "the creator disclosed altered or synthetic content to the platform"
        if negation:
            reason += "; the title or tags also deny AI use, which the platform disclosure outweighs"
    elif negation and positive:
        status, confidence = AIStatus.UNKNOWN, Confidence.NONE
        reason = "contradictory evidence: AI signals and a statement that no AI was used"
    elif negation:
        status, confidence = AIStatus.NOT_AI, Confidence.MEDIUM
        reason = f'the creator states that no AI was used ("{negation}")'
    elif statement and (tools or content_terms):
        status, confidence = AIStatus.CONFIRMED_AI, Confidence.HIGH
        reason = "the creator states the content is AI-generated and names the tool or AI content type"
    elif statement:
        status, confidence = AIStatus.LIKELY_AI, Confidence.HIGH
        reason = "the creator states the content is AI-generated"
    elif about and (tools or content_terms):
        status, confidence = AIStatus.POSSIBLY_AI, Confidence.LOW
        reason = f'AI tools or labels appear, but the wording ("{about}") suggests a video about AI tools'
    elif tools and content_terms:
        status, confidence = AIStatus.LIKELY_AI, Confidence.MEDIUM
        reason = "a generation tool is named and the content is labelled as AI"
    elif len(content_terms) >= 2:
        status, confidence = AIStatus.LIKELY_AI, Confidence.MEDIUM
        reason = "several different labels describe the content as AI"
    elif tools:
        status, confidence = AIStatus.LIKELY_AI, Confidence.MEDIUM
        reason = "a generation tool is named"
    elif content_terms:
        status, confidence = AIStatus.POSSIBLY_AI, Confidence.LOW
        reason = "one label describes the content as AI; not enough for more"
    elif bare:
        status, confidence = AIStatus.UNKNOWN, Confidence.NONE
        reason = 'only the word "AI" appears, which is not evidence that the content is AI-generated'
    else:
        status, confidence = AIStatus.UNKNOWN, Confidence.NONE
        reason = "no AI evidence in the title, the creator's tags or the platform disclosure"

    category, category_reason = _category(
        status, platform_category, f"{title_text} | {tag_text}", labels, tools
    )
    if platform_category:
        if "platform_category" not in sources and category is not ContentCategory.UNKNOWN:
            sources.append("platform_category")
    fmt = classify_format(duration_seconds, signals.live_status if signals else None, title, tags)
    excluded = GAMING_EXCLUSION if is_gaming(platform_category, title, tags) else None
    return Classification(
        status=status,
        confidence=confidence,
        category=category,
        reason=reason,
        category_reason=category_reason,
        evidence_sources=tuple(sources),
        evidence=tuple(evidence),
        format=fmt,
        classifier_version=CLASSIFIER_VERSION,
        classified_at=now,
        excluded_reason=excluded,
    )
