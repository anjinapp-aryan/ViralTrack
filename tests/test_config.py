import pytest

from tests.conftest import ROOT
from viraltrack.config import load_settings
from viraltrack.domain import ConfigError


def parse_env_file(path):
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key] = value
    return env


def test_defaults_are_safe():
    s = load_settings({})
    assert s.environment == "development"
    assert s.youtube.enabled is True
    assert s.youtube.api_token is None
    assert s.retention.youtube_amendment_accepted is False
    assert s.retention.youtube_stats_days == 30
    assert s.retention.youtube_text_days == 30
    assert s.retention.apply is False
    assert s.retention.transcripts_approved is False
    assert s.retention.thumbnails_approved is False


def test_env_example_is_valid_and_has_no_secrets():
    env = parse_env_file(ROOT / ".env.example")
    s = load_settings(env)
    assert s.youtube.api_token is None
    assert s.database.url is None
    assert "YOUTUBE_API_KEY" not in env


def test_stats_window_capped_without_amendment():
    with pytest.raises(ConfigError, match="between 1 and 30"):
        load_settings({"VT_RETENTION_YOUTUBE_STATS_DAYS": "90"})


def test_amendment_allows_36_months_of_stats_but_not_text():
    s = load_settings({"VT_YOUTUBE_ANALYTICS_AMENDMENT_ACCEPTED": "true"})
    assert s.retention.youtube_stats_days == 1095
    assert s.retention.youtube_text_days == 30
    with pytest.raises(ConfigError):
        load_settings({"VT_YOUTUBE_ANALYTICS_AMENDMENT_ACCEPTED": "true",
                       "VT_RETENTION_YOUTUBE_TEXT_DAYS": "31"})


@pytest.mark.parametrize("key,value", [
    ("VT_ENV", "staging"),
    ("VT_LOG_LEVEL", "LOUD"),
    ("VT_YOUTUBE_ENABLED", "maybe"),
    ("VT_YOUTUBE_TIMEOUT_SECONDS", "abc"),
    ("VT_YOUTUBE_FOUNDATION_URL", "localhost:8080"),
])
def test_invalid_values_rejected(key, value):
    with pytest.raises(ConfigError):
        load_settings({key: value})


def test_describe_masks_secrets():
    s = load_settings({"VT_YOUTUBE_FOUNDATION_TOKEN": "tok-secret",
                       "VT_DATABASE_URL": "postgresql://niches:pw-secret@db:5432/niches"})
    text = str(s.describe())
    assert "tok-secret" not in text and "pw-secret" not in text
    assert "db:5432/niches" in text


def test_production_requires_real_data_origin():
    with pytest.raises(ConfigError, match="real"):
        load_settings({"VT_ENV": "production", "VT_YOUTUBE_DATA_ORIGIN": "demo"})
    assert load_settings({"VT_ENV": "production"}).youtube.data_origin == "real"


def test_amendment_flag_is_the_only_source_of_approvals():
    assert load_settings({}).youtube.approvals == frozenset()
    s = load_settings({"VT_YOUTUBE_ANALYTICS_AMENDMENT_ACCEPTED": "true"})
    assert s.youtube.approvals == {"youtube_analytics_amendment"}
