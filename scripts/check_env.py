#!/usr/bin/env python3
"""
Pre-commit guard that keeps .env honest against .env.example.

Three checks, run against the working-tree files directly (not through git,
since .env is gitignored and pre-commit never sees ignored files):

1. Duplicate keys within .env — a silently-shadowed value is a real bug.
2. Unfilled placeholders — .env.example marks keys that must be
   customized with a trailing "# CHANGE ME" comment; if .env still holds
   that exact placeholder value, flag it.
3. Key drift between .env and .env.example — informational only, since
   some keys are optional and legitimately absent from .env.

Never prints values from .env — only key names and line numbers.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CHANGE_ME_MARKER = "# CHANGE ME"

LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def parse_env_file(path: Path) -> tuple[dict[str, list[tuple[int, str]]], set[str]]:
    """Return {key: [(lineno, value), ...]} and the set of keys marked CHANGE ME."""
    entries: dict[str, list[tuple[int, str]]] = {}
    change_me_keys: set[str] = set()
    for lineno, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        marked = line.endswith(CHANGE_ME_MARKER)
        if marked:
            line = line[: -len(CHANGE_ME_MARKER)].rstrip()
        match = LINE_RE.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        entries.setdefault(key, []).append((lineno, value))
        if marked:
            change_me_keys.add(key)
    return entries, change_me_keys


def main() -> int:
    example_path = REPO_ROOT / ".env.example"
    env_path = REPO_ROOT / ".env"

    if not env_path.is_file():
        # Nothing to check yet (fresh clone) — not this hook's job to enforce setup.
        return 0

    example_entries, change_me_keys = parse_env_file(example_path)
    env_entries, _ = parse_env_file(env_path)

    failures: list[str] = []
    warnings: list[str] = []

    for key, occurrences in env_entries.items():
        if len(occurrences) > 1:
            lines = ", ".join(str(lineno) for lineno, _ in occurrences)
            failures.append(
                f"{key} is defined {len(occurrences)}x in .env (lines {lines}) — later one silently wins"
            )

    for key in change_me_keys:
        example_value = example_entries[key][-1][1]
        env_occurrences = env_entries.get(key)
        if env_occurrences is None:
            continue  # covered by the missing-key warning below
        env_lineno, env_value = env_occurrences[-1]
        if env_value == example_value:
            failures.append(
                f"{key} (line {env_lineno}) still has its .env.example placeholder value — fill in a real value"
            )

    missing = sorted(set(example_entries) - set(env_entries))
    if missing:
        warnings.append(f"in .env.example but not .env: {', '.join(missing)}")

    extra = sorted(set(env_entries) - set(example_entries))
    if extra:
        warnings.append(
            f"in .env but not .env.example: {', '.join(extra)} — consider documenting in .env.example"
        )

    for warning in warnings:
        print(f"  ⚠ {warning}")
    for failure in failures:
        print(f"  ✗ {failure}")

    if failures:
        print(
            f"\n.env check failed ({len(failures)} issue{'s' if len(failures) != 1 else ''}) — see above."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
