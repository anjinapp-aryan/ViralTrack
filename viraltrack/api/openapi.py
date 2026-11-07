"""Print the API's OpenAPI document: python -m viraltrack.api.openapi > docs/api/openapi-v1.json

Built without any provider connection or network access, so the contract can be generated anywhere.
"""

import json
import sys

from viraltrack.api.app import create_app
from viraltrack.api.settings import load_api_settings
from viraltrack.config import load_settings


def document() -> dict:
    app = create_app(load_settings({"VT_YOUTUBE_DATA_ORIGIN": "test"}), load_api_settings({}), providers={})
    return app.openapi()


if __name__ == "__main__":
    sys.stdout.write(json.dumps(document(), indent=2, sort_keys=True) + "\n")
