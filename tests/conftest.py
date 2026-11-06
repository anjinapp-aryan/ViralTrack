import json
import os
import pathlib
import sys
import uuid

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "niche_finder"
UPSTREAM_BACKEND = ROOT / "upstream" / "youtube-niche-finder" / "backend"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def pg_schema():
    """A fresh Postgres schema holding the pinned upstream niche-finder schema.

    The DDL comes from the upstream module itself (SCHEMA + MIGRATIONS), so the
    retention job is tested against the real table layout, not a copy.
    """
    url = os.environ.get("VT_TEST_DATABASE_URL")
    if not url:
        pytest.skip("VT_TEST_DATABASE_URL not set")
    import psycopg2

    if str(UPSTREAM_BACKEND) not in sys.path:
        sys.path.insert(0, str(UPSTREAM_BACKEND))
    from infrastructure.postgres import schema as upstream_schema

    name = f"vt_test_{uuid.uuid4().hex[:8]}"
    conn = psycopg2.connect(url)
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA {name}")
        cur.execute(f"SET search_path TO {name}")
        cur.execute(upstream_schema.SCHEMA)
        for table, cols in upstream_schema.MIGRATIONS.items():
            for col, ddl in cols.items():
                cur.execute(f"ALTER TABLE IF EXISTS {table} ADD COLUMN IF NOT EXISTS {col} {ddl}")
    conn.commit()
    try:
        yield conn, name
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA {name} CASCADE")
        conn.commit()
        conn.close()


# ---- process identity (CI: the discovery-offline job runs pytest as a restricted user) ----
# When VT_TEST_EXPECT_UID (and optionally VT_TEST_EXPECT_GID) is set, the session refuses to start unless this
# process really runs as that user, read from the operating system. The header shows the identity in the log.

def pytest_report_header(config):
    from tests.support.ci_checks import current_identity

    ident = current_identity()
    return "process identity: " + " ".join(f"{key}={value}" for key, value in ident.items())


def pytest_sessionstart(session):
    expected = os.environ.get("VT_TEST_EXPECT_UID")
    if not expected:
        return
    from tests.support.ci_checks import identity_problems

    problems = identity_problems(expected, os.environ.get("VT_TEST_EXPECT_GID"))
    if problems:
        pytest.exit("wrong process identity: " + "; ".join(problems), returncode=3)
