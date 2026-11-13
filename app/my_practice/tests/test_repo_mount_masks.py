"""The dev container sees the repo root at /repo, minus the gitignored local files.

docker-compose.yml mounts the checkout read-only so the release guardrails can
read prod.py and the compose files, then masks .env, .git and the directories
holding personal notes. A dropped mask, or a new secret-shaped file outside the
masked directories (an `.env.bak`, an editor swap file), would be readable by
anything running in the container. Neither shows up in review.

Runs only in the dev container: CI and native runs read the checkout directly,
where these files are the developer's own.
"""

import fnmatch
import os
import re
import unittest

from django.test import SimpleTestCase

from .test_release_guardrails import REPO_ROOT

IN_DEV_CONTAINER = bool(os.environ.get("MY_PRACTICE_REPO_ROOT"))

# The .gitignore "Secrets" section: names that may exist under /repo only empty.
SECRET_PATTERNS = (".env", ".env.*", "*.sw?")
ALLOWED = {".env.example"}
# Large, gitignored and harmless; not worth walking.
SKIP_DIRS = {"node_modules", ".venv", "__pycache__", ".ruff_cache", ".pytest_cache"}


def _masked_targets() -> list[str]:
    compose = (REPO_ROOT / "docker-compose.yml").read_text()
    return re.findall(r"(?::|target: )/repo/([^:,}\s]+)", compose)


@unittest.skipUnless(IN_DEV_CONTAINER, "only the dev container mounts the repo root")
class RepoMountMaskTests(SimpleTestCase):
    def test_masks_are_in_effect(self):
        targets = _masked_targets()
        self.assertIn(".env", targets, "the mask list in docker-compose.yml moved")
        for target in targets:
            path = REPO_ROOT / target
            with self.subTest(target=target):
                if path.is_dir():
                    self.assertEqual(list(path.iterdir()), [], f"/repo/{target} is not masked")
                else:
                    self.assertEqual(path.stat().st_size, 0, f"/repo/{target} is not masked")

    def test_no_secret_shaped_file_is_readable(self):
        exposed = []
        for root, dirs, files in os.walk(REPO_ROOT):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in files:
                if name in ALLOWED or not any(fnmatch.fnmatch(name, p) for p in SECRET_PATTERNS):
                    continue
                path = os.path.join(root, name)
                if os.path.getsize(path):
                    exposed.append(os.path.relpath(path, REPO_ROOT))
        self.assertEqual(
            exposed,
            [],
            "Readable in the dev container through the /repo mount. Delete the file, or "
            "mask it (or its directory) in docker-compose.yml's django volumes.",
        )
