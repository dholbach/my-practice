"""`prod.py` creates the bind-mounted data directories itself.

Left to Docker, a missing bind-mount source is created owned by root, and a
later `./prod.py backup` run as the invoking user fails on `chmod`.
"""

import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from .test_prod_network import _load_prod


class EnsureDataDirsTests(SimpleTestCase):
    def setUp(self):
        self.prod = _load_prod()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "data"

    def test_creates_every_mounted_subdirectory(self):
        with mock.patch.object(self.prod, "_data_dir", return_value=str(self.root)):
            self.prod._ensure_data_dirs()
        for name in ("backups", "media", "documents", "questionnaires"):
            self.assertTrue((self.root / name).is_dir(), name)

    def test_existing_directories_are_left_alone(self):
        (self.root / "media").mkdir(parents=True)
        (self.root / "media" / "keep.txt").write_text("x")
        with mock.patch.object(self.prod, "_data_dir", return_value=str(self.root)):
            self.prod._ensure_data_dirs()
        self.assertTrue((self.root / "media" / "keep.txt").exists())

    def test_subdirs_match_the_compose_bind_mounts(self):
        compose = Path(self.prod.COMPOSE_FILE).read_text()
        for name in self.prod.DATA_SUBDIRS:
            self.assertIn(f"/{name}:", compose)
