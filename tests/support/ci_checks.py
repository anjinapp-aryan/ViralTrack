"""Checks run by the `discovery-offline` CI job (standard library only). Not a test module.

    python tests/support/ci_checks.py isolation <db-host> <db-port>
    python tests/support/ci_checks.py report <junit.xml>

`isolation` proves, after the firewall rule is installed, that an external connection FAILS and that the local
database service is still reachable. `report` enforces what the job promises: every expected test file was
collected (at least its recorded number of tests), nothing was skipped (a skip would mean the
upstream-backed tests did not run), nothing failed, and strict xfail tests are counted, not hidden.
It writes a short summary to stdout (the workflow appends it to the run summary).
"""
import socket
import sys
import xml.etree.ElementTree as ET

# Minimum number of tests per file at the time the job was written. Raise a number when tests are added; a
# smaller number means tests disappeared and the job fails.
EXPECTED_MINIMUM = {
    "tests/test_discovery_d1_adapter.py": 35,
    "tests/test_discovery_d1_upstream.py": 53,
    "tests/test_discovery_d1_policy.py": 35,
    "tests/test_collect_period.py": 119,
    "tests/test_collect_period_upstream.py": 35,
}
EXTERNAL_TARGETS = [("1.1.1.1", 443), ("8.8.8.8", 53), ("151.101.0.223", 443),
                    ("2606:4700:4700::1111", 443)]      # literal addresses (IPv4 and IPv6): no DNS needed


def isolation(db_host: str, db_port: int) -> int:
    failed = False
    for host, port in EXTERNAL_TARGETS:
        try:
            socket.create_connection((host, port), timeout=5).close()
        except OSError as exc:
            print(f"external {host}:{port} blocked ({type(exc).__name__}: {exc})")
        else:
            print(f"ERROR: external connection to {host}:{port} SUCCEEDED; isolation is not effective")
            failed = True
    try:
        socket.getaddrinfo("pypi.org", 443)
        try:
            socket.create_connection(("pypi.org", 443), timeout=5).close()
        except OSError as exc:
            print(f"external pypi.org:443 blocked ({type(exc).__name__}: {exc})")
        else:
            print("ERROR: external connection to pypi.org:443 SUCCEEDED; network isolation is not effective")
            failed = True
    except OSError as exc:
        print(f"external name resolution blocked ({type(exc).__name__}: {exc})")
    try:
        socket.create_connection((db_host, db_port), timeout=5).close()
        print(f"local database {db_host}:{db_port} reachable")
    except OSError as exc:
        print(f"ERROR: the local database {db_host}:{db_port} is NOT reachable under isolation ({exc})")
        failed = True
    return 1 if failed else 0


def report(path: str) -> int:
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    per_file: dict[str, int] = {}
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0}
    problems = []
    for case in cases:
        file_name = (case.get("classname") or "").replace(".", "/")
        for expected in EXPECTED_MINIMUM:
            stem = expected[:-3]
            if file_name == stem or file_name.startswith(stem + "/"):
                per_file[expected] = per_file.get(expected, 0) + 1
        if case.find("failure") is not None:
            counts["failed"] += 1
            problems.append(f"FAILED {case.get('classname')}::{case.get('name')}")
        elif case.find("error") is not None:
            counts["errors"] += 1
            problems.append(f"ERROR {case.get('classname')}::{case.get('name')}")
        elif (skip := case.find("skipped")) is not None:
            if (skip.get("type") or "") == "pytest.xfail":
                counts["xfailed"] += 1
            else:
                counts["skipped"] += 1
                problems.append(f"SKIPPED {case.get('classname')}::{case.get('name')}: {skip.get('message')}")
        else:
            counts["passed"] += 1
    for expected, minimum in EXPECTED_MINIMUM.items():
        got = per_file.get(expected, 0)
        if got < minimum:
            problems.append(f"COLLECTION {expected}: {got} tests collected, expected at least {minimum}")
    print("### Offline discovery tests (real upstream code, synthetic data, no network)")
    print(f"- collected: {len(cases)}")
    print("- " + ", ".join(f"{k}: {v}" for k, v in counts.items()))
    for expected in EXPECTED_MINIMUM:
        print(f"  - {expected}: {per_file.get(expected, 0)}")
    for problem in problems:
        print(f"- PROBLEM: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "isolation":
        raise SystemExit(isolation(sys.argv[2], int(sys.argv[3])))
    if len(sys.argv) == 3 and sys.argv[1] == "report":
        raise SystemExit(report(sys.argv[2]))
    raise SystemExit(__doc__)
