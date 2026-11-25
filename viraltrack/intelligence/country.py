"""Country and language dimensions, kept apart.

- discovery country: the market of one of ViralTrack's own regional collections that found the item. The
  data source's niche label carries it (``vt-market-<cc> <query>``) because the data source does not return
  the search region it stored. Only collections ViralTrack started with a region have one.
- creator country: what the creator declared on the channel. Self-reported, not verified.
- language: what the data source stores for the video: the creator's declared audio or metadata language,
  or, when neither is set, its own detection from the text. It does not say which.

Nothing here is inferred from language, names, descriptions, accents or hashtags. Unknown stays None.
"""

from __future__ import annotations

import re

from viraltrack.intelligence.taxonomy import Confidence, CountryDimensions

MARKET_LABEL_PREFIX = "vt-market-"
_MARKET_SLUG = re.compile(r"^vt-market-([a-z]{2})-")
_COUNTRY = re.compile(r"^[A-Z]{2}$")
_LANGUAGE = re.compile(r"^[a-z]{2,3}$")

DISCOVERY_SOURCE = "viraltrack_regional_collection"
CREATOR_COUNTRY_SOURCE = "creator_declared_channel_country"
LANGUAGE_SOURCE = "platform_metadata_or_data_source_text_detection"


def market_label(region: str, query: str) -> str:
    """The niche label a regional collection is stored under, so its market can be read back."""
    if not _COUNTRY.match(region or ""):
        raise ValueError(f"region must be an ISO 3166-1 alpha-2 code like IN, got {region!r}")
    return f"{MARKET_LABEL_PREFIX}{region.lower()} {query}"


def market_of_slug(slug: str) -> str | None:
    m = _MARKET_SLUG.match(slug or "")
    return m.group(1).upper() if m else None


def country_code(value) -> str | None:
    return value if isinstance(value, str) and _COUNTRY.match(value) else None


def language_code(value) -> str | None:
    """'en-US' -> 'en'; anything that is not a language code -> None."""
    if not isinstance(value, str):
        return None
    primary = value.strip().split("-")[0].split("_")[0].lower()
    return primary if _LANGUAGE.match(primary) else None


def dimensions(
    discovery_countries: tuple[str, ...], creator_country: str | None, language: str | None
) -> CountryDimensions:
    discovered = tuple(sorted({c for c in discovery_countries if country_code(c)}))
    creator = country_code(creator_country)
    lang = language_code(language)
    return CountryDimensions(
        discovery_countries=discovered,
        discovery_source=DISCOVERY_SOURCE if discovered else None,
        creator_country=creator,
        creator_country_source=CREATOR_COUNTRY_SOURCE if creator else None,
        creator_country_confidence=Confidence.MEDIUM if creator else Confidence.NONE,
        language_code=lang,
        language_source=LANGUAGE_SOURCE if lang else None,
    )
