"""The local, dev and prod environment templates (.env_local, .env_dev, .env_prod).

They are gitignored on purpose (people fill them with secrets), so these tests skip in a fresh clone
and run on a machine that has them. They check that each template is a valid configuration with
placeholders only, and that the ignore rule is in place.
"""
import re
import subprocess

import pytest

from tests.conftest import ROOT
from tests.test_config import parse_env_file
from viraltrack.config import load_settings

NAMES = ("local", "dev", "prod")
SECRET_KEY = re.compile(r"KEY|PASSWORD|TOKEN|SECRET")


def template(name):
    path = ROOT / f".env_{name}"
    if not path.exists():
        pytest.skip(f"{path.name} is not present (gitignored)")
    return path


def test_templates_are_gitignored_but_the_example_is_not():
    def ignored(name):
        return subprocess.run(["git", "check-ignore", "-q", name], cwd=ROOT).returncode == 0
    assert all(ignored(f".env_{n}") for n in NAMES) and ignored(".env")
    assert not ignored(".env.example")


@pytest.mark.parametrize("name", NAMES)
def test_template_is_valid_configuration(name):
    env = parse_env_file(template(name))
    s = load_settings(env)
    assert s.youtube.ingestion.enabled is False
    assert s.youtube.approvals == frozenset()
    assert s.retention.transcripts_approved is False and s.retention.thumbnails_approved is False
    assert s.retention.youtube_stats_days == 30
    assert s.youtube.data_origin == "real"
    assert s.environment == {"local": "development", "dev": "development", "prod": "production"}[name]


@pytest.mark.parametrize("name", NAMES)
def test_template_holds_placeholders_only(name):
    for key, value in parse_env_file(template(name)).items():
        if SECRET_KEY.search(key):
            assert value == "" or re.fullmatch(r"<[^<>]+>", value), key
        if value.startswith(("postgres://", "postgresql://")):
            assert re.match(r"postgres(ql)?://<[^<>]+>:<[^<>]+>@<[^<>]+>/", value), key


def test_prod_template_is_strict_about_database_security():
    s = load_settings(parse_env_file(template("prod"))).database
    assert s.provider == "neon" and s.ssl_mode == "verify-full"
    env = parse_env_file(template("prod"))
    assert env["FOUNDATION_DB_SSL_MODE"] == "verify-full" and env["VT_RETENTION_APPLY"] == "true"


def test_local_template_needs_no_database_url():
    s = load_settings(parse_env_file(template("local"))).database
    assert (s.provider, s.url) == ("local", None)
