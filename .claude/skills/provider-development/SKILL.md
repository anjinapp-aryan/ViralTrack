---
name: provider-development
description: Guide implementation or extension of a ViralTrack platform provider (YouTube, Instagram, TikTok, others) through the PlatformProvider interface, an adapter and the normalized model. Use when adding a provider, a provider capability or a new upstream endpoint mapping.
---

# provider-development

```text
PlatformProvider (viraltrack/providers/base.py)
      ↓
Adapter (viraltrack/providers/<platform>/: client.py, mapping.py, provider.py)
      ↓
Normalized ViralTrack model (viraltrack/domain: Content, Creator, Metric, Provenance)
```

Follow the YouTube provider as the pattern.

## Before writing code

1. **Legitimate source.** Name the official API or licensed source and link its documentation and terms.
   No scraping, private endpoints, cookies, CAPTCHA or auth bypass, or ban evasion.
   `docs/phase-0/PLATFORM_DATA_AUDIT.md` records what is and is not legitimate today. If the source is new
   or doubtful, stop and ask.
2. Run `reuse-audit`: does the foundation or an existing SDK already provide this?

## Checklist

| Item | Requirement |
|---|---|
| Capabilities | Declare every `Capability` with a true `supported` flag and a note explaining it or stating the limit |
| Unsupported | Don't override the method. The base raises `UnsupportedCapability` and makes no network call. Never return empty or fake data |
| Rate limits and quotas | Know the platform's limits. Stay under them. Never spread quota across multiple projects to evade limits |
| Retries | Retry transient errors only, with backoff and a cap. Never retry 4xx. Never retry in a way that hammers the platform |
| Caching | Only if needed. A cache is stored data, so run `data-retention` |
| Provenance | RAW values in `metrics`, DERIVED values in `derived`. Each carries `Provenance(provider, source, collected_at, kind)`. Use `None` for an unknown time |
| Errors | Map them to `ProviderUnavailable`, `NotFound`, `ProviderError`. Validate input before any request |
| Config | `VT_<PLATFORM>_*` in `viraltrack/config.py` and `.env.example`. Secrets never get defaults and are always masked |
| Registry | Register in `viraltrack/providers/registry.py` behind an enable flag |
| Persistence | Providers read. Any stored data needs a retention rule |
| Tests | Initialization, mapping from recorded fixtures (synthetic or licensed), provenance, each error path, each unsupported capability, read-only behaviour, and an optional live smoke test marked and skipped by default |
| Docs | Update `docs/phase-1/PROVIDER_BOUNDARY.md` (capability table) |

Never fake unsupported capabilities.
