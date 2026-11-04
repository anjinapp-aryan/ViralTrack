# Local Setup

Tested on 2026-11-03 on Windows 11, Docker Desktop (Engine 29.5.3, Compose v5.1.4), Python 3.12.10, uv 0.12.15.

## 1. Clone with the foundation

```bash
git clone --recurse-submodules https://github.com/anjinapp-aryan/ViralTrack.git
cd ViralTrack
# existing clone: git submodule update --init
```

## 2. Configure

```bash
cp .env.example .env
cp upstream/youtube-niche-finder/.env.example upstream/youtube-niche-finder/.env
```

In `upstream/youtube-niche-finder/.env`:

- `YOUTUBE_API_KEY=` — a key from a **dedicated** Google Cloud project with "YouTube Data API v3" enabled.
  Without it, `web` runs but collects nothing, and `worker` exits with a message.
- `NF_DEFAULT_LOCALE=en` — upstream defaults to Russian.
- Change `POSTGRES_PASSWORD` from the default `niches` for anything beyond local use.

Never commit either `.env` (both are git-ignored).

## 3a. Run with Docker (recommended)

```bash
docker compose build web retention
docker compose up -d postgres web retention        # add `worker` once YOUTUBE_API_KEY is set
docker compose ps
curl http://localhost:8080/api/health
docker compose logs retention
```

What was verified: images built in 47 s. `postgres` and `web` came up healthy, and `/api/health` returned
`"ok": true, "hasApiKey": false`. `retention` started after `web` and applied the policy (0 rows, empty
corpus). The test ran with `WEB_PORT=8090 POSTGRES_HOST_PORT=5544` because of local port choices; the
defaults are 8080 and 5433.

Not verified: `worker` and real collection (no YouTube key on this machine).

## 3b. Run without Docker (development)

```bash
# ViralTrack package
uv venv .venv && uv pip install -r requirements-dev.lock && uv pip install --no-deps -e .

# Foundation (needs Postgres 16 + pgvector; set NICHE_DATABASE_URL or POSTGRES_*)
cd upstream/youtube-niche-finder/backend
uv venv .venv && uv pip install -r requirements.txt
python tests/seed_demo.py                  # optional: synthetic demo data, no quota
python -m uvicorn api:app --port 8080
```

On Windows add `tzdata` to the foundation environment. Its tests need the IANA time-zone database, which
Linux has built in.

## 4. Use the provider from Python

```python
from viraltrack.config import load_settings
from viraltrack.domain import Platform
from viraltrack.providers import build_providers, DiscoveryQuery

yt = build_providers(load_settings())[Platform.YOUTUBE]
page = yt.discover_content(DiscoveryQuery(period="7d", short_form=True))
for c in page.items:
    print(c.title, c.metric("views").value, c.metric("outlier_score").provenance.source)
```

Verified against the foundation on demo data (port 3903) and on Docker (port 8090, empty corpus).

## 5. Retention

```bash
python -m viraltrack.config                # prints settings with secrets masked; exit 1 if invalid
python -m viraltrack.database              # read-only database compatibility check (DATABASE_URL)
python -m viraltrack.retention             # report only (transaction rolled back)
python -m viraltrack.retention --apply     # delete
```

Verified on the demo database: report mode found 9 rows to delete and changed nothing.

## 6. Tests

```bash
pytest                                                       # unit tests; Postgres tests skip
VT_TEST_DATABASE_URL=postgresql://user:pw@localhost:5432/db pytest   # + retention on real upstream DDL
VT_TEST_FOUNDATION_URL=http://localhost:8080 pytest -m live_foundation
```
