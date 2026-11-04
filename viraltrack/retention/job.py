"""Applies the retention policy to the niche-finder Postgres database.

Every run happens in one transaction. Without `apply` the transaction is
rolled back, so a report run shows exactly what an apply run would delete.

Timestamps in niche-finder are ISO-8601 TEXT. A value that does not look like
an ISO date is treated as unknown age and left alone (counted in the report).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from viraltrack.config import RetentionSettings
from viraltrack.retention.policy import (
    AGE_RULES,
    CHANNEL_DEPENDENTS,
    DERIVED_META_KEYS,
    OWN_CHANNEL_DEPENDENTS,
    THUMBNAIL_TABLES,
    TRANSCRIPT_TABLES,
    VIDEO_DEPENDENTS,
    Window,
)

log = logging.getLogger(__name__)

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


class SchemaNotFound(RuntimeError):
    pass


def _ts(expr: str) -> str:
    """Cast an ISO TEXT column to timestamptz; NULL when it is not ISO-shaped."""
    return (f"(CASE WHEN {expr} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}' "
            f"THEN ({expr})::timestamptz END)")


@dataclass
class RetentionReport:
    applied: bool
    stats_cutoff: datetime
    text_cutoff: datetime
    affected: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    unknown_age: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.affected.values())


def cutoffs(settings: RetentionSettings, now: datetime) -> dict[Window, datetime]:
    return {Window.STATS: now - timedelta(days=settings.youtube_stats_days),
            Window.TEXT: now - timedelta(days=settings.youtube_text_days)}


def _columns(cur, table: str) -> set[str]:
    cur.execute("SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = %s", (table,))
    return {r[0] for r in cur.fetchall()}


def _delete_items(cur, report: RetentionReport, label: str, table: str, key: str,
                  dependents: tuple[str, ...], ids_sql: str, params: dict) -> None:
    cur.execute(f"CREATE TEMP TABLE _vt_ids ON COMMIT DROP AS {ids_sql}", params)
    cur.execute("SELECT count(*) FROM _vt_ids")
    if cur.fetchone()[0]:
        for dep in dependents:
            if key in _columns(cur, dep):
                cur.execute(f"DELETE FROM {dep} WHERE {key} IN (SELECT id FROM _vt_ids)")
                report.affected[f"{label}.{dep}"] = cur.rowcount
        cur.execute(f"DELETE FROM {table} WHERE {key} IN (SELECT id FROM _vt_ids)")
        report.affected[f"{label}.{table}"] = cur.rowcount
    cur.execute("DROP TABLE _vt_ids")


def run(conn, settings: RetentionSettings, schema: str = "public",
        now: datetime | None = None, apply: bool | None = None) -> RetentionReport:
    """Enforce retention on `conn` (a psycopg2 connection). Returns what changed."""
    if not _IDENT.match(schema):
        raise ValueError(f"invalid schema name {schema!r}")
    now = now or datetime.now(timezone.utc)
    apply = settings.apply if apply is None else apply
    cut = cutoffs(settings, now)
    params = {"stats": cut[Window.STATS], "text": cut[Window.TEXT]}
    report = RetentionReport(applied=apply, stats_cutoff=cut[Window.STATS],
                             text_cutoff=cut[Window.TEXT])

    with conn.cursor() as cur:
        cur.execute(f"SET LOCAL search_path TO {schema}")
        vcols, ccols = _columns(cur, "videos"), _columns(cur, "channels")
        if not vcols or not ccols:
            # Fail closed: a wrong schema name must not look like "nothing to delete".
            conn.rollback()
            raise SchemaNotFound(f"no niche-finder tables in schema {schema!r}")

        # 1. Items YouTube no longer returns (confirmed gone): delete their data.
        if _columns(cur, "gone_items"):
            for kind, table, key, deps, cols in (
                    ("video", "videos", "video_id", VIDEO_DEPENDENTS, vcols),
                    ("channel", "channels", "channel_id", CHANNEL_DEPENDENTS, ccols)):
                if cols:
                    _delete_items(cur, report, f"gone_{kind}", table, key, deps,
                                  "SELECT ref_id AS id FROM gone_items "
                                  f"WHERE kind = '{kind}' AND confirmed_at IS NOT NULL", params)

        # 2. Videos/channels not refreshed within the text window.
        if vcols:
            fresh = [c for c in ("texts_refreshed_at", "first_seen_at", "updated_at") if c in vcols]
            texts = f"COALESCE({', '.join(fresh)})"
            _delete_items(cur, report, "stale_video", "videos", "video_id", VIDEO_DEPENDENTS,
                          f"SELECT video_id AS id FROM videos WHERE {_ts(texts)} < %(text)s "
                          f"OR {_ts('updated_at')} < %(stats)s", params)
            cur.execute(f"SELECT count(*) FROM videos WHERE {_ts(texts)} IS NULL")
            report.unknown_age["videos"] = cur.fetchone()[0]
        if ccols:
            fresh = [c for c in ("texts_refreshed_at", "first_seen_at", "updated_at") if c in ccols]
            texts = f"COALESCE({', '.join(fresh)})"
            _delete_items(cur, report, "stale_channel", "channels", "channel_id",
                          CHANNEL_DEPENDENTS,
                          f"SELECT channel_id AS id FROM channels WHERE {_ts(texts)} < %(text)s",
                          params)
            cur.execute(f"SELECT count(*) FROM channels WHERE {_ts(texts)} IS NULL")
            report.unknown_age["channels"] = cur.fetchone()[0]

        # 3. Chart entries belong to snapshots; age them by the snapshot time.
        if _columns(cur, "chart_snapshots"):
            old = f"SELECT snapshot_id FROM chart_snapshots WHERE {_ts('captured_at')} < %(stats)s"
            cur.execute(f"DELETE FROM chart_entries WHERE snapshot_id IN ({old})", params)
            report.affected["chart_entries.rows"] = cur.rowcount
            cur.execute(f"DELETE FROM chart_snapshots WHERE snapshot_id IN ({old})", params)
            report.affected["chart_snapshots.rows"] = cur.rowcount

        # 3b. Transcripts are not approved for storage: remove all of them.
        if not settings.transcripts_approved:
            for table in TRANSCRIPT_TABLES:
                if _columns(cur, table):
                    cur.execute(f"DELETE FROM {table}")
                    report.affected[f"transcripts_unapproved.{table}"] = cur.rowcount

        # 3c. Thumbnail archiving is not approved: remove every stored image.
        if not settings.thumbnails_approved:
            for table in THUMBNAIL_TABLES:
                if _columns(cur, table):
                    cur.execute(f"DELETE FROM {table}")
                    report.affected[f"thumbnails_unapproved.{table}"] = cur.rowcount
            # Image vectors computed from downloaded thumbnails are derived from them.
            wanted = ("thumb_embedding", "thumb_embedding_v", "thumb_embedded_at")
            present = [c for c in wanted if c in vcols]
            if present:
                sets = ", ".join(f"{c} = NULL" for c in present)
                cur.execute(f"UPDATE videos SET {sets} WHERE " +
                            " OR ".join(f"{c} IS NOT NULL" for c in present))
                report.affected["thumbnails_unapproved.videos.image_vectors"] = cur.rowcount

        # 4. Own channels whose authorization was not re-verified within the text window.
        if {"user_id", "channel_id", "connected_at", "last_synced_at"} <= _columns(cur, "own_channels"):
            stale = (f"SELECT user_id, channel_id FROM own_channels "
                     f"WHERE {_ts('COALESCE(last_synced_at, connected_at)')} < %(text)s")
            for dep in OWN_CHANNEL_DEPENDENTS:
                cur.execute(f"DELETE FROM {dep} WHERE (user_id, channel_id) IN ({stale})", params)
                report.affected[f"own_unverified.{dep}"] = cur.rowcount
            cur.execute(f"DELETE FROM own_channels WHERE (user_id, channel_id) IN ({stale})", params)
            report.affected["own_unverified.own_channels"] = cur.rowcount
        else:
            report.skipped["own_unverified"] = "own_channels columns missing"

        # 5. Derived aggregates kept in meta (JSON values with their own timestamp).
        for key, field in DERIVED_META_KEYS.items():
            stamp = rf"(CASE WHEN value ~ '^\s*\{{' THEN (value::jsonb ->> '{field}') END)"
            cur.execute(f"DELETE FROM meta WHERE key = %(key)s AND {_ts(stamp)} < %(text)s",
                        {**params, "key": key})
            report.affected[f"meta.{key}"] = cur.rowcount

        # 6. Row-age rules.
        for rule in AGE_RULES:
            cols = _columns(cur, rule.table)
            needed = {rule.timestamp, *rule.strip}
            if not cols:
                report.skipped[rule.name] = "table missing"
                continue
            if not needed <= cols:
                report.skipped[rule.name] = f"columns missing: {sorted(needed - cols)}"
                continue
            if rule.covered_by_stats and cut[Window.TEXT] <= cut[Window.STATS]:
                report.affected[rule.name] = 0   # rows already deleted by the stats rule
                continue
            cond = f"{_ts(rule.timestamp)} < %({rule.window.value})s AND {rule.where}"
            if rule.strip:
                sets = ", ".join(f"{c} = NULL" for c in rule.strip)
                cur.execute(f"UPDATE {rule.table} SET {sets} WHERE {cond}", params)
            else:
                cur.execute(f"DELETE FROM {rule.table} WHERE {cond}", params)
            report.affected[rule.name] = cur.rowcount

    if apply:
        conn.commit()
    else:
        conn.rollback()
    log.info("retention %s: %d rows affected (stats cutoff %s, text cutoff %s)",
             "applied" if apply else "report", report.total,
             report.stats_cutoff.isoformat(), report.text_cutoff.isoformat())
    return report
