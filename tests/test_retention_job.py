"""Retention job against the real upstream schema (needs VT_TEST_DATABASE_URL)."""
from datetime import datetime, timedelta, timezone

import pytest

from viraltrack.config import load_settings
from viraltrack.retention import run
from viraltrack.retention.job import SchemaNotFound

pytestmark = pytest.mark.postgres

NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def ago(days: float) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def seed(conn):
    with conn.cursor() as cur:
        for vid, refreshed in (("fresh", 2), ("stale", 40), ("gone", 1)):
            cur.execute("INSERT INTO videos (video_id, channel_id, title, view_count, updated_at, "
                        "first_seen_at, texts_refreshed_at) VALUES (%s,'UCa',%s,100,%s,%s,%s)",
                        (vid, f"title {vid}", ago(refreshed), ago(refreshed), ago(refreshed)))
            cur.execute("INSERT INTO video_niches VALUES (%s, 'cooking')", (vid,))
        cur.execute("INSERT INTO videos (video_id, channel_id, title, updated_at) "
                    "VALUES ('noage', 'UCa', 'x', 'not-a-date')")
        for days in (1, 45, 2000):
            cur.execute("INSERT INTO video_stats_history VALUES ('fresh', %s, 10, 1, 1, 't', 'th')",
                        (ago(days),))
            cur.execute("INSERT INTO channel_stats_history VALUES ('UCa', %s, 5, 5, 5)", (ago(days),))
        cur.execute("INSERT INTO channels (channel_id, title, updated_at) VALUES "
                    "('UCa', 'A', %s), ('UCold', 'Old', %s)", (ago(1), ago(60)))
        cur.execute("INSERT INTO gone_items VALUES ('video', 'gone', %s, %s, 3, %s)",
                    (ago(3), ago(1), ago(1)))
        cur.execute("INSERT INTO chart_snapshots (captured_at, region, source) VALUES "
                    "(%s, 'US', 'mostPopular') RETURNING snapshot_id", (ago(40),))
        snap = cur.fetchone()[0]
        cur.execute("INSERT INTO chart_entries VALUES (%s, 'fresh', 1, 10)", (snap,))
        cur.execute("INSERT INTO events (kind, ref_id, payload, created_at) VALUES "
                    "('outlier', 'fresh', '{}', %s), ('outlier', 'fresh', '{}', %s)",
                    (ago(1), ago(31)))
        cur.execute("INSERT INTO saved_items (kind, ref_id, folder, note, payload, created_at) "
                    "VALUES ('video', 'stale', 'default', 'mine', '{\"views\": 1}', %s)", (ago(90),))
        cur.execute("INSERT INTO tracked_channels (channel_id, added_at) VALUES ('UCold', %s)",
                    (ago(400),))
        cur.execute("INSERT INTO niches (slug, query, created_at) VALUES ('cooking', 'q', %s)",
                    (ago(400),))
    conn.commit()


def count(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]


def settings(**env):
    return load_settings({k: str(v) for k, v in env.items()}).retention


def test_report_mode_changes_nothing(pg_schema):
    conn, schema = pg_schema
    seed(conn)
    report = run(conn, settings(), schema=schema, now=NOW)
    assert report.applied is False and report.total > 0
    assert count(conn, f"SELECT count(*) FROM {schema}.videos") == 4
    assert count(conn, f"SELECT count(*) FROM {schema}.video_stats_history") == 3


def test_default_policy_enforces_30_days(pg_schema):
    conn, schema = pg_schema
    seed(conn)
    report = run(conn, settings(), schema=schema, now=NOW, apply=True)
    s = schema
    assert sorted(r[0] for r in rows(conn, f"SELECT video_id FROM {s}.videos")) == ["fresh", "noage"]
    assert report.unknown_age["videos"] == 1          # unparseable timestamp: left alone, reported
    assert count(conn, f"SELECT count(*) FROM {s}.video_niches") == 1
    assert count(conn, f"SELECT count(*) FROM {s}.video_stats_history") == 1
    assert count(conn, f"SELECT count(*) FROM {s}.channel_stats_history") == 1
    assert [r[0] for r in rows(conn, f"SELECT channel_id FROM {s}.channels")] == ["UCa"]
    assert count(conn, f"SELECT count(*) FROM {s}.chart_snapshots") == 0
    assert count(conn, f"SELECT count(*) FROM {s}.chart_entries") == 0
    assert count(conn, f"SELECT count(*) FROM {s}.events") == 1
    assert report.affected["gone_video.videos"] == 1


