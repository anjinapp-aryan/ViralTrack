"""The classified corpus: one record per collected item, filters and counts. Pure, no I/O."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from viraltrack.domain import Content
from viraltrack.intelligence import country as countries
from viraltrack.intelligence.classifier import classify
from viraltrack.intelligence.taxonomy import (
    AIStatus,
    Classification,
    ContentCategory,
    ContentSignals,
    CountryDimensions,
    FormatType,
)

UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassifiedItem:
    content: Content
    classification: Classification
    country: CountryDimensions
    signals_found: bool
    tags: tuple[str, ...] = ()   # the creator's tags, used for themes; never returned by the API


@dataclass(frozen=True)
class Filters:
    """Empty tuple = no filter on that dimension. Country and language values may include "unknown"."""
    statuses: tuple[AIStatus, ...] = ()
    categories: tuple[ContentCategory, ...] = ()
    formats: tuple[FormatType, ...] = ()
    creator_countries: tuple[str, ...] = ()
    discovery_countries: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()


def build(
    contents: Iterable[Content],
    signals: Mapping[str, ContentSignals],
    markets: Mapping[str, tuple[str, ...]],
    now: datetime,
) -> list[ClassifiedItem]:
    items = []
    for c in contents:
        s = signals.get(c.content_id)
        found = bool(s and s.found)
        result = classify(
            title=c.title,
            platform_category=c.category,
            duration_seconds=c.duration_seconds,
            signals=s if found else None,
            now=now,
        )
        dims = countries.dimensions(
            tuple(markets.get(c.content_id, ())), s.creator_country if found else None, c.language
        )
        items.append(ClassifiedItem(c, result, dims, found, tuple(s.tags) if found else ()))
    return items


def included(items: Iterable[ClassifiedItem]) -> list[ClassifiedItem]:
    """Items the AI views may show: everything except excluded content (Gaming)."""
    return [i for i in items if i.classification.excluded_reason is None]


def _match(value: str | None, wanted: tuple[str, ...]) -> bool:
    return not wanted or (value or UNKNOWN) in wanted


def apply(items: Iterable[ClassifiedItem], f: Filters) -> list[ClassifiedItem]:
    out = []
    for i in items:
        c = i.classification
        if f.statuses and c.status not in f.statuses:
            continue
        if f.categories and c.category not in f.categories:
            continue
        if f.formats and c.format.format_type not in f.formats:
            continue
        if not _match(i.country.creator_country, f.creator_countries):
            continue
        if f.discovery_countries:
            have = i.country.discovery_countries or (UNKNOWN,)
            if not set(have) & set(f.discovery_countries):
                continue
        if not _match(i.country.language_code, f.languages):
            continue
        out.append(i)
    return out


def views(i: ClassifiedItem) -> int | None:
    m = i.content.metric("views")
    return int(m.value) if m is not None else None


def order(items: list[ClassifiedItem], sort: str) -> list[ClassifiedItem]:
    """The approved raw orders only: views or publication time, unknown values last."""
    if sort == "views":
        return sorted(items, key=lambda i: (views(i) is not None, views(i) or 0), reverse=True)
    if sort == "published_at":
        return sorted(
            items,
            key=lambda i: (i.content.published_at is not None, i.content.published_at or datetime.min),
            reverse=True,
        )
    raise ValueError(f"unknown sort {sort!r}; use views or published_at")


def count_by(
    items: Iterable[ClassifiedItem], key: Callable[[ClassifiedItem], Iterable[str]]
) -> list[tuple[str, int]]:
    """Counts per value, largest first; an item with several values (discovery markets) counts once each."""
    counter: Counter[str] = Counter()
    for i in items:
        for k in set(key(i)):
            counter[k] += 1
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


def by_status(i: ClassifiedItem) -> list[str]:
    return [i.classification.status.value]


def by_category(i: ClassifiedItem) -> list[str]:
    return [i.classification.category.value]


def by_format(i: ClassifiedItem) -> list[str]:
    return [i.classification.format.format_type.value]


def by_confidence(i: ClassifiedItem) -> list[str]:
    return [i.classification.confidence.value]


def by_creator_country(i: ClassifiedItem) -> list[str]:
    return [i.country.creator_country or UNKNOWN]


def by_discovery_country(i: ClassifiedItem) -> list[str]:
    return list(i.country.discovery_countries) or [UNKNOWN]


def by_language(i: ClassifiedItem) -> list[str]:
    return [i.country.language_code or UNKNOWN]


def by_published_day(i: ClassifiedItem) -> list[str]:
    p = i.content.published_at
    return [p.date().isoformat()] if p else [UNKNOWN]
