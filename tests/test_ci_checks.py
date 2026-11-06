"""Negative controls for the `discovery-offline` CI gates (offline: no network, no database, no credentials).

Each control feeds a deliberately wrong input to the real gate code, or runs the real text of a workflow step
under bash with a stub in place of the command that would fail, and requires a non-zero exit status. A
matching positive control requires success, so a gate that always fails cannot pass these tests.
"""

import ast
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from tests.support import ci_checks as cc

ROOT = Path(__file__).resolve().parent.parent
CHECKS = ROOT / "tests" / "support" / "ci_checks.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(BASH is None, reason="bash not available")


def run(*args, env=None, cwd=None):
    return subprocess.run(
        [sys.executable, str(CHECKS), *args], capture_output=True, text=True, timeout=60, env=env, cwd=cwd
    )


# ---- building JUnit reports ----


def junit(xfails=None, skips=0, failures=0, errors=0, drop_from=None):
    """A JUnit report shaped like the job's: each file at its minimum, the nine known xfails, no more."""
    xfails = cc.EXPECTED_XFAILS if xfails is None else xfails
    cases = []
    for rel, minimum in cc.EXPECTED_MINIMUM.items():
        classname = rel[:-3].replace("/", ".")
        mine = [x.split("::")[1] for x in xfails if x.startswith(classname + "::")]
        plain = minimum - len([x for x in cc.EXPECTED_XFAILS if x.startswith(classname + "::")])
        if drop_from == rel:
            plain -= 1
        cases += [f'<testcase classname="{classname}" name="test_plain_{i}"/>' for i in range(plain)]
        cases += [
            f'<testcase classname="{classname}" name="{escape(n)}">'
            f'<skipped type="pytest.xfail" message="reason"/></testcase>'
            for n in mine
        ]
    first = "tests.test_collect_period"
    cases += [
        f'<testcase classname="{first}" name="test_skip_{i}"><skipped type="pytest.skip" message="s"/>'
        f"</testcase>"
        for i in range(skips)
    ]
    cases += [
        f'<testcase classname="{first}" name="test_fail_{i}"><failure message="boom"/></testcase>'
        for i in range(failures)
    ]
    cases += [
        f'<testcase classname="{first}" name="test_err_{i}"><error message="boom"/></testcase>'
        for i in range(errors)
    ]
    return (
        '<?xml version="1.0"?><testsuites><testsuite name="pytest">'
        + "".join(cases)
        + "</testsuite></testsuites>"
    )


