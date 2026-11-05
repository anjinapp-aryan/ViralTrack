"""Phase 2 Batch 3: retention and ingestion profile, verified on the pinned upstream schema.

Static tests read the pinned upstream source to establish what collection writes and which
timestamps it touches. Tests marked `postgres` run the retention job on the real upstream DDL
with synthetic rows and controlled timestamps. No YouTube data is involved and no request is made.
"""
import re
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import ROOT, UPSTREAM_BACKEND
from viraltrack.config import load_settings
from viraltrack.retention import run
from viraltrack.retention.policy import TABLES, THUMBNAIL_TABLES, TRANSCRIPT_TABLES, Action

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def ago(days: float) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def src(*parts) -> str:
    return (UPSTREAM_BACKEND.joinpath(*parts)).read_text(encoding="utf-8")


# which modules write what collection and the worker store ----------------------------------

COLLECTION_MODULES = [("application", "collecting.py"), ("application", "freshness.py"),
                      ("application", "packaging.py"), ("application", "thumbnail_search.py"),
                      ("infrastructure", "postgres", "repositories.py")]
_WRITE = re.compile(r"\b(?:INSERT INTO|UPDATE|DELETE FROM)\s+([a-z_]+)\b")


def schema_tables() -> set[str]:
    return set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", src("infrastructure", "postgres",
                                                                    "schema.py")))


def written_tables() -> set[str]:
    found = set()
    for module in COLLECTION_MODULES:
        found |= set(_WRITE.findall(src(*module)))
    return found & schema_tables()


def test_every_table_that_collection_writes_is_classified():
    written = written_tables()
    assert {"videos", "channels", "video_stats_history", "channel_stats_history", "gone_items",
            "video_changes", "video_niches", "niches", "thumbnail_archive"} <= written
    assert written <= set(TABLES), sorted(written - set(TABLES))


def test_every_upstream_table_is_classified_with_an_action():
    assert schema_tables() <= set(TABLES)
    assert all(rule.action in set(Action) for rule in TABLES.values())


def test_no_collection_table_is_left_unmanaged():
    """KEEP / REVIEW are allowed only for tables that hold no YouTube API data."""
    for name in written_tables():
        rule = TABLES[name]
        if rule.action in (Action.KEEP, Action.REVIEW):
            assert not {"RAW_PROVIDER_DATA"} & {c.value for c in rule.classes}, name


# which timestamp expires a row, and what can move it --------------------------------------

def test_collection_upserts_cannot_touch_the_retention_clocks():
    repo = src("infrastructure", "postgres", "repositories.py")
    cols = re.search(r"_VIDEO_COLS = \[(.*?)\]", repo, re.S).group(1)
    ccols = re.search(r"_CHANNEL_COLS = \[(.*?)\]", repo, re.S).group(1)
    for clock in ("first_seen_at", "texts_refreshed_at"):
        assert clock not in cols and clock not in ccols


def test_only_the_freshness_job_sets_texts_refreshed_at():
    writers = []
    for path in UPSTREAM_BACKEND.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"SET\s+texts_refreshed_at|texts_refreshed_at\s*=\s*\?", text):
            writers.append(path.name)
    assert writers == ["freshness.py"], writers


def test_no_update_statement_rewrites_first_seen_at():
    for path in UPSTREAM_BACKEND.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        assert not re.search(r"UPDATE\s+(?:videos|channels)\s+SET[^\"']*first_seen_at", text), path


