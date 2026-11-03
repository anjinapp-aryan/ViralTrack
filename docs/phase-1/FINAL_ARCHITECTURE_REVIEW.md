# Final Architecture Review (Phase 1.1)

Read-only review of the repository at `355cd19` plus the Phase 1.1 working-tree changes. Each finding was
verified by command or test, not taken from the earlier report.

| Area | Question | Verdict | Evidence |
|---|---|---|---|
| Foundation | Is upstream still unmodified? | **PASS** | `git -C upstream/youtube-niche-finder status` is clean at `d872014`. The CI pin check passed on GitHub run 41671578970 |
| Adapter | Does it depend on the documented API, not upstream internals? | **PASS** | It calls only `/api/viral`, `/api/search`, `/api/channels/{id}`, `/api/channels/{id}/history` and the documented query parameters (`sort_by`, `only_shorts`, …) from `docs/http-api.md`. No ViralTrack module imports from `upstream/` (grep) |
| Domain | Is the domain independent of YouTube? | **PASS** | `viraltrack/domain` imports only the stdlib and its own modules. `Platform`, `ContentType`, `DataOrigin` and `Exposure` are platform-neutral. A parametrized test builds `Content` for every platform |
| Provider | Can Instagram and TikTok be added later? | **PASS** | `PlatformProvider` + `PlatformCapabilities` + registry. A new provider adds one package and its own `MetricPolicy` rules. Nothing in the domain changes |
| Capabilities | Are unsupported capabilities explicit? | **PASS** | Base methods raise `UnsupportedCapability`. YouTube declares `GET_CONTENT`, `GLOBAL_TRENDING`, `HASHTAGS` and `AUDIO` unsupported, with reasons. Tests confirm no network call is made |
| Data | Are raw and derived data separated? | **PASS** | `Content.metrics` holds only RAW and `Content.derived` only DERIVED; the model enforces it |
| Derived metrics | Can a restricted metric become user-visible through ViralTrack? | **PASS (ViralTrack layer)** / **OPEN (foundation UI)** | Enforced in three places: the allow-list mapping, the policy check, and the `Content` invariant. Sorting is also gated. The foundation's own UI, API and MCP still show restricted metrics: they are INTERNAL_ONLY and must not be offered to end users (DERIVED_METRIC_POLICY.md) |
| Provenance | Can source, collection time and origin be identified? | **PASS with one gap** | Every metric carries provider, source, kind, origin, adapter and exposure; records carry their external id and `retrieved_at`. **Gap:** `collected_at` is `None` for video metrics because the foundation's list endpoints don't expose fetch times. Retention bounds their age to 30 days. Fixing it needs an upstream change (PR) |
| Demo vs real | Can demo data pass as real? | **PASS** | `DataOrigin` on every record and metric. `VT_ENV=production` requires origin `real`. With origin `real`, non-YouTube ids (the demo seed's `bvid008`) are rejected, which was verified against the live demo foundation |
| Retention | Can stored provider data be removed according to policy? | **PASS** | Every upstream table is classified (contract test). The four open groups are decided. The job fails closed and is tested on the real DDL; it runs daily in Docker |
| Upstream upgrades | Can the submodule move without rewriting ViralTrack? | **PASS** | Coupling is limited to the documented API and the schema. Both are guarded: new tables fail the policy test, and new numeric API fields fail the allow-list test |

## Security review

| Check | Result |
|---|---|
| Committed secrets | None. Full `git log -p --all` scanned for Google/OpenAI/GitHub/Slack keys and private keys; no `.env`, `.pem` or `.key` files are tracked |
| Keys in logs | `Settings.describe()` masks the token and the DSN password (tested). The provider never logs headers. The retention CLI prints counts only |
| Environment handling | Secrets have no defaults. `.env` is git-ignored. Production refuses demo/test data origins |
| Injection | Retention SQL interpolates only module constants, plus a schema name validated by regex; all values are bound parameters. **Fixed in 1.1:** creator ids were placed unescaped in URL paths (`../admin`); they are now percent-encoded (test added) |
| Exposed endpoints | ViralTrack exposes no endpoint. The foundation's `web`, `postgres` and `mcp-https` are published on `127.0.0.1` only by the upstream compose file. Without `NF_MULTI_USER=1` the foundation has no sign-in, so it must stay local |
| Docker | `retention` runs as a non-root user (uid 10001), publishes no ports and is not privileged. The default Postgres password `niches` comes from upstream: change it for anything non-local (LOCAL_SETUP.md). `ollama/ollama:latest` (profile, not started) is unpinned |

Not changed (outside Phase 1 scope): upstream's single-user no-auth default, and its `NF_DEFAULT_LOCALE=ru`.

## Residual architecture risks

1. Single-author upstream (bus factor). Mitigated by the pin and contract tests.
2. The foundation UI cannot become ViralTrack's production UI while restricted metrics are shown there. A
   ViralTrack UI must be built on the provider layer (Phase 2+ decision).
3. The `collected_at` gap needs an upstream contribution.
