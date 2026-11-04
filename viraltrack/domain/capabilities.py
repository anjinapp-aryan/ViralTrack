"""What a platform provider can legitimately do.

A capability is declared only when the provider really supports it through a
legitimate data source. Calling an operation whose capability is missing raises
`UnsupportedCapability`; providers never return fake or empty stand-in data.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Capability(str, Enum):
    DISCOVER_CONTENT = "discover_content"      # ranked discovery over a collected corpus
    SEARCH_CONTENT = "search_content"          # search within the collected corpus
    GET_CONTENT = "get_content"                # one item by id
    GET_CREATOR = "get_creator"
    CREATOR_HISTORY = "creator_history"        # stored snapshots of creator metrics
    GLOBAL_TRENDING = "global_trending"        # platform-wide "trending now" feed
    SHORT_FORM = "short_form"                  # Shorts / Reels classification
    ENGAGEMENT_METRICS = "engagement_metrics"  # likes / comments
    HASHTAGS = "hashtags"
    AUDIO = "audio"                            # trending sounds / audio
    DERIVED_VELOCITY = "derived_velocity"      # views-per-hour etc. computed from snapshots
    # Ingestion: ask the provider's backend to collect through the official API.
    # Internal-only operations; they may spend platform quota.
    COLLECT_CREATOR = "collect_creator"        # one creator's uploads
    COLLECT_QUERY = "collect_query"            # keyword search
    REFRESH_STATS = "refresh_stats"            # re-read counters of collected items
    INGESTION_STATUS = "ingestion_status"      # quota remaining, as the backend reports it


@dataclass(frozen=True)
class CapabilityInfo:
    supported: bool
    note: str  # why, or the limit that applies


@dataclass(frozen=True)
class PlatformCapabilities:
    info: dict[Capability, CapabilityInfo]

    def supports(self, capability: Capability) -> bool:
        entry = self.info.get(capability)
        return bool(entry and entry.supported)

    def note(self, capability: Capability) -> str:
        entry = self.info.get(capability)
        return entry.note if entry else "not declared by this provider"