def write(tmp_path, text, name="report.xml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def gate(tmp_path, report_path):
    summary = tmp_path / "summary.md"
    done = run("gate", str(report_path), str(summary))
    return done, summary


# ---- the report gate ----


def test_a_valid_report_passes_and_writes_its_summary(tmp_path):
    done, summary = gate(tmp_path, write(tmp_path, junit()))
    assert done.returncode == 0, done.stdout
    assert cc.SUMMARY_HEADER in summary.read_text(encoding="utf-8")
    assert "PROBLEM" not in done.stdout and "xfailed: 9" in done.stdout


def test_a_missing_report_fails_and_still_writes_a_summary(tmp_path):
    done, summary = gate(tmp_path, tmp_path / "does-not-exist.xml")
    assert done.returncode == 1 and "PROBLEM" in done.stdout
    assert "PROBLEM" in summary.read_text(encoding="utf-8")


def test_an_empty_report_fails(tmp_path):
    done, _ = gate(tmp_path, write(tmp_path, ""))
    assert done.returncode == 1 and "empty" in done.stdout


def test_a_malformed_report_fails(tmp_path):
    done, _ = gate(tmp_path, write(tmp_path, "<testsuite><testcase"))
    assert done.returncode == 1 and "unreadable" in done.stdout


def test_a_truncated_report_fails(tmp_path):
    whole = junit()
    done, _ = gate(tmp_path, write(tmp_path, whole[: len(whole) // 2]))
    assert done.returncode == 1 and "unreadable" in done.stdout


def test_a_report_without_tests_fails(tmp_path):
    done, _ = gate(tmp_path, write(tmp_path, "<testsuites><testsuite></testsuite></testsuites>"))
    assert done.returncode == 1 and "COLLECTION" in done.stdout


def test_any_other_skip_fails(tmp_path):
    done, _ = gate(tmp_path, write(tmp_path, junit(skips=1)))
    assert done.returncode == 1 and "SKIPPED" in done.stdout


@pytest.mark.parametrize("kwargs,word", [({"failures": 1}, "FAILED"), ({"errors": 1}, "ERROR")])
def test_failures_and_errors_fail(tmp_path, kwargs, word):
    done, _ = gate(tmp_path, write(tmp_path, junit(**kwargs)))
    assert done.returncode == 1 and word in done.stdout


def test_a_file_with_fewer_tests_than_recorded_fails(tmp_path):
    done, _ = gate(tmp_path, write(tmp_path, junit(drop_from="tests/test_collect_period.py")))
    assert done.returncode == 1 and "COLLECTION tests/test_collect_period.py" in done.stdout


def test_fewer_than_nine_xfails_fails(tmp_path):
    done, _ = gate(tmp_path, write(tmp_path, junit(xfails=set(sorted(cc.EXPECTED_XFAILS)[:8]))))
    assert done.returncode == 1 and "XFAIL" in done.stdout


def test_more_than_nine_xfails_fails(tmp_path):
    extra = set(cc.EXPECTED_XFAILS) | {"tests.test_collect_period::test_something_new_that_is_xfailed"}
    done, _ = gate(tmp_path, write(tmp_path, junit(xfails=extra)))
    assert done.returncode == 1 and "XFAIL" in done.stdout


def test_nine_xfails_with_a_swapped_name_fails(tmp_path):
    swapped = (set(cc.EXPECTED_XFAILS) - {sorted(cc.EXPECTED_XFAILS)[0]}) | {
        "tests.test_discovery_d1_adapter::test_a_different_test"
    }
    done, _ = gate(tmp_path, write(tmp_path, junit(xfails=swapped)))
    assert done.returncode == 1 and "XFAIL" in done.stdout


# ---- the summary ----


def test_require_summary_controls(tmp_path):
    assert run("require-summary", str(tmp_path / "absent.md")).returncode == 1
    assert run("require-summary", str(write(tmp_path, "", "empty.md"))).returncode == 1
    assert run("require-summary", str(write(tmp_path, "something else\n", "wrong.md"))).returncode == 1
    good = write(tmp_path, cc.SUMMARY_HEADER + "\n- collected: 1\n", "good.md")
    assert run("require-summary", str(good)).returncode == 0


def test_the_gate_fails_when_the_summary_cannot_be_written(tmp_path):
    report = write(tmp_path, junit())
    done = run("gate", str(report), str(tmp_path))  # a directory is not a writable file
    assert done.returncode == 1 and "could not be written" in done.stdout


# ---- the workflow: pipefail, and the real step text under bash ----


def job_text() -> str:
    text = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")
    return text[text.index("  discovery-offline:") :]


def run_blocks():
    """(step name, command lines) for every `run: |` block of the job, in order; plus single-line runs."""
    lines = job_text().split("\n")
    blocks, name = [], None
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"\s+- name: (.*)", line)
        if m:
            name = m.group(1)
        if re.match(r"\s+run: \|\s*$", line):
            indent = len(line) - len(line.lstrip()) + 2
            body = []
            i += 1
            while i < len(lines) and (
                not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) >= indent
            ):
                body.append(lines[i][indent:] if lines[i].strip() else "")
                i += 1
            blocks.append((name, "\n".join(body).rstrip() + "\n"))
            continue
        single = re.match(r"\s+run: (?!\|)(.+)", line)
        if single:
            blocks.append((name, single.group(1) + "\n"))
        i += 1
    return blocks


def step(prefix: str) -> str:
    for name, body in run_blocks():
        if name and name.startswith(prefix):
            return body
    raise AssertionError(f"no step starting with {prefix!r}")


def test_the_job_sets_bash_as_the_default_shell_and_every_multiline_step_enables_pipefail():
    assert re.search(r"defaults:\n\s+run:\n\s+shell: bash", job_text())
    blocks = run_blocks()
    assert len(blocks) >= 8
    for name, body in blocks:
        if body.count("\n") > 1:
            first = next(line for line in body.split("\n") if line.strip())
            assert first == "set -o pipefail", f"step {name!r} does not start with set -o pipefail"
        else:
            assert "|" not in body, f"single-line step {name!r} pipes a command without pipefail"


def test_the_old_report_step_pattern_is_gone():
    text = job_text()
    assert "| tee summary.md" not in text and '! grep -q "PROBLEM"' not in text
    assert "ci_checks.py gate" in text and "ci_checks.py require-summary" in text


@needs_bash
def test_a_failing_command_piped_through_tee_exits_nonzero_only_with_pipefail():
    plain = subprocess.run([BASH, "-e", "-c", "false | tee /dev/null"], capture_output=True)
    strict = subprocess.run([BASH, "-e", "-c", "set -o pipefail; false | tee /dev/null"], capture_output=True)
    assert plain.returncode == 0, "the old behaviour: tee hides the failure"
    assert strict.returncode != 0, "with pipefail the failure is visible"


def posix(path) -> str:
    return Path(path).as_posix()


def stub(tmp_path, name, body):
    path = tmp_path / name
    path.write_text("#!/bin/bash\n" + body + "\n", encoding="utf-8", newline="\n")
    return path


def run_step(tmp_path, prefix, fake_sudo_body=None, replacements=None, env_extra=None):
    """Run the REAL text of a workflow step under `bash -e`, with stubs for sudo and curl."""
    body = step(prefix)
    for old, new in (replacements or {}).items():
        body = body.replace(old, new)
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    if fake_sudo_body is not None:
        stub(bindir, "sudo", fake_sudo_body)
    stub(bindir, "curl", "echo 200")
    script = tmp_path / "step.sh"
    script.write_text(body, encoding="utf-8", newline="\n")
    env = dict(
        os.environ,
        PATH=posix(bindir) + os.pathsep + os.environ["PATH"],
        GITHUB_STEP_SUMMARY=posix(tmp_path / "gh_summary.md"),
        VT_UID="1002",
        VT_GID="1002",
    )
    env.update(env_extra or {})
    return subprocess.run(
        [BASH, "-e", posix(script)], capture_output=True, text=True, cwd=tmp_path, env=env, timeout=60
    )


@needs_bash
def test_the_isolation_step_fails_when_the_check_fails_and_passes_when_it_passes(tmp_path):
    # The stub validates the real step: `sudo -u vtoffline <command>`; anything else is rejected.
    check = "ci_checks.py isolation localhost 5432 1002 1002"
    bad_body = "".join(
        [
            'if [ "$1" != "-u" ] || [ "$2" != "vtoffline" ]; then ',
            'echo "unexpected sudo arguments: $*" >&2; exit 97; fi' + "; ",
            "shift 2; ",
            'case "$*" in ',
            'id) echo "uid=1002(vtoffline)"; exit 0;; ',
            f'*"{check}") echo "ERROR: external connection succeeded"; exit 1;; ',
            '*) echo "unexpected command: $*" >&2; exit 98;; ',
            "esac",
        ]
    )
    good_body = bad_body.replace(
        'echo "ERROR: external connection succeeded"; exit 1', 'echo "ISOLATION OK"; exit 0'
    )
    assert "tests/support/ci_checks.py isolation" in step("Verify the isolation")
    (tmp_path / "bad").mkdir()
    (tmp_path / "good").mkdir()
    bad = run_step(tmp_path / "bad", "Verify the isolation", bad_body)
    good = run_step(tmp_path / "good", "Verify the isolation", good_body)
    # fail for the INTENDED reason: the check's own message reached the log, not a stub or sudo problem
    assert bad.returncode != 0, bad.stdout + bad.stderr
    assert "ERROR: external connection succeeded" in bad.stdout, bad.stdout + bad.stderr
    assert "unexpected" not in bad.stderr and "not found" not in bad.stderr, bad.stderr
    assert good.returncode == 0, good.stdout + good.stderr
    assert "ISOLATION OK" in good.stdout, good.stdout


def gate_step(tmp_path, report_text=None, python_stub=None):
    """Run the real report-gate step. `report_text` is written where the step reads it."""
    report = tmp_path / "report.xml"
    if report_text is not None:
        report.write_text(report_text, encoding="utf-8")
    py = (
        f'"{posix(sys.executable)}" "{posix(CHECKS)}"'
        if python_stub is None
        else f'bash "{posix(python_stub)}"'
    )
    return run_step(
        tmp_path,
        "Enforce collection",
        replacements={
            "/tmp/vt-venv/bin/python tests/support/ci_checks.py": py,
            "/tmp/vt-offline/report.xml": f'"{posix(report)}"',
        },
    )


@needs_bash
@pytest.mark.parametrize("case", ["missing", "empty", "malformed", "truncated", "no-tests"])
def test_the_report_step_fails_for_a_bad_report(tmp_path, case):
    text = {
        "missing": None,
        "empty": "",
        "malformed": "<testsuite><testcase",
        "truncated": junit()[: len(junit()) // 2],
        "no-tests": "<testsuites><testsuite></testsuite></testsuites>",
    }[case]
    done = gate_step(tmp_path, text)
    assert done.returncode != 0, done.stdout + done.stderr


@needs_bash
def test_the_report_step_passes_for_a_valid_report(tmp_path):
    done = gate_step(tmp_path, junit())
    assert done.returncode == 0, done.stdout + done.stderr
    assert cc.SUMMARY_HEADER in (tmp_path / "gh_summary.md").read_text(encoding="utf-8")


@needs_bash
def test_the_report_step_fails_when_no_summary_is_produced(tmp_path):
    silent = stub(tmp_path, "silent_python.sh", "exit 0")  # a 'checker' that succeeds and writes nothing
    done = gate_step(tmp_path, junit(), python_stub=silent)
    assert done.returncode != 0
    assert "no report summary" in done.stdout.lower() or "no report summary" in done.stderr.lower()


# ---- process identity ----


def test_the_wrong_uid_is_a_problem():
    me = cc.current_identity()
    assert cc.identity_problems(99999, None)
    if me["uid"] is not None:
        assert any("not a number" in p for p in cc.identity_problems("abc", None))
        assert cc.identity_problems(me["uid"] + 1, None)
        assert cc.identity_problems(me["uid"], (me["gid"] or 0) + 1)


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="needs POSIX uid/gid")
def test_the_right_uid_and_gid_are_no_problem():
    me = cc.current_identity()
    assert cc.identity_problems(me["uid"], me["gid"]) == []
    assert cc.identity_problems(str(me["uid"])) == []


@pytest.mark.skipif(hasattr(os, "getuid"), reason="only meaningful where the OS has no uid")
def test_an_os_without_uids_cannot_pass_an_identity_check():
    assert cc.identity_problems(1000, 1000)


def test_a_child_with_another_identity_is_a_problem():
    assert cc.child_identity_problems({"uid": 0, "gid": 1002}, 1002, 1002)
    assert cc.child_identity_problems({"gid": 1002}, 1002, 1002)  # unknown is a problem
    assert cc.child_identity_problems({"uid": 1002, "gid": 1002}, 1002, 1002) == []
    assert cc.child_identity_problems({"uid": 5}, None, None) == []  # no expectation, no check


def test_pytest_refuses_to_start_as_the_wrong_user():
    env = dict(
        os.environ, VT_TEST_EXPECT_UID="99999", VT_TEST_EXPECT_GID="99999", PYTHONDONTWRITEBYTECODE="1"
    )
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_domain.py", "-p", "no:cacheprovider", "-q"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
        timeout=120,
    )
    assert done.returncode == 3, done.stdout + done.stderr
    assert "wrong process identity" in done.stdout + done.stderr


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="needs POSIX uid/gid")
def test_pytest_starts_as_the_right_user_and_shows_the_identity():
    me = cc.current_identity()
    env = dict(
        os.environ,
        VT_TEST_EXPECT_UID=str(me["uid"]),
        VT_TEST_EXPECT_GID=str(me["gid"]),
        PYTHONDONTWRITEBYTECODE="1",
    )
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_domain.py", "-p", "no:cacheprovider", "-q"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
        timeout=120,
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_pytest_shows_the_process_identity_in_its_header():
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_domain.py",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "--co",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=120,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
    )
    assert "process identity:" in done.stdout


