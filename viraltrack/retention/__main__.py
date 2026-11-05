"""python -m viraltrack.retention [--apply] [--loop]

Report (default) or enforce the retention policy on the niche-finder database
named by DATABASE_URL / DATABASE_SCHEMA (any PostgreSQL provider, see
docs/architecture/DATABASE_CONFIGURATION.md). The docker-compose `retention` service runs it
with --apply --loop, every VT_RETENTION_INTERVAL_SECONDS (default 3600). It uses exactly one connection.

Exit codes: 0 done, 2 configuration error, 3 wrong schema, 4 database unreachable.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from viraltrack.config import load_settings
from viraltrack.database import DatabaseUnavailable, connect, prepare_transaction
from viraltrack.domain import ConfigError
from viraltrack.retention.job import SchemaNotFound, run

RETRY_SECONDS = 600     # after a failed run, never wait for the whole interval


def run_once(settings, apply: bool) -> int:
    """One retention run. Prints the JSON report; returns the exit code (see module docstring)."""
    if not settings.database.url:
        print("config error: DATABASE_URL is not set", file=sys.stderr)
        return 2
    try:
        conn = connect(settings.database)
    except DatabaseUnavailable as exc:
        print(f"database error: {exc}", file=sys.stderr)
        return 4
    try:
        prepare_transaction(conn, settings.database)
        report = run(conn, settings.retention, schema=settings.database.schema,
                     apply=apply or settings.retention.apply)
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
    }, indent=2), flush=True)
    return 0


def loop(settings, apply: bool, *, sleep=time.sleep, max_runs: int | None = None) -> int:
    """Run forever: wait `interval_seconds` after a successful run, `RETRY_SECONDS` (capped at the
    interval) after a failed one. The cutoff is unchanged; only how often it is applied differs.
    `sleep` and `max_runs` exist for tests."""
    interval = settings.retention.interval_seconds
    retry = min(RETRY_SECONDS, interval)
    runs = 0
    while max_runs is None or runs < max_runs:
        try:
            code = run_once(settings, apply)
        except Exception:                       # noqa: BLE001 - a bug must not stop the schedule
            logging.getLogger(__name__).exception("retention run crashed")
            code = 1
        runs += 1
        if max_runs is not None and runs >= max_runs:
            return code
        sleep(interval if code == 0 else retry)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m viraltrack.retention")
    parser.add_argument("--apply", action="store_true",
                        help="delete for real (default: report only, then roll back)")
    parser.add_argument("--loop", action="store_true",
                        help="repeat every VT_RETENTION_INTERVAL_SECONDS (default 3600); "
                             "a failed run is retried after 600 s")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    logging.basicConfig(level=settings.log_level,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if args.loop:
        if not settings.database.url:
            print("config error: DATABASE_URL is not set", file=sys.stderr)
            return 2
        return loop(settings, args.apply)
    return run_once(settings, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
