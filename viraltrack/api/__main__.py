"""Run the API: python -m viraltrack.api (binds VT_API_HOST:VT_API_PORT, default 127.0.0.1:8000)."""

import logging
import sys

from viraltrack.api.app import create_app
from viraltrack.api.settings import load_api_settings
from viraltrack.config import load_settings
from viraltrack.domain import ConfigError


def main() -> int:
    try:
        settings = load_settings()
        api = load_api_settings(environment=settings.environment)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 1
    import uvicorn

    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    uvicorn.run(
        create_app(settings, api),
        host=api.host,
        port=api.port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )  # the app writes its own access log without query strings
    return 0


if __name__ == "__main__":
    sys.exit(main())
