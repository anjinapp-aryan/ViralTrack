# ViralTrack

Viral-content discovery and trend intelligence for creators.

ViralTrack is built on existing open source instead of from scratch. Its YouTube engine is
[youtube-niche-finder](https://github.com/pandich93/youtube-niche-finder) (MIT), included unmodified as a
pinned submodule. This repository adds a platform-neutral boundary around it:

- `viraltrack/domain`: a platform-neutral content model in which every metric carries provenance
  (raw platform data vs derived values)
- `viraltrack/providers`: a capability-based provider interface and the YouTube adapter
- `viraltrack/retention`: enforcement of YouTube's data-storage rules on the foundation's database

Instagram and TikTok are not integrated: Phase 0 found no legitimate discovery source for them.

- Setup: [docs/phase-1/LOCAL_SETUP.md](docs/phase-1/LOCAL_SETUP.md)
- Architecture: [docs/phase-1/ARCHITECTURE.md](docs/phase-1/ARCHITECTURE.md)
- Research and decisions: [docs/phase-0](docs/phase-0), [docs/phase-1](docs/phase-1)
- Third-party licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