# ---- the network isolation check itself (local sockets only; no external address is contacted) ----


def listening():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(5)
    return sock, sock.getsockname()[1]


def closed_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_the_isolation_check_fails_when_an_external_host_is_reachable(monkeypatch):
    server, port = listening()
    monkeypatch.setattr(cc, "EXTERNAL_TARGETS", [("127.0.0.1", port)])  # stands in for a reachable host
    monkeypatch.setattr(cc, "EXTERNAL_NAME", None)
    try:
        assert cc.isolation("127.0.0.1", port) == 1
    finally:
        server.close()


def test_the_isolation_check_fails_when_the_database_is_unreachable(monkeypatch):
    monkeypatch.setattr(cc, "EXTERNAL_TARGETS", [("127.0.0.1", closed_port())])
    monkeypatch.setattr(cc, "EXTERNAL_NAME", None)
    assert cc.isolation("127.0.0.1", closed_port()) == 1


def test_the_isolation_check_passes_when_external_is_blocked_and_the_database_answers(monkeypatch):
    server, port = listening()
    monkeypatch.setattr(
        cc, "EXTERNAL_TARGETS", [("127.0.0.1", closed_port())]
    )  # stands in for a blocked host
    monkeypatch.setattr(cc, "EXTERNAL_NAME", None)
    try:
        assert cc.isolation("127.0.0.1", port) == 0
    finally:
        server.close()


