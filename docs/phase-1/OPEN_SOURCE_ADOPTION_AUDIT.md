# Open-Source Adoption Audit

This is an engineering license screen, not legal advice. Items marked **UNRESOLVED** need a human decision
before production.

## Foundation and its contents

| Component | Source | License | Reuse decision | Notes |
|---|---|---|---|---|
| youtube-niche-finder (all code) | github.com/pandich93/youtube-niche-finder @ d872014 | MIT (`LICENSE`, (c) 2026 Fozil Umarov) | REUSE unmodified (submodule) | No other license header, SPDX tag or copyright notice in the tree (searched). The MIT notice ships with the submodule and is repeated in `THIRD_PARTY_NOTICES.md`. |
| Frontend (static JS, 31 screens) | same repo, `frontend/` | MIT | REUSE as served by the `web` service | Plain JavaScript, no npm tree, no vendored libraries, no external scripts (only links to youtube.com and console.cloud.google.com). |
| Chrome extension | same repo, `extension/` | MIT | Not used in Phase 1 | |
| Screenshots | same repo, `assets/*.jpg` (17 files) | MIT as files | **Not reused** | May show real YouTube titles and thumbnails, which are third-party content. ViralTrack must not reuse them in its own marketing. |
| Demo seed (synthetic data) | `backend/tests/seed_demo.py` | MIT | Recorded responses used as ViralTrack test fixtures | Synthetic ids and numbers. Attribution in `tests/fixtures/niche_finder/README.md`. |

## Python dependencies of the foundation (79 installed, `backend/requirements.txt`)

Scanned with `pip-licenses` in Phase 0 at the same commit (d872014), so the result still applies.

| Component | License | Decision | Notes |
|---|---|---|---|
| ~74 packages (fastapi, uvicorn, httpx, numpy, pillow, mcp, cryptography, …) | MIT / BSD / Apache-2.0 / PSF / ISC | OK | |
| psycopg2-binary | LGPL-3.0 (+ exception) | OK as an unmodified library | The binary wheel bundles libpq (PostgreSQL License) and OpenSSL. Not modified, dynamically used. |
| certifi | MPL-2.0 | OK unmodified | |
| tqdm | MPL-2.0 AND MIT | OK unmodified | |
| py_rust_stemmers 0.1.8 (via fastembed) | MIT (resolved in Phase 1.1) | OK | The wheel ships `licenses/LICENSE` (MIT (c) 2024 qdrant) but no `License` metadata field, so scanners report UNKNOWN. Its CycloneDX SBOM lists 24 bundled Rust crates: MIT OR Apache-2.0, MIT OR BSD-3-Clause, Apache-2.0 WITH LLVM-exception, Unicode-3.0 |

## Machine-learning model weights (downloaded at runtime, not in git)

| Component | Source | License | Decision | Notes |
|---|---|---|---|---|
| sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | Hugging Face (fastembed) | apache-2.0 (HF API, verified 2026-11-03) | OK | Text embeddings for semantic niche search |
| Qdrant/clip-ViT-B-32-vision / -text | Hugging Face (fastembed) | mit (HF API, verified 2026-11-03) | OK | Thumbnail similarity. Training data of CLIP is out of scope here. |

## ViralTrack's own dependencies (`requirements-dev.lock`, 17 pinned)

| Component | License | Decision |
|---|---|---|
| httpx, httpcore, anyio, idna, sniffio, h11, certifi (MPL-2.0) | BSD / MIT / MPL-2.0 | OK. httpx is the same client the foundation uses. |
| psycopg2-binary | LGPL-3.0 | OK unmodified. The same driver the foundation uses. |
| pytest, pluggy, iniconfig, packaging, ruff (dev only) | MIT / Apache-2.0 | OK |

## Docker images

| Image | Used by | License | Notes |
|---|---|---|---|
| python:3.12-slim | foundation `web`/`worker`, ViralTrack `retention` | PSF + Debian packages (mixed OSS) | Standard base image |
| pgvector/pgvector:pg16 | foundation `postgres` | PostgreSQL License (Postgres and pgvector) | |
| caddy:2-alpine | foundation `mcp-https` (profile only) | Apache-2.0 | Not started by ViralTrack |
| ollama/ollama:latest | foundation `ollama` (profile only) | MIT | Not started. Unpinned tag; pin it before use. |

