class ViralTrackError(Exception):
    pass


class ConfigError(ViralTrackError):
    pass


class UnsupportedCapability(ViralTrackError):
    def __init__(self, provider: str, capability, note: str):
        super().__init__(f"{provider}: {capability.value} is not supported ({note})")
        self.provider = provider
        self.capability = capability
        self.note = note


class ProviderError(ViralTrackError):
    """The provider's backend failed or answered something we cannot use."""

    def __init__(self, provider: str, message: str, status: int | None = None):
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.status = status


class ProviderUnavailable(ProviderError):
    """The backend could not be reached at all."""


class NotFound(ProviderError):
    pass