@pytest.mark.postgres
def test_expiry_uses_the_text_clock_and_a_stats_refresh_cannot_extend_it(pg_schema):
    conn, s = pg_schema
    rows = [  # id, texts_refreshed_at, first_seen_at, updated_at
        ("keep_29", ago(29), ago(100), ago(1)),
        ("drop_31", ago(31), ago(100), ago(1)),            # stats refreshed yesterday, text is old
        ("drop_first_seen", None, ago(31), ago(1)),        # never text-refreshed, first seen 31 d ago
        ("keep_first_seen", None, ago(29), ago(29)),
    ]
    with conn.cursor() as cur:
        for vid, texts, first, upd in rows:
            cur.execute(f"INSERT INTO {s}.videos (video_id, channel_id, title, updated_at, "
                        "first_seen_at, texts_refreshed_at) VALUES (%s,'UCa','t',%s,%s,%s)",
                        (vid, upd, first, texts))
        # exactly what upstream's refresh_stats runs on every stored video
        cur.execute(f"UPDATE {s}.videos SET view_count=%s, like_count=COALESCE(%s, like_count), "
                    "comment_count=COALESCE(%s, comment_count), title=COALESCE(%s, title), "
                    "updated_at=%s WHERE video_id=%s", (10, 1, 1, "t", ago(0), "drop_31"))
        cur.execute(f"UPDATE {s}.videos SET updated_at=%s WHERE video_id IN "
                    "('drop_first_seen', 'keep_29', 'keep_first_seen')", (ago(0),))
    conn.commit()
    run(conn, load_settings({}).retention, schema=s, now=NOW, apply=True)
    with conn.cursor() as cur:
        cur.execute(f"SELECT video_id FROM {s}.videos ORDER BY 1")
        assert [r[0] for r in cur.fetchall()] == ["keep_29", "keep_first_seen"]


@pytest.mark.postgres
def test_only_a_real_text_refresh_restarts_the_clock(pg_schema):
    conn, s = pg_schema
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO {s}.videos (video_id, channel_id, title, updated_at, first_seen_at,"
                    " texts_refreshed_at) VALUES ('v','UCa','t',%s,%s,%s)",
                    (ago(26), ago(60), ago(26)))
        # the freshness job re-reads rows older than 25 days and stamps them
        cur.execute(f"UPDATE {s}.videos SET updated_at=%s, texts_refreshed_at=%s WHERE video_id='v'",
                    (ago(0), ago(0)))
    conn.commit()
    run(conn, load_settings({}).retention, schema=s, now=NOW, apply=True)
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {s}.videos")
        assert cur.fetchone()[0] == 1
    # 31 days later with no further refresh the row expires
    run(conn, load_settings({}).retention, schema=s, now=NOW + timedelta(days=31), apply=True)
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {s}.videos")
        assert cur.fetchone()[0] == 0


@pytest.mark.postgres
def test_stale_channels_follow_the_same_text_clock(pg_schema):
    conn, s = pg_schema
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO {s}.channels (channel_id, title, updated_at, first_seen_at) VALUES "
                    "('UCkeep','a',%s,%s), ('UCdrop','b',%s,%s)",
                    (ago(0), ago(29), ago(0), ago(31)))
    conn.commit()
    run(conn, load_settings({}).retention, schema=s, now=NOW, apply=True)
    with conn.cursor() as cur:
        cur.execute(f"SELECT channel_id FROM {s}.channels")
        assert [r[0] for r in cur.fetchall()] == ["UCkeep"]


# daily cleanup across every collection-written table ---------------------------------------

@pytest.mark.postgres
def test_cleanup_deletes_expired_rows_in_every_collection_table(pg_schema):
    conn, s = pg_schema
    with conn.cursor() as cur:
        for vid, age in (("new", 3), ("old", 40)):
            cur.execute(f"INSERT INTO {s}.videos (video_id, channel_id, title, updated_at, "
                        "first_seen_at, texts_refreshed_at) VALUES (%s,'UCa','t',%s,%s,%s)",
                        (vid, ago(age), ago(age), ago(age)))
            cur.execute(f"INSERT INTO {s}.video_niches VALUES (%s,'n')", (vid,))
            cur.execute(f"INSERT INTO {s}.video_changes (video_id, changed_at, field, old_value, "
                        "new_value) VALUES (%s,%s,'title','a','b')", (vid, ago(age)))
        cur.execute(f"INSERT INTO {s}.video_stats_history VALUES ('new',%s,1,1,1,'t','th'),"
                    "('new',%s,1,1,1,'t','th')", (ago(29), ago(31)))
        cur.execute(f"INSERT INTO {s}.channel_stats_history VALUES ('UCa',%s,1,1,1),('UCa',%s,1,1,1)",
                    (ago(29), ago(31)))
        cur.execute(f"INSERT INTO {s}.gone_items VALUES ('video','x',%s,%s,1,%s)",
                    (ago(40), ago(40), ago(40)))
        cur.execute(f"INSERT INTO {s}.chart_snapshots (captured_at, region, source) VALUES "
                    "(%s,'US','mostPopular'), (%s,'US','mostPopular')", (ago(29), ago(31)))
    conn.commit()
    report = run(conn, load_settings({}).retention, schema=s, now=NOW, apply=True)

    def n(table):
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {s}.{table}")
            return cur.fetchone()[0]
    assert (n("videos"), n("video_niches"), n("video_changes")) == (1, 1, 1)
    assert n("video_stats_history") == 1 and n("channel_stats_history") == 1
    assert n("gone_items") == 0 and n("chart_snapshots") == 1
    assert report.total > 0


