"""Guardrails for the two things that are only wrong once it is too late.

Both failure modes here are invisible in review — the diff looks complete, the
suite is green, and the damage lands at deploy time or in a published release.

1. A model field edited without its migration. Nothing in the test suite needs
   the migration to exist: tests build their schema from the models, so they
   pass. The mismatch only surfaces as a failed `migrate` against the real
   database, after the image has shipped.

2. The three version strings drifting apart. docs/operations/RELEASE.md says
   they must match and the release checklist says to bump all three, but the
   only thing enforcing it was remembering to. A `prod.py` that reports one
   version while docker-compose.prod.yml pulls another is exactly the state in
   which `./prod.py update` does something surprising.
"""

import re
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from my_practice.version import VERSION

REPO_ROOT = Path(settings.BASE_DIR).parent


class MigrationDriftTests(TestCase):
    """`makemigrations --check` must have nothing left to generate."""

    def test_no_missing_migrations(self):
        try:
            call_command("makemigrations", "--check", "--dry-run", verbosity=0)
        except SystemExit:
            self.fail(
                "Model changes have no matching migration.\n"
                "  Generate it with: ./dev.py makemigrations\n"
                "  The suite builds its schema from the models, so it stays green "
                "either way — this only breaks when `migrate` runs for real."
            )


class VersionConsistencyTests(SimpleTestCase):
    """app/my_practice/version.py, prod.py and docker-compose.prod.yml agree."""

    def _read(self, relative_path, pattern, description):
        path = REPO_ROOT / relative_path
        self.assertTrue(path.is_file(), f"{relative_path} is missing")
        match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
        self.assertIsNotNone(
            match,
            f"Could not find {description} in {relative_path}. If the file moved or "
            f"the line was reworded, update the pattern in this test — do not delete it.",
        )
        return match.group(1)

    def test_version_strings_match(self):
        prod_version = self._read(
            "prod.py",
            r'^VERSION = "([^"]+)"',
            "the VERSION assignment",
        )
        image_version = self._read(
            "docker-compose.prod.yml",
            r"^\s*image:\s*ghcr\.io/dholbach/my-practice:(\S+)",
            "the app image tag",
        )

        self.assertEqual(
            VERSION,
            prod_version,
            "app/my_practice/version.py and prod.py disagree about the version. "
            "The release checklist bumps all three together — see "
            "docs/operations/RELEASE.md.",
        )
        self.assertEqual(
            VERSION,
            image_version,
            "app/my_practice/version.py and docker-compose.prod.yml disagree about "
            "the version. The release checklist bumps all three together — see "
            "docs/operations/RELEASE.md.",
        )

    def test_version_is_tag_shaped(self):
        """`./prod.py update` matches this against GitHub release tags."""
        self.assertRegex(
            VERSION,
            r"^v\d+\.\d+\.\d+$",
            "VERSION must look like a release tag (vX.Y.Z) — it is compared "
            "directly against tag_name from the GitHub releases API.",
        )
