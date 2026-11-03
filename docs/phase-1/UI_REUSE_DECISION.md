# UI Reuse Decision

The foundation ships a working dashboard: static JS, 31 screens, i18n (en/ru), served by its `web` service
on :8080. ViralTrack has no UI of its own and builds none in Phase 1.

| UI capability | Source | Decision | Note |
|---|---|---|---|
| Overview dashboard (viral videos, outlier channels, categories, keywords, competition) | niche-finder `screens/overview.js` | **REUSE** | Works on demo data |
| Viral / outlier lists with filters (period, subscribers, views, Shorts, region, category) | `viral.js`, `find.js` | **REUSE** | |
| Video and channel cards | `ui.js`, `shared.js` | **REUSE** | Link out to youtube.com |
| Channel page (growth, velocity, history) | `channel.js` | **REUSE** | |
| Collections / saved items with folders | `saved.js` | **REUSE** | open-outlier collections: **REFERENCE** only |
| Watchlist (tracked channels) | `tracker.js`, `channels.js` | **REUSE** | |
| Alerts | `alerts.js` | **REUSE** | Alert logic is upstream's. ViralTrack adds none in Phase 1 |
| Niches, keywords, language gaps, packaging, ideas | various | **REUSE** | Available. Not ViralTrack-specific |
| Branding ("niche-finder" → "ViralTrack") | — | **ADAPT** (later) | Needs a theme or override layer, not a fork of the screens. Not done in Phase 1 |
| Default language | `NF_DEFAULT_LOCALE=ru` upstream | **ADAPT** (configuration) | Set `NF_DEFAULT_LOCALE=en` in the foundation's `.env` (see LOCAL_SETUP.md) |
| In-app video playback | — | **BUILD** (later) | No candidate embeds a player. Use YouTube IFrame / IG / TikTok oEmbed |
| Cross-platform unified dashboard and comparison | social-dash, content-dashboard | **REFERENCE** | Layout ideas only. Needs a second legitimate platform first |
| Provenance labels on every number ("not a YouTube metric") | upstream `/api/scores` + "?" hints | **REUSE**, then ADAPT | Upstream already explains each score. ViralTrack's model tags it in code |

Decision: **the foundation's UI is ViralTrack's UI for now.** New UI work starts only when there is a
ViralTrack-specific feature to show: player, cross-platform view, branding.
