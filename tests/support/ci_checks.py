"""Checks run by the `discovery-offline` CI job (standard library only). Not a test module.

    python tests/support/ci_checks.py isolation <db-host> <db-port> [<expected-uid> <expected-gid>]
    python tests/support/ci_checks.py gate <junit.xml> <summary.md>
    python tests/support/ci_checks.py require-summary <summary.md>
    python tests/support/ci_checks.py report <junit.xml>              (prints; `gate` is what the job uses)

`isolation` proves, after the firewall rule is installed, that an external connection FAILS, that the local
database service is still reachable and, when given, that this process runs as the expected restricted user.
`gate` enforces what the job promises and ALWAYS writes a summary file: every expected test file was
collected (at least its recorded number of tests), nothing was skipped (a skip would mean the upstream-backed
tests did not run), nothing failed, exactly the known strict xfails (EXPECTED_XFAILS) are xfailed, and
the report itself is present, well formed and non-empty. A missing, truncated or malformed report is a
PROBLEM, never a pass.
`require-summary` fails when the summary file is missing, empty or lacks its header.

Every command returns a non-zero exit status on any problem and reports it on stdout with the word PROBLEM
or ERROR.
"""

import os
import socket
import sys
import xml.etree.ElementTree as ET

SUMMARY_HEADER = "### Offline discovery tests (real upstream code, synthetic data, no network)"

# Minimum number of tests per file at the time the job was written. Raise a number when tests are added; a
# smaller number means tests disappeared and the job fails.
EXPECTED_MINIMUM = {
    "tests/test_discovery_d1_adapter.py": 35,
    "tests/test_discovery_d1_upstream.py": 53,
    "tests/test_discovery_d1_policy.py": 32,
    "tests/test_collect_period.py": 119,
    "tests/test_collect_period_upstream.py": 35,
}

# The strict xfail tests that document known defects (D1 closure report, section 3). The job requires
# exactly these: a fixed defect turns its xfail into a failure (strict), and a deleted or renamed one is
# caught here. When a defect is fixed, remove its entry in the same change as its xfail marker. D3 and the
# F-1/F-2 fix resolved all nine original ones, so the set is empty: ANY xfail in these files is now a failure
# until an owner-approved new known defect is listed here.
EXPECTED_XFAILS: frozenset[str] = frozenset()

# Literal addresses (IPv4 and IPv6): no DNS needed.
EXTERNAL_TARGETS = [
    ("1.1.1.1", 443),
    ("8.8.8.8", 53),
    ("151.101.0.223", 443),
    ("2606:4700:4700::1111", 443),
]
EXTERNAL_NAME = "pypi.org"  # a name lookup is informational; None skips it


# ---- process identity ----


def current_identity() -> dict:
    """Real and effective uid/gid of THIS process, read from the operating system, not from a name."""
    out = {}
    for key in ("getuid", "geteuid", "getgid", "getegid"):
        func = getattr(os, key, None)
        out[key[3:]] = func() if func else None
    return out


def identity_problems(expected_uid, expected_gid=None) -> list[str]:
    """Problems if this process is not exactly the expected user (real AND effective ids)."""
    ident = current_identity()
    if ident["uid"] is None:
        return ["the operating system does not expose uid/gid here, so the identity cannot be verified"]
    problems = []
    for label, want, keys in (
        ("uid", expected_uid, ("uid", "euid")),
        ("gid", expected_gid, ("gid", "egid")),
    ):
        if want in (None, ""):
            continue
        try:
            want = int(want)
        except ValueError:
            problems.append(f"expected {label} {want!r} is not a number")
            continue
        for key in keys:
            if ident[key] != want:
                problems.append(f"process {key} is {ident[key]}, expected {want}")
    return problems


def child_identity_problems(result: dict, expected_uid, expected_gid=None) -> list[str]:
    """Problems if a child process (the foundation runner) reports a different identity than expected."""
    problems = []
    for label, want in (("uid", expected_uid), ("gid", expected_gid)):
        if want in (None, ""):
            continue
        if result.get(label) != int(want):
            problems.append(f"child process {label} is {result.get(label)!r}, expected {int(want)}")
    return problems


# ---- network isolation ----


def isolation(db_host: str, db_port: int, expected_uid=None, expected_gid=None) -> int:
    ident = current_identity()
    print("process identity: " + " ".join(f"{k}={v}" for k, v in ident.items()))
    failed = False
    if expected_uid not in (None, ""):
        for problem in identity_problems(expected_uid, expected_gid):
            print(f"ERROR: {problem}")
            failed = True
    for host, port in EXTERNAL_TARGETS:
        try:
            socket.create_connection((host, port), timeout=5).close()
        except OSError as exc:
            print(f"external {host}:{port} blocked ({type(exc).__name__}: {exc})")
        else:
            print(f"ERROR: external connection to {host}:{port} SUCCEEDED; isolation is not effective")
            failed = True
    if EXTERNAL_NAME:
        try:
            socket.getaddrinfo(EXTERNAL_NAME, 443)
            print(f"note: name resolution of {EXTERNAL_NAME} WORKS for this user (DNS is not blocked)")
            try:
                socket.create_connection((EXTERNAL_NAME, 443), timeout=5).close()
            except OSError as exc:
                print(f"external {EXTERNAL_NAME}:443 blocked ({type(exc).__name__}: {exc})")
            else:
                print(f"ERROR: external connection to {EXTERNAL_NAME}:443 SUCCEEDED; not isolated")
                failed = True
        except OSError as exc:
            print(f"external name resolution blocked ({type(exc).__name__}: {exc})")
    try:
        socket.create_connection((db_host, db_port), timeout=5).close()
        print(f"local database {db_host}:{db_port} reachable")
    except OSError as exc:
        print(f"ERROR: the local database {db_host}:{db_port} is NOT reachable under isolation ({exc})")
        failed = True
    print("ISOLATION FAILED" if failed else "ISOLATION OK")
    return 1 if failed else 0


