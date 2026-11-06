# Provider Boundary

Code: `viraltrack/providers/base.py`, `viraltrack/domain/capabilities.py`.

## Interface

```python
class PlatformProvider(ABC):
    provider_id: str
    platform: Platform
    def capabilities(self) -> PlatformCapabilities   # what is legitimately supported, with a note why
    def discover_content(self, DiscoveryQuery) -> ContentPage
    def search_content(self, SearchQuery) -> ContentPage
    def get_content(self, content_id) -> Content
    def get_creator(self, creator_id) -> Creator
    def get_creator_history(self, creator_id) -> list[CreatorSnapshot]
    def get_trending_content(self, region=None) -> ContentPage
    # ingestion (Phase 2): internal-only, may spend platform quota
    def collect_creator(self, creator_ref, max_items=None) -> IngestionResult
    def collect_query(self, text, pages=1, region=None, language=None, period=None) -> IngestionResult
    def refresh_stats(self, period="7d", limit=None) -> IngestionResult
    def ingestion_status(self) -> QuotaStatus
```

Every method defaults to raising `UnsupportedCapability(provider, capability, note)`. A provider overrides
only what it really supports. An unsupported call never returns an empty list (an empty list would read as
"nothing is trending"), and it never makes a network call (tested).

## YouTube capabilities (derived from the foundation's real API, not guessed)

| Capability | Supported | Backed by | Note |
|---|---|---|---|
| discover_content | yes | `GET /api/viral` | Videos within the collected corpus, filtered by raw values only (period, channel subscribers, views, duration; `min_views_per_subscriber=0` is always sent) and ordered by an allowed metric; not all of YouTube |
| search_content | yes | `GET /api/search` | Corpus search, no quota |
| get_content | **no** | — | Upstream has no single-video read endpoint |
| get_creator | yes | `GET /api/channels/{id}` | Collected channels only (404 → `NotFound`) |
| creator_history | yes | `GET /api/channels/{id}/history` | Limited by retention (30 days by default) |
| global_trending | **no** | — | `chart=mostPopular` covers only Music, Movies and Gaming since 2025-07-21 |
| short_form | yes (filter) | none: `only_shorts` / `exclude_shorts` are always sent `false` (F-6) | A duration filter applied by ViralTrack on `lengthSeconds`: more than 0 and at most 180 s inclusive; zero, missing or invalid duration is not short; the foundation's `is_short` is ignored. The `short` label is RESTRICTED (DERIVED_METRIC_POLICY.md) |
| engagement_metrics | yes | likes, comments | |
| hashtags | **no** | — | Not in upstream read API |
| audio | **no** | — | No YouTube API |
| derived_velocity | yes | upstream snapshots | Passed through as DERIVED, not computed by ViralTrack |
| collect_creator | yes (internal) | `POST /api/collect/channel` | Uploads playlist; ~1 unit per 50 videos (upstream figure) |
| collect_query | yes (internal) | `POST /api/collect/niche` | `search.list`, its own bucket of 100 calls a day |
| refresh_stats | yes (internal) | `POST /api/refresh` | Re-reads counters of recent videos and tracked channels |
| ingestion_status | yes (internal) | `GET /api/health` | Units and search calls left today, as the foundation reports them |

## Ordering and metric exposure (Phase 1.1)

`DiscoveryQuery.sort` / `SearchQuery.sort` take ViralTrack metric names (default `views`). The adapter always
sends an explicit `sort_by`, because the foundation's defaults rank by restricted scores. Derived values pass
through the provider's `MetricPolicy`. Ids placed in URL paths are percent-encoded.

## Which operations spend YouTube quota

Reads spend none: they use only endpoints the upstream API reference marks "free". Scheduled collection stays
with the foundation's worker.

Since Phase 2 Batch 2, `collect_creator`, `collect_query` and `refresh_stats` spend quota. They ask the
foundation to collect; ViralTrack never calls YouTube itself, and the foundation's own client enforces the
daily pool (10,000 units, 100 `search.list` calls). Each call goes through these steps, in this order:

1. **Off switch.** `VT_YOUTUBE_INGESTION_ENABLED` (default `false`). While it is false, every ingestion method,
   including `ingestion_status`, raises `IngestionDisabled` and sends nothing (tested for each method).
