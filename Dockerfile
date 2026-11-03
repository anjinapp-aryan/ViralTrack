# ViralTrack boundary package (retention job, provider adapters).
# The YouTube foundation has its own image: upstream/youtube-niche-finder/backend/Dockerfile.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml ./
COPY viraltrack ./viraltrack
RUN pip install . && useradd --system --uid 10001 viraltrack
USER viraltrack

CMD ["python", "-m", "viraltrack.config"]
