"""AI content intelligence: evidence-based AI classification, content categories, format and country
dimensions, and opportunity briefs over the collected corpus.

Everything here is computed at read time from metadata a provider already holds. Nothing is persisted, no
platform request is made, and no restricted metric is read: the inputs are titles, creator tags, the
platform's own synthetic-media disclosure, declared channel country, declared or detected language,
duration, broadcast status, publication time and raw views (the last two only for ordering and display).
"""

from viraltrack.intelligence.classifier import CLASSIFIER_VERSION, classify
from viraltrack.intelligence.taxonomy import (
    AIStatus,
    Classification,
    Confidence,
    ContentCategory,
    ContentSignals,
    CountryDimensions,
    FormatType,
)

__all__ = [
    "AIStatus",
    "CLASSIFIER_VERSION",
    "Classification",
    "Confidence",
    "ContentCategory",
    "ContentSignals",
    "CountryDimensions",
    "FormatType",
    "classify",
]
