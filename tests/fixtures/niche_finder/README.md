Responses captured from the niche-finder HTTP API (upstream commit d872014)
running on its own synthetic demo seed (`backend/tests/seed_demo.py`, MIT).
No real YouTube data: video and channel ids, titles and numbers are synthetic.

## AI Content Intelligence fixtures (`ai_*.json`)

Hand-written in the shapes of the pinned foundation's routes (`/api/viral`, `/api/inspect/video` with
`fetch=false`, `/api/niches`, `/api/niches/{slug}/videos`), not captured. Every id, title, channel and number is
invented. They carry the foundation's restricted fields on purpose, so a leak would show in the tests.
`ai_inspect.json` and `ai_niche_videos.json` map an id or slug to one response body.
