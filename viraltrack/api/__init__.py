"""The ViralTrack HTTP API (D5). Needs the optional `api` dependencies: pip install -e ".[api]"."""

from viraltrack.api.app import API_VERSION, create_app

__all__ = ["API_VERSION", "create_app"]
