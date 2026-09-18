#!/usr/bin/env python3
"""Fail if the runtime pins in requirements.txt and requirements-dev.txt diverge.

requirements-dev.txt duplicates every runtime pin instead of using `-r
requirements.txt` — Dependabot does not resolve `-r` includes when it generates
a security-update PR, so runtime CVE alerts raised against the dev file had no
fix path. The duplication buys working Dependabot coverage; this keeps it
honest.

The check is one-directional on purpose. requirements-dev.txt is a superset:
it carries the runtime pins *plus* the tooling (ruff, mypy, pytest, ...), which
must never leak into the production image. So every pin in requirements.txt has
to appear in requirements-dev.txt at the same version, while extra entries in
the dev file are exactly what is expected.

This exists because the two files had already drifted: requirements.txt pinned
sqlparse to close PYSEC-2026-3696..3699 and requirements-dev.txt did not carry
the pin at all, so CI — which installs requirements-dev.txt — was testing
against the vulnerable version the production image did not ship.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "app" / "requirements.txt"
DEV = ROOT / "app" / "requirements-dev.txt"

# name==version, with optional extras (`psycopg[binary]==3.3.5`) and an
# optional trailing comment.
PIN = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)(?:\[[^\]]*\])?==(?P<version>[^\s#]+)")


def normalise(name):
    """PEP 503 normalisation, so `types_foo` and `types-foo` compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


def read_pins(path):
    """Map of normalised package name -> (version, line number)."""
    pins = {}
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = PIN.match(stripped)
        if match:
            pins[normalise(match.group("name"))] = (match.group("version"), lineno)
    return pins


def main():
    runtime = read_pins(RUNTIME)
    dev = read_pins(DEV)

    missing = []
    mismatched = []
    for name, (version, lineno) in sorted(runtime.items()):
        if name not in dev:
            missing.append(f"{name}=={version}  (requirements.txt:{lineno})")
        elif dev[name][0] != version:
            mismatched.append(
                f"{name}: requirements.txt has {version} (line {lineno}), "
                f"requirements-dev.txt has {dev[name][0]} (line {dev[name][1]})"
            )

    if not missing and not mismatched:
        return 0

    print("Runtime pins are out of sync between the two requirements files:\n", file=sys.stderr)
    if missing:
        print("  Missing from app/requirements-dev.txt:", file=sys.stderr)
        for item in missing:
            print(f"    {item}", file=sys.stderr)
        print(file=sys.stderr)
    if mismatched:
        print("  Version mismatch:", file=sys.stderr)
        for item in mismatched:
            print(f"    {item}", file=sys.stderr)
        print(file=sys.stderr)
    print(
        "  CI installs requirements-dev.txt, so a pin that is only in requirements.txt\n"
        "  is never exercised by the test suite — and a pin that is only in\n"
        "  requirements-dev.txt never reaches the production image. Update both.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
