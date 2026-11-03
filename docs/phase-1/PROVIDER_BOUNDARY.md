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
```

Every method defaults to raising `UnsupportedCapability(provider, capability, note)`. A provider overrides
only what it really supports. An unsupported call never returns an empty list (an empty list would read as
"nothing is trending"), and it never makes a network call (tested).

## YouTube capabilities (derived from the foundation's real API, not guessed)

| Capability | Supported | Backed by | Note |
|---|---|---|---|
| discover_content | yes | `GET /api/viral` | Small-channel videos with high views per follower within the collected corpus, ordered by an allowed metric; not all of YouTube |
| search_content | yes | `GET /api/search` | Corpus search, no quota |
| get_content | **no** | — | Upstream has no single-video read endpoint |
| get_creator | yes | `GET /api/channels/{id}` | Collected channels only (404 → `NotFound`) |
| creator_history | yes | `GET /api/channels/{id}/history` | Limited by retention (30 days by default) |
| global_trending | **no** | — | `chart=mostPopular` covers only Music, Movies and Gaming since 2025-07-21 |
| short_form | yes (filter) | `only_shorts` | Duration ≤ 180 s filter. The `short` label is RESTRICTED (DERIVED_METRIC_POLICY.md) |
| engagement_metrics | yes | likes, comments | |
| hashtags | **no** | — | Not in upstream read API |
| audio | **no** | — | No YouTube API |
| derived_velocity | yes | upstream snapshots | Passed through as DERIVED, not computed by ViralTrack |

## Ordering and metric exposure (Phase 1.1)

`DiscoveryQuery.sort` / `SearchQuery.sort` take ViralTrack metric names (default `views`). The adapter always
sends an explicit `sort_by`, because the foundation's defaults rank by restricted scores. Derived values pass
through the provider's `MetricPolicy`. Ids placed in URL paths are percent-encoded.

## Which operations spend YouTube quota

None. The adapter calls only endpoints the upstream API reference marks "free". Collection (which spends quota)
stays with the foundation's worker and its own guardrails (100 `search.list` calls a day, 10,000 units).

## Errors

| Situation | Exception |
|---|---|
| Foundation unreachable | `ProviderUnavailable` |
| 404 | `NotFound` (message from the foundation, e.g. "Run collect_channel / track_channel first.") |
| 401/403 (multi-user mode) | `ProviderError` with a hint to set `VT_YOUTUBE_FOUNDATION_TOKEN` |
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
