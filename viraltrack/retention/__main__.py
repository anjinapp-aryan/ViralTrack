"""python -m viraltrack.retention [--apply]

Report (default) or enforce the retention policy on the niche-finder database
named by VT_DATABASE_URL / VT_DATABASE_SCHEMA. Run it daily; the docker-compose
`retention` service does that with --apply.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

import psycopg2

from viraltrack.config import load_settings
from viraltrack.domain import ConfigError
from viraltrack.retention.job import SchemaNotFound, run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m viraltrack.retention")
    parser.add_argument("--apply", action="store_true",
                        help="delete for real (default: report only, then roll back)")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    logging.basicConfig(level=settings.log_level,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not settings.database.url:
        print("config error: VT_DATABASE_URL is not set", file=sys.stderr)
        return 2
    conn = psycopg2.connect(settings.database.url)
    try:
        report = run(conn, settings.retention, schema=settings.database.schema,
                     apply=args.apply or settings.retention.apply)
    except SchemaNotFound as exc:
        print(f"retention error: {exc}", file=sys.stderr)
        return 3
    finally:
        conn.close()
    print(json.dumps({
        "applied": report.applied,
        "statsCutoff": report.stats_cutoff.isoformat(),
        "textCutoff": report.text_cutoff.isoformat(),
        "total": report.total,
        "affected": report.affected,
        "skipped": report.skipped,
        "unknownAge": report.unknown_age,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
