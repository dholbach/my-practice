#!/usr/bin/env python3
"""
Pre-commit guard against committing personal data.

Scans staged changes (or the whole tree with --all) for terms from a local,
untracked denylist. The denylist holds the actual sensitive strings (real
names, addresses, client codes), so it must never be committed — it lives
inside .git/ where git cannot track it.

Denylist location: .git/pii-denylist (override with PII_DENYLIST env var).
Format: one term per line; blank lines and lines starting with # ignored.
Matching is case-insensitive substring.

If the denylist is missing or empty the check passes silently, so clones
and outside contributors are unaffected.

Usage:
    scripts/check_pii.py          # scan staged additions (pre-commit mode)
    scripts/check_pii.py --all    # scan all tracked files
"""

import os
import subprocess
import sys
from pathlib import Path


def load_denylist(repo_root: Path) -> list[str]:
    path = Path(os.environ.get("PII_DENYLIST", repo_root / ".git" / "pii-denylist"))
    if not path.is_file():
        return []
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(line.lower())
    return terms


def staged_additions() -> list[tuple[str, str]]:
    """Return (filename, added_line) pairs from the staged diff."""
    diff = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--no-color"],
        capture_output=True,
        text=True,
        errors="replace",
    ).stdout
    pairs = []
    current = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            pairs.append((current, line[1:]))
    return pairs


def tracked_file_lines() -> list[tuple[str, str]]:
    files = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True
    ).stdout.splitlines()
    pairs = []
    for f in files:
        try:
            text = Path(f).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        pairs.extend((f, line) for line in text.splitlines())
    return pairs


def main() -> int:
    repo_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
        ).stdout.strip()
    )
    terms = load_denylist(repo_root)
    if not terms:
        return 0

    pairs = tracked_file_lines() if "--all" in sys.argv else staged_additions()

    hits = []
    for filename, line in pairs:
        lowered = line.lower()
        for term in terms:
            if term in lowered:
                hits.append((filename, term))

    if hits:
        print("🚫 PII check failed — denylisted terms found:")
        for filename, term in sorted(set(hits)):
            print(f"   {filename}: contains '{term}'")
        print("Remove the sensitive data, or edit .git/pii-denylist if this is a false positive.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
