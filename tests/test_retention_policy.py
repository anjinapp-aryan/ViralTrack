"""Policy-versus-upstream contract: read the pinned upstream schema as text."""
import re

from tests.conftest import UPSTREAM_BACKEND
from viraltrack.retention import AGE_RULES, TABLES
from viraltrack.retention.policy import CHANNEL_DEPENDENTS, VIDEO_DEPENDENTS

SCHEMA_PY = (UPSTREAM_BACKEND / "infrastructure" / "postgres" / "schema.py").read_text(encoding="utf-8")


def upstream_tables() -> set[str]:
    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS ([a-z_]+)", SCHEMA_PY))
    tables |= set(re.findall(r'RLS_KEY_TABLE = "([a-z_]+)"', SCHEMA_PY))
    return tables


def test_every_upstream_table_is_classified():
    missing = upstream_tables() - set(TABLES)
    assert not missing, f"classify these upstream tables in viraltrack/retention/policy.py: {missing}"


def test_no_stale_classifications():
    assert set(TABLES) - upstream_tables() == set()


def test_rules_reference_real_tables():
    tables = upstream_tables()
    for rule in AGE_RULES:
        assert rule.table in tables, rule.name
    assert set(VIDEO_DEPENDENTS) | set(CHANNEL_DEPENDENTS) <= tables
