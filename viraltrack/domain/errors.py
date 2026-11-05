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


class ProviderTimeout(ProviderUnavailable):
    """ViralTrack stopped waiting. This is a CLIENT-side timeout, not a failure reported by the
    backend: for a request that was already sent (`outcome_unknown`), the backend may still finish
    the operation, and a collection may already have spent quota. Never retried automatically."""

    def __init__(self, provider: str, message: str, status: int | None = None,
                 outcome_unknown: bool = True):
        super().__init__(provider, message, status)
        self.outcome_unknown = outcome_unknown


class NotFound(ProviderError):
    pass


class ProviderAuthFailed(ProviderError):
    """The backend rejected ViralTrack's credentials (401/403)."""


class ProviderCredentialsMissing(ProviderError):
    """The backend has no platform API credentials, so it cannot collect anything."""


class QuotaExhausted(ProviderError):
    """Platform quota is spent, or below the floor ViralTrack keeps in reserve."""


class RateLimited(ProviderError):
    """The backend asked us to wait (cooldown). `retry_after` is in seconds, if given."""

    def __init__(self, provider: str, message: str, status: int | None = None,
                 retry_after: int | None = None):
        super().__init__(provider, message, status)
        self.retry_after = retry_after


class IngestionDisabled(ViralTrackError):
    """Ingestion is switched off in configuration; no request was made."""

    def __init__(self, provider: str, setting: str):
        super().__init__(f"{provider}: ingestion is disabled (set {setting}=true to allow it)")
        self.provider = provider
        self.setting = setting