@pytest.mark.postgres
def test_report_mode_deletes_nothing_even_for_expired_rows(pg_schema):
    conn, s = pg_schema
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO {s}.videos (video_id, channel_id, title, updated_at, first_seen_at)"
                    " VALUES ('old','UCa','t',%s,%s)", (ago(90), ago(90)))
    conn.commit()
    report = run(conn, load_settings({}).retention, schema=s, now=NOW)
    assert report.applied is False and report.total >= 1
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {s}.videos")
        assert cur.fetchone()[0] == 1


# thumbnails ---------------------------------------------------------------------------------

@pytest.mark.postgres
def test_thumbnail_archive_and_image_vectors_are_purged_until_approved(pg_schema):
    conn, s = pg_schema
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO {s}.videos (video_id, channel_id, title, updated_at, first_seen_at,"
                    " texts_refreshed_at, thumb_embedding, thumb_embedded_at, thumbnail) "
                    "VALUES ('v','UCa','t',%s,%s,%s, '\\x01', %s, 'https://i.ytimg.com/vi/v/mq.jpg')",
                    (ago(1), ago(1), ago(1), ago(1)))
        cur.execute(f"INSERT INTO {s}.thumbnail_archive (video_id, captured_at, dhash, image) VALUES "
                    "('v',%s,'h','\\x02')", (ago(1),))          # fresh: still purged
    conn.commit()
    report = run(conn, load_settings({}).retention, schema=s, now=NOW, apply=True)
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {s}.thumbnail_archive")
        assert cur.fetchone()[0] == 0
        cur.execute(f"SELECT thumb_embedding IS NULL, thumb_embedded_at IS NULL, thumbnail "
                    f"FROM {s}.videos")
        # the vector goes; the URL the API returned stays (it is API data, not an image)
        assert cur.fetchone() == (True, True, "https://i.ytimg.com/vi/v/mq.jpg")
    assert report.affected["thumbnails_unapproved.thumbnail_archive"] == 1
    assert report.affected["thumbnails_unapproved.videos.image_vectors"] == 1


@pytest.mark.postgres
def test_after_approval_thumbnails_follow_the_text_window(pg_schema):
    conn, s = pg_schema
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO {s}.videos (video_id, channel_id, title, updated_at, first_seen_at,"
                    " texts_refreshed_at) VALUES ('v','UCa','t',%s,%s,%s)", (ago(1), ago(1), ago(1)))
        cur.execute(f"INSERT INTO {s}.thumbnail_archive (video_id, captured_at, dhash, image) VALUES "
                    "('v',%s,'a','\\x01'),('v',%s,'b','\\x02')", (ago(29), ago(31)))
    conn.commit()
    approved = load_settings({"VT_THUMBNAILS_APPROVED": "true"}).retention
    run(conn, approved, schema=s, now=NOW, apply=True)
    with conn.cursor() as cur:
        cur.execute(f"SELECT dhash FROM {s}.thumbnail_archive")
        assert [r[0] for r in cur.fetchall()] == ["a"]


def test_thumbnails_are_not_approved_by_default():
    assert load_settings({}).retention.thumbnails_approved is False
    assert THUMBNAIL_TABLES == ("thumbnail_archive",)


# the worker and API paths that download thumbnails ------------------------------------------

def test_thumbnail_downloads_are_reachable_only_from_two_guarded_steps():
    callers = {}
    for path in UPSTREAM_BACKEND.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "fetch_thumbnail" in text and path.name != "thumbnails.py":
            callers[path.name] = text
    assert set(callers) == {"packaging.py", "thumbnail_search.py"}
    worker = src("application", "worker_cycle.py")
    assert re.search(r"if DO_THUMBS and _due\(\"thumbs\"[^\n]*:\n[^\n]*fingerprint_thumbnails", worker)
    assert re.search(r"if DO_THUMB_EMBED[^\n]*:\n(?:[^\n]*\n){0,3}[^\n]*embed_thumbnails", worker)
    assert 'WORKER_THUMBS", "1") not in ("0", "false", "no")' in worker
    assert 'WORKER_THUMB_EMBED", "0") not in ("0", "false", "no")' in worker