## Third-party services the foundation can call

| Service | Required? | Terms |
|---|---|---|
| YouTube Data API v3 | Yes | YouTube API Services ToS and Developer Policies. Retention: see DATA_RETENTION_POLICY.md |
| YouTube Analytics API + Google OAuth (own channel) | Optional, off | Google API Services User Data Policy |
| OpenRouter / Ollama / other LLM providers | Optional, off | Each provider's terms. Sends titles and comments to the LLM. |
| Telegram, SMTP, Sentry | Optional, off | |

## Attribution requirements

- MIT: keep the copyright and permission notice with copies of the software. Met: the submodule carries
  `LICENSE`, and `THIRD_PARTY_NOTICES.md` repeats it.
- Apache-2.0 model weights: keep the license with any redistributed weights. Weights are downloaded at runtime,
  never redistributed by ViralTrack.

## Files copied or adapted from upstream

None. ViralTrack code calls upstream; it contains no upstream source. The only upstream-derived files are
synthetic JSON test fixtures (recorded API output of the MIT demo seed).

## Final classification (Phase 1.1)

Obligations below apply when ViralTrack **distributes** software (e.g. publishes Docker images or ships
installers). Running a hosted service is not distribution under these licenses. AGPL would differ, but none is
present.

| Component | License | Class | Obligation / note |
|---|---|---|---|
| youtube-niche-finder @ d872014 | MIT | **NOTICE REQUIRED** | Keep the copyright and permission notice (done: submodule `LICENSE` + `THIRD_PARTY_NOTICES.md`) |
| httpx, httpcore, anyio, idna, h11, typing_extensions, pytest, ruff, pluggy, iniconfig, packaging, Pygments, colorama | BSD / MIT / Apache-2.0 / PSF | **CLEAR** | Keep their notices in redistributed packages (pip does) |
| psycopg2-binary 2.9.13 | LGPL-3.0 with exceptions (wheel bundles libpq, OpenSSL) | **NOTICE REQUIRED** | Used unmodified as a separate module. On distribution: include the LGPL text, point to source, and allow replacing the library. Not a reason to remove it |
| certifi 2026.10.23 | MPL-2.0 | **NOTICE REQUIRED** | File-level copyleft, unmodified. Keep the notice and make its source available on distribution |
| tqdm 4.70.1 | MPL-2.0 AND MIT | **NOTICE REQUIRED** | As certifi |
| numpy, pillow, onnxruntime, tokenizers, fastembed, the rest of the 79 foundation packages | BSD / MIT / MIT-CMU / Apache-2.0 / Zlib / CC0 / 0BSD | **CLEAR** | |
| py_rust_stemmers 0.1.8 | MIT (+ permissive crates) | **CLEAR** | Resolved above |
| paraphrase-multilingual-MiniLM-L12-v2 (weights) | Apache-2.0 | **NOTICE REQUIRED** | Only if ViralTrack redistributes the weights. Today they are downloaded at runtime |
| clip-ViT-B-32 vision/text (weights) | MIT | **CLEAR** | Same |
| python:3.12-slim | PSF + Debian packages (includes GPL components) | **NOTICE REQUIRED** | Publishing an image built on it means offering corresponding source for its GPL packages (standard Debian practice) |
| pgvector/pgvector:pg16 | PostgreSQL License | **CLEAR** | |
| caddy:2-alpine / ollama:latest | Apache-2.0 / MIT | **CLEAR** | Profile services, not started. Pin ollama before use |
| Upstream screenshots (`assets/*.jpg`) | MIT as files; may depict third-party YouTube content | **REVIEW REQUIRED** if reused | Not reused |
| pgserver | Not a project dependency | n/a | Used only by the local test sandbox, never shipped |

**Nothing is BLOCKED.**

## Unresolved

1. ~~`py_rust_stemmers` license metadata~~: resolved (MIT).
2. **ViralTrack itself has no license.** Recommendation and the owner question: VIRALTRACK_LICENSE_DECISION.md.
