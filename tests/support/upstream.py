"""Helpers to run the real upstream API offline (see upstream_runner.py and upstream_collect_runner.py)."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.conftest import UPSTREAM_BACKEND

RUNNER = Path(__file__).with_name("upstream_runner.py")
COLLECT_RUNNER = Path(__file__).with_name("upstream_collect_runner.py")


def upstream_python() -> str:
    path = os.environ.get("VT_TEST_UPSTREAM_PYTHON")
    if not path or not Path(path).exists():
        message = "VT_TEST_UPSTREAM_PYTHON not set (a Python with the upstream requirements)"
        if os.environ.get("VT_TEST_REQUIRE_UPSTREAM") == "1":    # CI: a skip would hide a missing setup
            pytest.fail(message)
        pytest.skip(message)
    return path


def _run(runner: Path, schema: str, payload: dict) -> dict:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("YOUTUBE_", "NICHE_", "POSTGRES_", "NF_", "WORKER_", "LLM_"))
    }
    env.update(
        NICHE_DATABASE_URL=os.environ["VT_TEST_DATABASE_URL"],
        NICHE_DB_SCHEMA=schema,
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
        WORKER_THUMBS="0",
        LLM_PROVIDER="none",
    )
    done = subprocess.run(
        [upstream_python(), str(runner), str(UPSTREAM_BACKEND)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
        encoding="utf-8",
    )
    line = next((ln for ln in reversed(done.stdout.splitlines()) if ln.startswith("RESULT:")), None)
    if line is None:
        raise AssertionError(f"upstream runner failed ({done.returncode}): {done.stderr[-800:]}")
    result = json.loads(line[len("RESULT:") :])
    assert result["network_attempts"] == 0, "an offline test tried to reach the network"
    return result


def run_upstream(schema: str, paths: list[str]) -> dict:
    """GET each path from the real upstream API over `schema`. Returns the runner's JSON result."""
    return _run(RUNNER, schema, {"paths": list(paths)})


def run_upstream_collect(
    schema: str, bodies: list[dict], pages_available: int = 1, per_page: int = 2
) -> dict:
    """POST each body to the real `/api/collect/niche` with YouTube faked; nothing leaves the process."""
    return _run(
        COLLECT_RUNNER,
        schema,
        {"calls": [{"body": b} for b in bodies], "pages_available": pages_available, "per_page": per_page},
    )
