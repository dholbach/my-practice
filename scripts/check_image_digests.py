#!/usr/bin/env python3
"""Fail when a third-party container image is referenced without a digest.

A bare ``image: postgres:17-alpine`` is a moving target: a rebuild of the tag
changes what runs and Dependabot has nothing to bump. ``repo:tag@sha256:...``
pins the exact image while Dependabot still proposes each rebuild as a diff.

Checked: ``image:`` lines in docker-compose*.yml and .github/workflows/*.yml.

Exempt, because a digest cannot or must not be written there:
  * ``my-practice-django``, built locally by ``./dev.py`` (never pulled);
  * ``ghcr.io/dholbach/my-practice``, this project's own release image, whose
    tag ``prod.py update`` rewrites on every release.
Values containing ``${...}`` are exempt as well (the smoke test's version).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXEMPT_PREFIXES = ("my-practice-django", "ghcr.io/dholbach/my-practice:")
IMAGE_LINE = re.compile(r"^\s*(?:-\s+)?image:\s*(\S+)")
PINNED = re.compile(r":[^:@/]+@sha256:[0-9a-f]{64}$")


def main() -> int:
    files = [*ROOT.glob("docker-compose*.yml"), *ROOT.glob(".github/workflows/*.yml")]
    problems = []
    for path in sorted(files):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            match = IMAGE_LINE.match(line)
            if not match:
                continue
            image = match.group(1).strip("'\"")
            if "${" in image or image.startswith(EXEMPT_PREFIXES) or PINNED.search(image):
                continue
            problems.append(f"{path.relative_to(ROOT)}:{number}: {image!r} has no @sha256 digest")
    print("\n".join(problems) or "all third-party images are pinned")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