# ---- test report ----


def analyse(path: str) -> tuple[list[str], list[str]]:
    """(summary lines, problems). Never raises: an unreadable report is itself a problem."""
    lines = [SUMMARY_HEADER]
    problems: list[str] = []
    try:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"no such report: {path}")
        if os.path.getsize(path) == 0:
            raise ValueError("the report file is empty")
        root = ET.parse(path).getroot()
    except (OSError, ValueError, ET.ParseError) as exc:
        problems.append(f"REPORT unreadable (missing/empty/truncated/malformed): {type(exc).__name__}: {exc}")
        lines.append("- collected: 0 (the report could not be read)")
        return lines + [f"- PROBLEM: {p}" for p in problems], problems
    cases = list(root.iter("testcase"))
    per_file: dict[str, int] = {}
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0}
    xfailed_ids = set()
    for case in cases:
        classname = case.get("classname") or ""
        test_id = f"{classname}::{case.get('name')}"
        file_name = classname.replace(".", "/")
        for expected in EXPECTED_MINIMUM:
            stem = expected[:-3]
            if file_name == stem or file_name.startswith(stem + "/"):
                per_file[expected] = per_file.get(expected, 0) + 1
        if case.find("failure") is not None:
            counts["failed"] += 1
            problems.append(f"FAILED {test_id}")
        elif case.find("error") is not None:
            counts["errors"] += 1
            problems.append(f"ERROR {test_id}")
        elif (skip := case.find("skipped")) is not None:
            if (skip.get("type") or "") == "pytest.xfail":
                counts["xfailed"] += 1
                xfailed_ids.add(test_id)
            else:
                counts["skipped"] += 1
                problems.append(f"SKIPPED {test_id}: {skip.get('message')}")
        else:
            counts["passed"] += 1
    for expected, minimum in EXPECTED_MINIMUM.items():
        got = per_file.get(expected, 0)
        if got < minimum:
            problems.append(f"COLLECTION {expected}: {got} tests collected, expected at least {minimum}")
    if counts["xfailed"] != len(EXPECTED_XFAILS) or xfailed_ids != EXPECTED_XFAILS:
        missing = sorted(EXPECTED_XFAILS - xfailed_ids)
        unexpected = sorted(xfailed_ids - EXPECTED_XFAILS)
        problems.append(
            f"XFAIL expected exactly {len(EXPECTED_XFAILS)} known strict xfails, found {counts['xfailed']}; "
            f"missing {missing}; unexpected {unexpected}"
        )
    lines.append(f"- collected: {len(cases)}")
    lines.append("- " + ", ".join(f"{k}: {v}" for k, v in counts.items()))
    lines += [f"  - {expected}: {per_file.get(expected, 0)}" for expected in EXPECTED_MINIMUM]
    lines += [f"- PROBLEM: {p}" for p in problems]
    return lines, problems


def report(path: str) -> int:
    lines, problems = analyse(path)
    print("\n".join(lines))
    return 1 if problems else 0


def gate(path: str, summary_path: str) -> int:
    """Analyse the report, ALWAYS write the summary, and fail on any problem or on an unusable summary."""
    lines, problems = analyse(path)
    text = "\n".join(lines) + "\n"
    try:
        with open(summary_path, "w", encoding="utf-8") as handle:
            handle.write(text)
    except OSError as exc:
        print(text, end="")
        print(f"ERROR: the summary could not be written to {summary_path}: {exc}")
        return 1
    print(text, end="")
    if require_summary(summary_path) != 0:
        return 1
    return 1 if problems else 0


def require_summary(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        print(f"ERROR: no report summary: {exc}")
        return 1
    if not text.strip():
        print(f"ERROR: the report summary {path} is empty")
        return 1
    if SUMMARY_HEADER not in text:
        print(f"ERROR: the report summary {path} does not contain its header")
        return 1
    return 0


def main(argv: list[str]) -> int:
    if len(argv) in (4, 6) and argv[1] == "isolation":
        return isolation(argv[2], int(argv[3]), *(argv[4:6] if len(argv) == 6 else ()))
    if len(argv) == 4 and argv[1] == "gate":
        return gate(argv[2], argv[3])
    if len(argv) == 3 and argv[1] == "require-summary":
        return require_summary(argv[2])
    if len(argv) == 3 and argv[1] == "report":
        return report(argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
