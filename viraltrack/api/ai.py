"""AI Content Intelligence routes (read-only): /api/v1/ai/content, /summary, /countries, /opportunities.

Each request reads one window of the collected corpus through the provider (the same approved discovery path,
bounded follower limit and raw sorts as /discover), the stored classification metadata (read from the data
source's database only, never from the platform), and the markets of ViralTrack's regional collections. It
classifies at request time and stores nothing. Gaming content is excluded (owner decision). Restricted
metrics are never read: the inputs are titles, creator tags, the platform's synthetic-content disclosure,
declared channel country, language, duration, broadcast status, publication time and raw views.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, Query

from viraltrack.api import schemas, serialize
from viraltrack.domain import DataOrigin
from viraltrack.intelligence import corpus, opportunities
from viraltrack.intelligence.classifier import CLASSIFIER_VERSION
from viraltrack.intelligence.corpus import ClassifiedItem, Filters
from viraltrack.intelligence.taxonomy import (
    DEFAULT_AI_STATUSES,
    AIStatus,
    ContentCategory,
    FormatType,
)
from viraltrack.providers.base import DiscoveryQuery, PlatformProvider
from viraltrack.providers.youtube.provider import MAX_CREATOR_FOLLOWERS

CORPUS_LIMIT = 500
RECENT_ITEMS = 8
PAGE_SIZE_MAX = 100
PERIOD_PATTERN = r"^(all|[1-9][0-9]{0,3}[hd])$"
COUNTRY_VALUE = r"^([A-Z]{2}|unknown)$"
LANGUAGE_VALUE = r"^([a-z]{2,3}|unknown)$"

CORPUS_NOTE = (
    "Counts describe the collected corpus examined for this answer, not the platform and not any country's "
    "market."
)
CLASSIFICATION_NOTE = (
    "AI status is decided from evidence in the title, the creator's tags and the platform's "
    "synthetic-content "
    "disclosure; video descriptions are not available. Unknown means not enough evidence, not human-made."
)
FORMAT_NOTE = (
    "short_form is a length tag (1 to 180 s), not the platform's own Shorts classification, which is not "
    "available."
)
GAMING_NOTE = "Gaming content is excluded from AI Content Intelligence."

Status = schemas.AIStatusName
Category = schemas.CategoryName
Format = schemas.FormatName


@dataclass(frozen=True)
class Corpus:
    items: list[ClassifiedItem]        # examined items, Gaming excluded
    examined: int
    excluded: int
    meta: dict


def install(
    app: FastAPI,
    provider_for: Callable[[str], PlatformProvider],
    origin: DataOrigin,
    errors: dict,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> None:
    def load(platform: str, period: str) -> Corpus:
        provider = provider_for(platform)
        page = provider.discover_content(
            DiscoveryQuery(
                period=period,
                limit=CORPUS_LIMIT,
                max_creator_followers=MAX_CREATOR_FOLLOWERS,
                sort="views",
            )
        )
        contents = list(page.items)
        signals = provider.get_content_signals([c.content_id for c in contents])
        markets = provider.discovery_markets()
        everything = corpus.build(contents, signals, markets, clock())
        kept = corpus.included(everything)
        seen = [
            m.provenance.foundation_first_seen_at
            for c in contents
            for m in (c.metric("views"),)
            if m is not None and m.provenance.foundation_first_seen_at is not None
        ]
        notes = [CORPUS_NOTE, CLASSIFICATION_NOTE, FORMAT_NOTE, GAMING_NOTE]
        notes += [n for n in page.notes if n not in notes]
        limit_reached = len(contents) >= CORPUS_LIMIT
        if limit_reached:
            notes.append(
                f"Only the {CORPUS_LIMIT} most viewed collected videos of the period were examined; counts "
                "may be incomplete."
            )
        meta = dict(
            platform="youtube",
            data_origin=origin.value,
            demo=serialize.is_demo(origin),
            period=period,
            candidates_examined=len(contents),
            candidate_limit=CORPUS_LIMIT,
            candidate_limit_reached=limit_reached,
            excluded_gaming=len(everything) - len(kept),
            signals_missing=sum(1 for i in everything if not i.signals_found),
            collected_from=min(seen) if seen else None,
            collected_to=max(seen) if seen else None,
            classifier_version=CLASSIFIER_VERSION,
            notes=notes,
        )
        return Corpus(kept, len(contents), len(everything) - len(kept), meta)

    def filters(status, category, format, creator_country, discovery_country, language) -> Filters:
        return Filters(
            statuses=tuple(AIStatus(s) for s in status) if status else DEFAULT_AI_STATUSES,
            categories=tuple(ContentCategory(c) for c in category or ()),
            formats=tuple(FormatType(f) for f in format or ()),
            creator_countries=tuple(creator_country or ()),
            discovery_countries=tuple(discovery_country or ()),
            languages=tuple(language or ()),
        )

    common = dict(responses=errors, tags=["ai-intelligence"])

    def q_status():
        return Query(None, description="AI statuses; default CONFIRMED_AI and LIKELY_AI")

    @app.get(
        "/api/v1/ai/content",
        response_model=schemas.AIPage,
        summary="Collected videos with their AI classification, format and country dimensions.",
        **common,
    )
    def ai_content(
        period: str = Query("30d", pattern=PERIOD_PATTERN),
        status: list[Status] | None = q_status(),
        category: list[Category] | None = Query(None),
        format: list[Format] | None = Query(None),
        creator_country: list[str] | None = Query(None, description="ISO codes or 'unknown'"),
        discovery_country: list[str] | None = Query(None, description="ISO codes or 'unknown'"),
        language: list[str] | None = Query(None, description="language codes or 'unknown'"),
        sort: Literal["views", "published_at"] = Query("views"),
        platform: schemas.PlatformName = Query("youtube"),
        page: int = Query(1, ge=1, le=CORPUS_LIMIT),
        page_size: int = Query(24, ge=1, le=PAGE_SIZE_MAX),
    ):
        _check_codes(creator_country, discovery_country, language)
        c = load(platform, period)
        f = filters(status, category, format, creator_country, discovery_country, language)
        matching = corpus.order(corpus.apply(c.items, f), sort)
        start = (page - 1) * page_size
        chunk = matching[start : start + page_size]
        return schemas.AIPage(
            data=[ai_video(i) for i in chunk],
            meta=schemas.AIPageMeta(
                **c.meta,
                sort=sort,
                page=page,
                page_size=page_size,
                returned=len(chunk),
                total=len(matching),
                has_more=start + page_size < len(matching),
            ),
        )

    @app.get(
        "/api/v1/ai/summary",
        response_model=schemas.AISummary,
        summary="Counts of the classified corpus by status, category, format, confidence, country and "
        "language.",
        **common,
    )
    def ai_summary(
        period: str = Query("30d", pattern=PERIOD_PATTERN),
        status: list[Status] | None = q_status(),
        category: list[Category] | None = Query(None),
        format: list[Format] | None = Query(None),
        creator_country: list[str] | None = Query(None),
        discovery_country: list[str] | None = Query(None),
        language: list[str] | None = Query(None),
        platform: schemas.PlatformName = Query("youtube"),
    ):
        _check_codes(creator_country, discovery_country, language)
        c = load(platform, period)
        f = filters(status, category, format, creator_country, discovery_country, language)
        matching = corpus.apply(c.items, f)
        recent = corpus.order(matching, "published_at")[:RECENT_ITEMS]
        return schemas.AISummary(
            meta=schemas.CorpusMeta(**c.meta),
            matching=len(matching),
            by_status=counts(c.items, corpus.by_status),
            by_category=counts(matching, corpus.by_category),
            by_format=counts(matching, corpus.by_format),
            by_confidence=counts(matching, corpus.by_confidence),
            by_creator_country=counts(matching, corpus.by_creator_country),
            by_discovery_country=counts(matching, corpus.by_discovery_country),
            by_language=counts(matching, corpus.by_language),
            recent=[ai_video(i) for i in recent],
        )

    @app.get(
        "/api/v1/ai/countries",
        response_model=schemas.AICountries,
        summary="Per-country breakdown of the classified corpus (creator-declared or discovery market).",
        **common,
    )
    def ai_countries(
        basis: Literal["creator", "discovery"] = Query("creator"),
        period: str = Query("30d", pattern=PERIOD_PATTERN),
        status: list[Status] | None = q_status(),
        category: list[Category] | None = Query(None),
        format: list[Format] | None = Query(None),
        country: list[str] | None = Query(None, description="limit to these ISO codes or 'unknown'"),
        language: list[str] | None = Query(None),
        platform: schemas.PlatformName = Query("youtube"),
    ):
        _check_codes(country, None, language)
        c = load(platform, period)
        matching = corpus.apply(c.items, filters(status, category, format, None, None, language))
        key = corpus.by_creator_country if basis == "creator" else corpus.by_discovery_country
        rows = []
        for value, n in counts(matching, key, raw=True):
            if country and value not in country:
                continue
            members = [i for i in matching if value in key(i)]
            rows.append(
                schemas.CountryRow(
                    country=value,
                    items=n,
                    by_category=counts(members, corpus.by_category),
                    by_format=counts(members, corpus.by_format),
                    by_language=counts(members, corpus.by_language),
                    by_published_day=sorted(
                        counts(members, corpus.by_published_day), key=lambda x: x.key
                    ),
                )
            )
        return schemas.AICountries(meta=schemas.CorpusMeta(**c.meta), basis=basis, data=rows)

    @app.get(
        "/api/v1/ai/opportunities",
        response_model=schemas.AIOpportunities,
        summary="Groups of AI content in the corpus, with evidence and an original creative brief for each.",
        **common,
    )
    def ai_opportunities(
        basis: Literal["creator", "discovery"] = Query("creator"),
        period: str = Query("30d", pattern=PERIOD_PATTERN),
        status: list[Status] | None = q_status(),
        category: list[Category] | None = Query(None),
        format: list[Format] | None = Query(None),
        creator_country: list[str] | None = Query(None),
        discovery_country: list[str] | None = Query(None),
        language: list[str] | None = Query(None),
        min_items: int = Query(opportunities.MIN_ITEMS_DEFAULT, ge=2, le=50),
        limit: int = Query(20, ge=1, le=50),
        platform: schemas.PlatformName = Query("youtube"),
    ):
        _check_codes(creator_country, discovery_country, language)
        c = load(platform, period)
        f = filters(status, category, format, creator_country, discovery_country, language)
        found = opportunities.find(corpus.apply(c.items, f), basis, min_items)[:limit]
        return schemas.AIOpportunities(
            meta=schemas.CorpusMeta(**c.meta),
            basis=basis,
            min_items=min_items,
            data=[opportunity(o) for o in found],
        )


def _check_codes(countries, more_countries, languages) -> None:
    for value in [*(countries or ()), *(more_countries or ())]:
        if not re.match(COUNTRY_VALUE, value):
            raise ValueError("country values must be ISO 3166-1 alpha-2 codes like IN, or 'unknown'")
    for value in languages or ():
        if not re.match(LANGUAGE_VALUE, value):
            raise ValueError("language values must be codes like kn or en, or 'unknown'")


def counts(items, key, raw: bool = False):
    pairs = corpus.count_by(items, key)
    return pairs if raw else [schemas.Count(key=k, count=n) for k, n in pairs]


def ai_video(i: ClassifiedItem) -> schemas.AIVideo:
    c = i.classification
    d = i.country
    return schemas.AIVideo(
        video=serialize.video(i.content),
        classification=schemas.AIClassificationOut(
            status=c.status.value,
            confidence=c.confidence.value,
            category=c.category.value,
            reason=c.reason,
            category_reason=c.category_reason,
            evidence_sources=list(c.evidence_sources),
            evidence=list(c.evidence),
            classifier_version=c.classifier_version,
            classified_at=c.classified_at,
        ),
        format=schemas.FormatOut(
            format_type=c.format.format_type.value,
            format_confidence=c.format.format_confidence.value,
            reason=c.format.reason,
            duration_seconds=i.content.duration_seconds,
        ),
        country=schemas.CountryOut(
            discovery_countries=list(d.discovery_countries),
            discovery_source=d.discovery_source,
            creator_country=d.creator_country,
            creator_country_source=d.creator_country_source,
            creator_country_confidence=d.creator_country_confidence.value,
            language_code=d.language_code,
            language_source=d.language_source,
        ),
    )


def opportunity(o: opportunities.Opportunity) -> schemas.Opportunity:
    return schemas.Opportunity(
        key=o.key,
        category=o.category.value,
        format_type=o.format_type.value,
        language_code=o.language_code,
        country=o.country,
        country_basis=o.country_basis,
        item_count=o.item_count,
        newest_published_at=o.newest_published_at,
        themes=[schemas.Theme(term=t, items=n) for t, n in o.themes],
        summary=o.summary,
        evidence=[
            schemas.EvidenceItem(
                id=i.content.content_id,
                url=i.content.url,
                title=i.content.title,
                creator_name=i.content.creator.name,
                published_at=i.content.published_at,
                views=serialize.metric(i.content.metric("views")),
                status=i.classification.status.value,
                category=i.classification.category.value,
            )
            for i in o.evidence
        ],
        brief=schemas.CreativeBrief(**o.brief),
    )
