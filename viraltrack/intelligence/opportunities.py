"""Opportunity identification and original creative briefs, from the classified corpus. Pure, no I/O.

An opportunity is a group of AI items in the collected corpus that share a content category, a format, a
language and a country. It is reported only when the group has enough items, and it says how many and which
ones. Groups are ordered by how many collected items support them, then by the newest publication: no score,
no restricted metric, no prediction.

Themes are the creator-provided hashtags, tags and title words that recur in at least two items of a group.
They are counted, not interpreted. The brief is written from fixed templates (no language model): it points
at a theme and a format and asks for new work; it never reuses a supporting video's title, lyrics, melody,
script, characters, scenes or branding.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field

from viraltrack.intelligence.classifier import labels_of
from viraltrack.intelligence.corpus import UNKNOWN, ClassifiedItem, views
from viraltrack.intelligence.taxonomy import ContentCategory, FormatType

MIN_ITEMS_DEFAULT = 3
MAX_THEMES = 6
MAX_EVIDENCE = 10
GENERATED_BY = "template"
TEMPLATE_NOTE = (
    "Written from fixed templates and the collected metadata; no language model was used. A starting point "
    "to edit, not finished copy."
)

CATEGORY_PLURAL = {
    ContentCategory.AI_MUSIC_VIDEO: "AI music videos",
    ContentCategory.AI_MUSIC_AUDIO: "AI music tracks where audio is the product",
    ContentCategory.AI_VIDEO_WITH_MUSIC: "AI videos with a music soundtrack",
    ContentCategory.AI_NORMAL_VIDEO: "AI videos that are not music-based",
}
CATEGORY_NOUN = {
    ContentCategory.AI_MUSIC_VIDEO: "music video",
    ContentCategory.AI_MUSIC_AUDIO: "song or instrumental track",
    ContentCategory.AI_VIDEO_WITH_MUSIC: "visual story with an original soundtrack",
    ContentCategory.AI_NORMAL_VIDEO: "video",
}
MUSIC_CATEGORIES = (ContentCategory.AI_MUSIC_VIDEO, ContentCategory.AI_MUSIC_AUDIO)
FORMAT_PHRASE = {
    FormatType.SHORT_FORM: "short-form (up to 3 min)",
    FormatType.LONG_FORM: "long-form",
    FormatType.LIVE: "live",
    FormatType.UNKNOWN: "unknown-length",
}
LANGUAGES = {
    "ar": "Arabic", "bn": "Bengali", "de": "German", "en": "English", "es": "Spanish", "fr": "French",
    "gu": "Gujarati", "hi": "Hindi", "id": "Indonesian", "it": "Italian", "ja": "Japanese", "kn": "Kannada",
    "ko": "Korean", "ml": "Malayalam", "mr": "Marathi", "ne": "Nepali", "pa": "Punjabi", "pt": "Portuguese",
    "ru": "Russian", "ta": "Tamil", "te": "Telugu", "th": "Thai", "tr": "Turkish", "uk": "Ukrainian",
    "ur": "Urdu", "vi": "Vietnamese", "zh": "Chinese", "fil": "Filipino", "pl": "Polish", "nl": "Dutch",
}
COUNTRIES = {
    "AE": "the UAE", "AR": "Argentina", "AU": "Australia", "BD": "Bangladesh", "BR": "Brazil", "CA": "Canada",
    "DE": "Germany", "EG": "Egypt", "ES": "Spain", "FR": "France", "GB": "the UK", "ID": "Indonesia",
    "IN": "India", "IT": "Italy", "JP": "Japan", "KR": "South Korea", "LK": "Sri Lanka", "MX": "Mexico",
    "MY": "Malaysia", "NG": "Nigeria", "NP": "Nepal", "PH": "the Philippines", "PK": "Pakistan",
    "RU": "Russia", "SA": "Saudi Arabia", "SG": "Singapore", "TH": "Thailand", "TR": "Turkey",
    "UA": "Ukraine", "US": "the USA", "VN": "Vietnam", "ZA": "South Africa",
}

# Words that say nothing about a theme: AI and tool words, formats, platform words, filler.
_STOP = frozenset("""
a an and the of to in on for with by from at is are was be this that it its my your our you me we i he she
they them his her new full hd 4k 8k official video videos song songs music shorts short reels reel status
viral trending trend explore fyp foryou foryoupage subscribe like share channel youtube ytshorts
youtubeshorts ai aimusic aisong aisongs aivideo aivideos aianimation aiart aigenerated generated made
created using ft feat vs part ep episode version latest best top free hindi english kannada tamil telugu
suno udio sora kling veo runway midjourney luma pika hailuo pixverse elevenlabs heygen lyrics lyrical
2023 2024 2025 2026 2027 mv cover remix audio
""".split())
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass(frozen=True)
class Opportunity:
    key: str
    category: ContentCategory
    format_type: FormatType
    language_code: str | None
    country: str | None
    country_basis: str
    item_count: int
    newest_published_at: object
    themes: tuple[tuple[str, int], ...]
    summary: str
    evidence: tuple[ClassifiedItem, ...]
    brief: dict = field(default_factory=dict)


def _terms(i: ClassifiedItem) -> set[str]:
    hashtags, tags = labels_of(i.content.title, i.tags)
    words = {w.lower() for w in _WORD.findall(re.sub(r"#\S+", " ", i.content.title or ""))}
    terms = hashtags | tags | words
    out = set()
    for t in terms:
        if t in _STOP or t.isdigit():
            continue
        # Latin-script words shorter than 3 letters are mostly filler; other scripts keep 2+
        if len(t) < (3 if t.isascii() else 2):
            continue
        out.add(t)
    return out


def themes(items: list[ClassifiedItem]) -> tuple[tuple[str, int], ...]:
    """Terms in at least two items, with the number of items, most common first."""
    counter: Counter[str] = Counter()
    for i in items:
        counter.update(_terms(i))
    common = [(t, n) for t, n in counter.items() if n >= 2]
    return tuple(sorted(common, key=lambda tn: (-tn[1], tn[0]))[:MAX_THEMES])


def _language_name(code: str | None) -> str | None:
    return LANGUAGES.get(code, code) if code else None


def _country_name(code: str | None) -> str | None:
    return COUNTRIES.get(code, code) if code else None


def find(
    items: list[ClassifiedItem], country_basis: str = "creator", min_items: int = MIN_ITEMS_DEFAULT
) -> list[Opportunity]:
    if country_basis not in ("creator", "discovery"):
        raise ValueError("country_basis must be creator or discovery")
    groups: dict[tuple, list[ClassifiedItem]] = {}
    for i in items:
        c = i.classification
        if c.category not in CATEGORY_PLURAL:
            continue
        if country_basis == "creator":
            places = [i.country.creator_country]
        else:
            places = list(i.country.discovery_countries) or [None]
        for place in places:
            key = (c.category, c.format.format_type, i.country.language_code, place)
            groups.setdefault(key, []).append(i)

    found = []
    for (category, fmt, lang, place), members in groups.items():
        if len(members) < min_items:
            continue
        dated = [m.content.published_at for m in members if m.content.published_at]
        newest = max(dated) if dated else None
        group_themes = themes(members)
        evidence = tuple(sorted(members, key=lambda m: (views(m) is not None, views(m) or 0), reverse=True))
        opp = Opportunity(
            key="|".join([category.value, fmt.value, lang or UNKNOWN, place or UNKNOWN, country_basis]),
            category=category,
            format_type=fmt,
            language_code=lang,
            country=place,
            country_basis=country_basis,
            item_count=len(members),
            newest_published_at=newest,
            themes=group_themes,
            summary=_summary(category, fmt, lang, place, country_basis, len(members), group_themes),
            evidence=evidence[:MAX_EVIDENCE],
        )
        found.append(_with_brief(opp, members))
    return sorted(
        found,
        key=lambda o: (
            -o.item_count,
            -(o.newest_published_at.timestamp() if o.newest_published_at else 0),
            o.key,
        ),
    )


def _place_phrase(place: str | None, basis: str) -> str:
    if not place:
        if basis == "creator":
            return " with no known country"
        return " outside ViralTrack's regional collections"
    name = _country_name(place)
    return f" from creators who list {name} as their country" if basis == "creator" else f" found in {name}"


def _summary(category, fmt, lang, place, basis, n, group_themes) -> str:
    lang_part = f" in {_language_name(lang)}" if lang else " in an unknown language"
    themes_part = (
        "; recurring themes: " + ", ".join(t for t, _ in group_themes)
        if group_themes
        else "; no recurring theme"
    )
    noun = CATEGORY_NOUN[category]
    lang_name = _language_name(lang)
    suggestion = (
        f" Consider an original {lang_name + ' ' if lang_name else ''}{noun} with your own story, "
        "characters, words and visuals"
        + (", and an original melody" if category in MUSIC_CATEGORIES else "")
        + "."
    )
    return (
        f"{n} {FORMAT_PHRASE[fmt]} {CATEGORY_PLURAL[category]}{lang_part}{_place_phrase(place, basis)} "
        f"appear in the collected corpus{themes_part}.{suggestion}"
    )


def _duration_hint(fmt: FormatType, members: list[ClassifiedItem]) -> str:
    lengths = sorted(m.content.duration_seconds for m in members if m.content.duration_seconds)
    if not lengths:
        return "no length known for the supporting videos; choose one that fits the platform"
    mid = int(statistics.median(lengths))
    lo, hi = lengths[0], lengths[-1]
    if fmt is FormatType.SHORT_FORM:
        return f"about {mid} s (supporting videos run {lo} to {hi} s; keep it at most 180 s)"
    return f"about {round(mid / 60)} min (supporting videos run {round(lo / 60)} to {round(hi / 60)} min)"


_OUTLINE = {
    ContentCategory.AI_MUSIC_VIDEO: [
        "Opening image that states the theme without words",
        "Verse: introduce your own characters and setting",
        "Chorus: the emotional turn, with a visual motif you designed",
        "Bridge: a change of place or time that deepens the story",
        "Closing image that resolves the story",
    ],
    ContentCategory.AI_MUSIC_AUDIO: [
        "Intro that sets the mood in the first seconds",
        "Verse with newly written lyrics on the theme",
        "Chorus with an original melody and a short, repeatable line",
        "Second verse that moves the story on",
        "Outro; simple cover art or a minimal visual that you made",
    ],
    ContentCategory.AI_VIDEO_WITH_MUSIC: [
        "Hook shot that poses a question",
        "Build-up: three scenes that develop the theme",
        "Peak moment timed to the soundtrack",
        "Resolution and a closing frame",
    ],
    ContentCategory.AI_NORMAL_VIDEO: [
        "Hook: the question or promise of the video",
        "Context in one or two sentences",
        "Main content in three clear steps or scenes",
        "Payoff and a closing line",
    ],
}


def _with_brief(opp: Opportunity, members: list[ClassifiedItem]) -> Opportunity:
    lang = _language_name(opp.language_code)
    theme_words = [t for t, _ in opp.themes]
    theme_text = ", ".join(theme_words[:3]) if theme_words else "a theme of your choice"
    music = opp.category in MUSIC_CATEGORIES
    short = opp.format_type is FormatType.SHORT_FORM
    brief = {
        "opportunity_title": f"Original {lang + ' ' if lang else ''}{CATEGORY_NOUN[opp.category]} "
        f"({FORMAT_PHRASE[opp.format_type]}) on {theme_text}",
        "country": opp.country,
        "country_basis": opp.country_basis,
        "language_code": opp.language_code,
        "category": opp.category.value,
        "format_type": opp.format_type.value,
        "audience_hypothesis": (
            f"A hypothesis to test, not audience data: viewers of {lang or 'this language'} "
            f"{CATEGORY_PLURAL[opp.category]} respond to {theme_text}. It rests only on "
            f"{opp.item_count} collected videos."
        ),
        "theme": theme_text,
        "original_creative_angle": (
            f"Tell a new story about {theme_text} from a point of view none of the supporting videos uses, "
            "with your own characters and setting. Use them only to understand the format; reuse none of "
            "their "
            "titles, words, melodies, characters, scenes or branding."
        ),
        "suggested_duration": _duration_hint(opp.format_type, members),
        "hook_concept": (
            "Show the emotional core in the first two seconds, before any text or logo."
            if short
            else "State the promise of the video in the first 15 seconds, then deliver it."
        ),
        "story_outline": list(_OUTLINE[opp.category]),
        "music_direction": (
            f"An original composition{' in ' + lang if lang else ''}: new lyrics, melody and arrangement. "
            "No imitation of a named artist's voice and no reuse of a supporting video's song."
            if music
            else "An original or properly licensed soundtrack that supports the scenes."
            if opp.category is ContentCategory.AI_VIDEO_WITH_MUSIC
            else None
        ),
        "visual_direction": (
            "A visual style you define (palette, character design, camera language), consistent across "
            "scenes; "
            + ("vertical 9:16." if short else "horizontal 16:9.")
        ),
        "platform_recommendations": (
            ["YouTube Shorts (vertical, up to 3 min)", "Instagram Reels", "TikTok"]
            if short
            else ["YouTube (horizontal)"]
        ),
        "rights_checklist": list(RIGHTS_CHECKLIST),
        "generated_by": GENERATED_BY,
        "note": TEMPLATE_NOTE,
    }
    return Opportunity(**{**opp.__dict__, "brief": brief})


RIGHTS_CHECKLIST = (
    "Lyrics, melody, arrangement and script are newly written; nothing is taken from the supporting videos.",
    "No cloned voice of a real singer or person without their written consent.",
    "Characters, logos and visual style are your own; no other creator's branding or recognisable "
    "characters.",
    "The terms of every AI tool used allow commercial use of its output; keep a record of them.",
    "Realistic AI-generated or altered content is disclosed to the platform where its rules require it.",
    "Samples, stock footage, fonts and other assets are licensed for this use.",
    "AI output is not automatically free of third-party rights; take advice when unsure.",
)