def test_ingestion_profile_turns_every_thumbnail_step_off():
    text = (ROOT / "deploy" / "compose.ingestion-profile.yml").read_text(encoding="utf-8")
    env = text.split("x-ingestion-env: &ingestion-env")[1].split("services:")[0]
    assert 'WORKER_THUMBS: "0"' in env and 'WORKER_THUMB_EMBED: "0"' in env
    assert 'LLM_PROVIDER: "none"' in env
    services = text.split("\nservices:\n")[1]
    for name in ("web", "worker", "mcp", "mcp-http"):
        assert f"  {name}:\n    environment: *ingestion-env" in services


def test_ingestion_profile_does_not_touch_the_database_or_the_local_postgres_service():
    text = (ROOT / "deploy" / "compose.ingestion-profile.yml").read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "POSTGRES" not in code and "DATABASE" not in code and "depends_on" not in code


# transcripts --------------------------------------------------------------------------------

@pytest.mark.postgres
def test_transcripts_are_deleted_every_run_whatever_their_age(pg_schema):
    conn, s = pg_schema
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO {s}.videos (video_id, channel_id, title, updated_at, first_seen_at,"
                    " texts_refreshed_at) VALUES ('v','UCa','t',%s,%s,%s)", (ago(1), ago(1), ago(1)))
        cur.execute(f"INSERT INTO {s}.transcripts (video_id, language, text, created_at) "
                    "VALUES ('v','en','hello',%s)", (ago(0),))
    conn.commit()
    report = run(conn, load_settings({}).retention, schema=s, now=NOW, apply=True)
    with conn.cursor() as cur:
        for table in TRANSCRIPT_TABLES:
            cur.execute(f"SELECT count(*) FROM {s}.{table}")
            assert cur.fetchone()[0] == 0, table
    assert report.affected["transcripts_unapproved.transcripts"] == 1


# failures are visible, and never half-applied -------------------------------------------------

@pytest.mark.postgres
def test_a_failing_run_deletes_nothing_and_raises(pg_schema, monkeypatch):
    from viraltrack.retention import job
    conn, s = pg_schema
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO {s}.videos (video_id, channel_id, title, updated_at, first_seen_at)"
                    " VALUES ('old','UCa','t',%s,%s)", (ago(90), ago(90)))
        cur.execute(f"INSERT INTO {s}.gone_items VALUES ('video','x',%s,%s,1,%s)",
                    (ago(40), ago(40), ago(40)))
    conn.commit()
    original = job._delete_items
    calls = []

    def boom(*a, **k):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("simulated failure part-way")
        return original(*a, **k)
    monkeypatch.setattr(job, "_delete_items", boom)
    with pytest.raises(RuntimeError, match="part-way"):
        run(conn, load_settings({}).retention, schema=s, now=NOW, apply=True)
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {s}.videos")
        assert cur.fetchone()[0] == 1                      # the first step's deletes were rolled back


def test_the_deployed_retention_service_retries_failures_and_depends_on_web():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert '"viraltrack.retention", "--apply", "--loop"' in compose        # schedule + retry live in code
    assert "restart: unless-stopped" in compose
    assert "condition: service_healthy" in compose


@pytest.mark.postgres
def test_cli_failure_is_a_nonzero_exit_with_a_message_on_stderr(pg_schema, monkeypatch, capsys):
    import os

    from viraltrack.retention.__main__ import main
    _, s = pg_schema
    monkeypatch.setenv("DATABASE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", os.environ["VT_TEST_DATABASE_URL"])
    monkeypatch.setenv("DATABASE_SCHEMA", "does_not_exist")
    assert main(["--apply"]) == 3
    assert "no niche-finder tables" in capsys.readouterr().err
    monkeypatch.setenv("DATABASE_SCHEMA", s)
    assert main(["--apply"]) == 0
    assert '"applied": true' in capsys.readouterr().out