2. **Argument limits.**
   - Pages ≤ `VT_YOUTUBE_MAX_SEARCH_PAGES` (1).
   - Videos ≤ `VT_YOUTUBE_MAX_VIDEOS_PER_COLLECT` (200).
   - `period` format; region (ISO alpha-2) and language codes. For `collect_query`, `period` is optional
     (`None` by default) and must be `all` or a lowercase whole number of hours or days from 1 to 9999
     (`24h`, `7d`); `all` and `None` send no period (no publication limit); empty, zero, uppercase, aliases
     (`week`) and other units (`w`, `m`) are rejected, never normalised. See
     [../phase-3/D2_IMPLEMENTATION_REPORT.md](../phase-3/D2_IMPLEMENTATION_REPORT.md).
   - References of at most 200 characters.

   A violation raises `ValueError` before any request.
3. **Cooldown.** After a 429 with `Retry-After`, the provider sends nothing until it expires.
4. **Pre-flight.** `GET /api/health`:
   - No key at the foundation: `ProviderCredentialsMissing`.
   - Units left below `VT_YOUTUBE_QUOTA_FLOOR_UNITS` (1000): `QuotaExhausted`.
   - For keyword search, fewer calls left than the pages asked for plus `VT_YOUTUBE_QUOTA_FLOOR_SEARCH_CALLS`
     (10): `QuotaExhausted`.
   - Quota not reported, as when a multi-user foundation answers an unauthenticated request: refused.
5. **POST**, only to `WRITE_ROUTES` = `/api/collect/channel`, `/api/collect/niche`, `/api/refresh`. The client
   refuses any other path before sending. The body is JSON and the request carries the `X-NF-Client` header.

Quota figures in `IngestionResult` are copied from the foundation's answer
(`quota.units_from_shared_pool`, `quota.search_calls`). Refresh sums the two parts it reports. When the
foundation reports nothing, the figure is None. ViralTrack never estimates them.

These methods are **internal-only**: no ViralTrack API, CLI, UI or MCP exposes them.

## Errors

| Situation | Exception |
|---|---|
| Foundation unreachable | `ProviderUnavailable` |
| Client timeout (read/write: the foundation may still finish; connect/pool: nothing delivered) | `ProviderTimeout`, a subclass of `ProviderUnavailable`, with `outcome_unknown`. Never retried for collection POSTs |
| 404 | `NotFound` (message from the foundation, e.g. "Run collect_channel / track_channel first.") |
| 401/403 (multi-user mode) | `ProviderAuthFailed` (a `ProviderError`) with a hint to set `VT_YOUTUBE_FOUNDATION_TOKEN` |
| 403 `PlanLimit` / `FeatureOff` / `ReadOnlyView` | `ProviderError` (a refusal, not a credentials problem) |
| 428 (foundation has no YouTube key) | `ProviderCredentialsMissing` |
| 429 `QuotaExceeded`, or below ViralTrack's floor | `QuotaExhausted` |
| 429 `ManualRunLimit` / other cooldown | `RateLimited` with `retry_after` seconds; later calls are refused locally until it expires |
| Ingestion switched off | `IngestionDisabled`, no request |
| Other 4xx/5xx, non-JSON, wrong JSON shape | `ProviderError` |
| Malformed `period`, unknown `sort`, empty id | `ValueError` before any request |
| `sort` by a metric the policy does not allow | `RestrictedMetric` before any request |

## Adding Instagram later (example)

1. Create `viraltrack/providers/instagram/`, implementing `PlatformProvider`.
2. Declare capabilities honestly from Phase 0. `get_creator` and `creator_history` are possible for **known
   professional accounts** (Business Discovery). Hashtag search is possible, limited to 30 tags per 7 days.
   `global_trending`, `audio` and general `discover_content` are unsupported.
3. Map responses to `Content`/`Creator`/`Metric` with `source="instagram-graph-api"`.
4. Register it in `viraltrack/providers/registry.py` behind `VT_INSTAGRAM_ENABLED`.
5. Add any tables it needs to the retention policy, and check Meta's storage terms first.

TikTok follows the same steps once a legitimate source exists. Today none does (Phase 0, B-4).