def test_the_isolation_check_fails_for_the_wrong_user(monkeypatch):
    server, port = listening()
    monkeypatch.setattr(cc, "EXTERNAL_TARGETS", [("127.0.0.1", closed_port())])
    monkeypatch.setattr(cc, "EXTERNAL_NAME", None)
    try:
        assert cc.isolation("127.0.0.1", port, 99999, 99999) == 1
    finally:
        server.close()


# ---- the expected counts match the real test files ----


def test_the_expected_xfails_are_exactly_the_strict_xfail_markers_in_the_sources():
    found = set()
    for module in ("tests.test_discovery_d1_adapter", "tests.test_discovery_d1_policy"):
        tree = ast.parse((ROOT / (module.replace(".", "/") + ".py")).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for deco in node.decorator_list:
                    text = ast.unparse(deco)
                    if "mark.xfail" in text:
                        assert "strict=True" in text, f"{node.name} is an xfail that is not strict"
                        found.add(f"{module}::{node.name}")
    assert found == set(cc.EXPECTED_XFAILS)


def test_the_expected_minimums_do_not_exceed_what_the_files_collect():
    files = list(cc.EXPECTED_MINIMUM)
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *files,
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=120,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
    )
    counts = {}
    for line in done.stdout.splitlines():
        if "::" in line:
            counts[line.split("::")[0]] = counts.get(line.split("::")[0], 0) + 1
    for rel, minimum in cc.EXPECTED_MINIMUM.items():
        assert counts.get(rel, 0) >= minimum, (rel, counts.get(rel, 0), minimum)