def test_user_data_survives(pg_schema):
    conn, schema = pg_schema
    seed(conn)
    run(conn, settings(), schema=schema, now=NOW, apply=True)
    assert rows(conn, f"SELECT note, payload FROM {schema}.saved_items") == [("mine", None)]
    assert count(conn, f"SELECT count(*) FROM {schema}.tracked_channels") == 1
    assert count(conn, f"SELECT count(*) FROM {schema}.niches") == 1


def test_amendment_keeps_stats_but_not_text(pg_schema):
    conn, schema = pg_schema
    seed(conn)
    run(conn, settings(VT_YOUTUBE_ANALYTICS_AMENDMENT_ACCEPTED="true"), schema=schema,
        now=NOW, apply=True)
    hist = rows(conn, f"SELECT captured_at, title, thumbnail FROM {schema}.video_stats_history "
                      "ORDER BY captured_at DESC")
    assert len(hist) == 2                                  # 2000-day row exceeds 36 months
    assert hist[0][1:] == ("t", "th")                      # 1 day old: title kept
    assert hist[1][1:] == (None, None)                     # 45 days old: counts kept, text stripped
    assert count(conn, f"SELECT count(*) FROM {schema}.channel_stats_history") == 2
    # titles in the videos table still follow the 30-day rule
    assert count(conn, f"SELECT count(*) FROM {schema}.videos WHERE video_id = 'stale'") == 0


def test_rejects_bad_schema_name(pg_schema):
    conn, _ = pg_schema
    with pytest.raises(ValueError):
        run(conn, settings(), schema="public; DROP TABLE videos", now=NOW)


def test_missing_foundation_schema_fails_closed(pg_schema):
    conn, _ = pg_schema
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS vt_empty_schema")
    conn.commit()
    try:
        with pytest.raises(SchemaNotFound):
            run(conn, settings(), schema="vt_empty_schema", now=NOW, apply=True)
    finally:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA vt_empty_schema")
        conn.commit()


def rows(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def test_phase_1_1_decisions(pg_schema):
    """own_* unverified 30 d, drafts.review, derived meta, transcripts with their video."""
    conn, s = pg_schema
    seed(conn)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO own_channels (user_id, channel_id, connected_at, last_synced_at) "
                    "VALUES (1, 'UCok', %s, %s), (1, 'UCdead', %s, %s), (1, 'UCnever', %s, NULL)",
                    (ago(90), ago(1), ago(90), ago(40), ago(35)))
        for ch in ("UCok", "UCdead"):
            cur.execute("INSERT INTO own_video_metrics (user_id, channel_id, video_id, window_name) "
                        "VALUES (1, %s, %s, '28d')", (ch, f"v_{ch}"))
            cur.execute("INSERT INTO own_channel_daily (user_id, channel_id, day, content_type) "
                        "VALUES (1, %s, '2026-10-01', 'short')", (ch,))
        cur.execute("INSERT INTO drafts (title, review, created_at) VALUES "
                    "('old', '{\"n\": 1}', %s), ('new', '{\"n\": 2}', %s)", (ago(45), ago(2)))
        cur.execute("INSERT INTO meta VALUES ('maturity_curve', %s), ('maturity_curve_check', %s), "
                    "('yt_units_2026-01-01', '500')",
                    ('{"calibratedAt": "%s", "curve": {}}' % ago(40),
                     '{"checkedAt": "%s"}' % ago(1)))
        cur.execute("INSERT INTO transcripts (video_id, text) VALUES ('stale', 't'), ('fresh', 't')")
    conn.commit()
    run(conn, settings(), schema=s, now=NOW, apply=True)
    assert [r[0] for r in rows(conn, f"SELECT channel_id FROM {s}.own_channels")] == ["UCok"]
    assert [r[0] for r in rows(conn, f"SELECT channel_id FROM {s}.own_video_metrics")] == ["UCok"]
    assert [r[0] for r in rows(conn, f"SELECT channel_id FROM {s}.own_channel_daily")] == ["UCok"]
    assert sorted(rows(conn, f"SELECT title, review FROM {s}.drafts")) == [
        ("new", '{"n": 2}'), ("old", None)]
    assert sorted(r[0] for r in rows(conn, f"SELECT key FROM {s}.meta")) == [
        "maturity_curve_check", "yt_units_2026-01-01"]
    assert [r[0] for r in rows(conn, f"SELECT video_id FROM {s}.transcripts")] == ["fresh"]
