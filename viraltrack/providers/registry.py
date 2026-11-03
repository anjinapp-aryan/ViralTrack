"""Builds the enabled providers from settings.

Instagram and TikTok have no provider yet: Phase 0 found no legitimate
discovery source for them (see docs/phase-0/PLATFORM_DATA_AUDIT.md). A future
provider is added by implementing `PlatformProvider` and registering it here.
"""
from __future__ import annotations

from viraltrack.config import Settings
from viraltrack.domain import Platform
from viraltrack.providers.base import PlatformProvider


def build_providers(settings: Settings, http_client=None) -> dict[Platform, PlatformProvider]:
    providers: dict[Platform, PlatformProvider] = {}
    if settings.youtube.enabled:
        from viraltrack.providers.youtube import YouTubeProvider
        providers[Platform.YOUTUBE] = YouTubeProvider(settings.youtube, http_client=http_client)
    return providers
