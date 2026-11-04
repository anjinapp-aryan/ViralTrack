"""Rendered Docker Compose checks: API-key isolation (F1) and thumbnail-safe defaults (F2).

These run `docker compose config` (no daemon, no containers, no network) against the real files and
inspect the merged result, not individual YAML fragments. Skipped when the docker CLI is missing.
The sentinel key below is a fake value; the real key in a developer's .env is never read or printed.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SENTINEL = "sentinel-not-a-real-key-0123456789"
pytestmark = pytest.mark.skipif(shutil.which("docker") is None, reason="docker CLI not installed")


def render(tmp_path, env_lines=(), files=(), extra_env=None, profiles=()):
    """Render the stack from a copy-free, throwaway env file so the developer's .env is never used."""
    envfile = tmp_path / "test.env"
    envfile.write_text("\n".join(("YOUTUBE_API_KEY=" + SENTINEL, *env_lines)) + "\n", encoding="utf-8")
    cmd = ["docker", "compose", "--env-file", str(envfile)]
    for f in files:
        cmd += ["-f", str(ROOT / f)]
    for p in profiles:
        cmd += ["--profile", p]
    cmd += ["config", "--format", "json"]
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("VT_", "DATABASE_", "WORKER_", "LLM_", "YOUTUBE_", "POSTGRES_"))}
    env.update(extra_env or {})
    out = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, check=True, timeout=120)
    return json.loads(out.stdout.decode("utf-8"))["services"]


def env_of(services, name):
    return services[name].get("environment", {})


# ---- F1: retention does not receive the API key -------------------------------------------------

def test_retention_has_no_env_file_and_no_api_key(tmp_path):
    svc = render(tmp_path)["retention"]
    assert "env_file" not in svc
    assert "YOUTUBE_API_KEY" not in svc.get("environment", {})
    assert SENTINEL not in json.dumps(svc)


def test_retention_receives_only_vt_and_database_variables(tmp_path):
    names = set(env_of(render(tmp_path), "retention"))
    assert names and all(n.startswith(("VT_", "DATABASE_")) for n in names), sorted(names)


def test_retention_still_gets_what_it_needs(tmp_path):
    svc = render(tmp_path, ["VT_RETENTION_APPLY=true", "VT_THUMBNAILS_APPROVED=false",
                            "VT_TRANSCRIPTS_APPROVED=false", "POSTGRES_USER=u1", "POSTGRES_PASSWORD=pw1",
                            "POSTGRES_DB=d1", "DATABASE_SCHEMA=nf"])["retention"]["environment"]
    assert svc["VT_RETENTION_APPLY"] == "true"
    assert svc["VT_THUMBNAILS_APPROVED"] == "false"
    assert svc["DATABASE_PROVIDER"] == "local"
    assert svc["DATABASE_URL"] == "postgresql://u1:pw1@postgres:5432/d1"   # same default as before
    assert svc["DATABASE_SCHEMA"] == "nf"


def test_retention_settings_load_from_the_rendered_environment(tmp_path):
    """The exact variables compose hands the container must pass ViralTrack's own validation,
    including the blanks that stand for 'default'."""
    from viraltrack.config import load_settings
    svc = env_of(render(tmp_path), "retention")
    settings = load_settings(dict(svc))
    assert settings.database.provider == "local"
    assert settings.retention.apply is False
    assert settings.retention.thumbnails_approved is False


def test_web_and_worker_still_receive_the_api_key(tmp_path):
    services = render(tmp_path)
    for name in ("web", "worker"):
        assert env_of(services, name)["YOUTUBE_API_KEY"] == SENTINEL


def test_managed_database_retention_is_isolated_too(tmp_path):
    services = render(tmp_path, files=("docker-compose.yml", "deploy/compose.managed-db.yml"),
                      extra_env={"DATABASE_PROVIDER": "neon", "DATABASE_URL": "postgresql://u:p@h/d?sslmode=require"})
    assert "env_file" not in services["retention"]
    assert "YOUTUBE_API_KEY" not in services["retention"].get("environment", {})
    assert env_of(services, "retention")["DATABASE_PROVIDER"] == "neon"
    assert env_of(services, "web")["YOUTUBE_API_KEY"] == SENTINEL


# ---- F2: plain compose is the thumbnail-safe configuration ----------------------------------------

SAFE = {"WORKER_THUMBS": "0", "WORKER_THUMB_EMBED": "0", "LLM_PROVIDER": "none"}


def test_plain_compose_config_is_thumbnail_safe(tmp_path):
    services = render(tmp_path)
    for name in ("web", "worker"):
        for key, want in SAFE.items():
            assert env_of(services, name)[key] == want, (name, key)


def test_every_foundation_service_that_runs_the_app_is_safe(tmp_path):
    """Services behind compose profiles (mcp, mcp-http) are safe once enabled."""
    services = render(tmp_path, profiles=("manual", "http"))
    for name, svc in services.items():
        if svc.get("command") and "python" in json.dumps(svc.get("command")) and name != "retention":
            for key, want in SAFE.items():
                assert env_of(services, name)[key] == want, (name, key)
    assert {"web", "worker", "mcp", "mcp-http"} <= set(services)


@pytest.mark.parametrize("value", ["1", "true", ""])
def test_a_root_env_value_cannot_switch_thumbnails_back_on(tmp_path, value):
    services = render(tmp_path, [f"WORKER_THUMBS={value}", f"WORKER_THUMB_EMBED={value}",
                                 f"LLM_PROVIDER={value or 'openai'}"],
                      extra_env={"WORKER_THUMBS": value or "1", "WORKER_THUMB_EMBED": value or "1"})
    for name in ("web", "worker"):
        for key, want in SAFE.items():
            assert env_of(services, name)[key] == want, (name, key)


def test_managed_database_override_keeps_the_safe_defaults(tmp_path):
    services = render(tmp_path, files=("docker-compose.yml", "deploy/compose.managed-db.yml"),
                      extra_env={"DATABASE_PROVIDER": "neon", "DATABASE_URL": "postgresql://u:p@h/d?sslmode=require"})
    for name in ("web", "worker"):
        for key, want in SAFE.items():
            assert env_of(services, name)[key] == want
        assert env_of(services, name)["PGSSLMODE"] == "require"


def test_explicit_profile_flag_is_harmless_when_repeated(tmp_path):
    """The old documented command (-f profile) must keep working; the profile is merged twice."""
    services = render(tmp_path, files=("docker-compose.yml", "deploy/compose.ingestion-profile.yml"))
    assert env_of(services, "worker")["WORKER_THUMBS"] == "0"


def test_the_local_stack_is_otherwise_unchanged(tmp_path):
    services = render(tmp_path)
    assert set(services) >= {"postgres", "web", "worker", "retention"}
    assert services["retention"]["depends_on"]["web"]["condition"] == "service_healthy"
    assert "retention" not in services["web"].get("depends_on", {})
