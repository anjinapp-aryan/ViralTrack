"""VT_RETENTION_INTERVAL_SECONDS and the retention loop (scheduling only: the cutoff is unchanged)."""
import pytest

from viraltrack.config import load_settings
from viraltrack.domain import ConfigError
from viraltrack.retention import __main__ as cli


def test_default_is_one_hour():
    assert load_settings({}).retention.interval_seconds == 3600
    assert load_settings({"VT_RETENTION_INTERVAL_SECONDS": ""}).retention.interval_seconds == 3600


def test_neon_override_of_six_hours():
    assert load_settings({"VT_RETENTION_INTERVAL_SECONDS": "21600"}).retention.interval_seconds == 21600


@pytest.mark.parametrize("bad", ["0", "59", "86401", "-5", "hourly", "1.5"])
def test_out_of_range_or_malformed_interval_is_refused(bad):
    with pytest.raises(ConfigError, match="VT_RETENTION_INTERVAL_SECONDS"):
        load_settings({"VT_RETENTION_INTERVAL_SECONDS": bad})


def test_the_interval_does_not_touch_the_cutoffs():
    a = load_settings({}).retention
    b = load_settings({"VT_RETENTION_INTERVAL_SECONDS": "21600"}).retention
    keep = lambda r: (r.youtube_text_days, r.youtube_stats_days, r.apply)  # noqa: E731
    assert keep(a) == keep(b) == (30, 30, False)


class Clock:
    def __init__(self):
        self.sleeps = []

    def __call__(self, seconds):
        self.sleeps.append(seconds)


def settings(interval="3600"):
    return load_settings({"VT_RETENTION_INTERVAL_SECONDS": interval, "DATABASE_URL": "postgresql://u:p@h/d"})


def script(monkeypatch, codes):
    calls = []
    it = iter(codes)

    def fake(st, apply):
        calls.append(apply)
        code = next(it)
        if isinstance(code, Exception):
            raise code
        return code
    monkeypatch.setattr(cli, "run_once", fake)
    return calls


def test_success_waits_the_configured_interval(monkeypatch):
    calls, clock = script(monkeypatch, [0, 0, 0]), Clock()
    cli.loop(settings("21600"), True, sleep=clock, max_runs=3)
    assert clock.sleeps == [21600, 21600]            # no sleep after the last counted run
    assert calls == [True, True, True]


def test_failure_retries_after_600_seconds_not_the_interval(monkeypatch):
    script(monkeypatch, [4, 3, 0, 0])
    clock = Clock()
    cli.loop(settings("21600"), True, sleep=clock, max_runs=4)
    assert clock.sleeps == [600, 600, 21600]


def test_retry_never_exceeds_a_short_interval(monkeypatch):
    script(monkeypatch, [4, 0])
    clock = Clock()
    cli.loop(settings("60"), True, sleep=clock, max_runs=2)
    assert clock.sleeps == [60]


def test_a_crash_is_logged_and_retried_not_fatal(monkeypatch):
    script(monkeypatch, [RuntimeError("boom"), 0])
    clock = Clock()
    code = cli.loop(settings(), True, sleep=clock, max_runs=2)
    assert clock.sleeps == [600] and code == 0


def test_loop_passes_report_only_through(monkeypatch):
    calls = script(monkeypatch, [0])
    cli.loop(settings(), False, sleep=Clock(), max_runs=1)
    assert calls == [False]


def test_loop_requires_a_database_url(monkeypatch, capsys):
    for k in ("DATABASE_URL", "VT_DATABASE_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(cli, "loop", lambda *a, **k: pytest.fail("must not start"))
    assert cli.main(["--loop"]) == 2
    assert "DATABASE_URL" in capsys.readouterr().err


def test_bad_interval_exits_2(monkeypatch, capsys):
    monkeypatch.setenv("VT_RETENTION_INTERVAL_SECONDS", "5")
    assert cli.main(["--loop"]) == 2
    assert "VT_RETENTION_INTERVAL_SECONDS" in capsys.readouterr().err
