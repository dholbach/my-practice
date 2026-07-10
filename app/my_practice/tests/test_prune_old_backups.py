"""
Tests for the prune_old_backups management command (P-007).
"""

import os
import tempfile
from datetime import datetime, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class PruneOldBackupsTest(TestCase):
    def setUp(self):
        self.backup_dir = tempfile.mkdtemp()

    def _make_backup(self, name: str, age_days: int) -> str:
        path = os.path.join(self.backup_dir, name)
        with open(path, "wb") as f:
            f.write(b"x" * 1024)
        mtime = (datetime.now() - timedelta(days=age_days)).timestamp()
        os.utime(path, (mtime, mtime))
        return path

    def _run(self, *args):
        out = StringIO()
        call_command("prune_old_backups", *args, "--backup-dir", self.backup_dir, stdout=out)
        return out.getvalue()

    def test_missing_backup_dir_warns_and_exits(self):
        out = StringIO()
        call_command("prune_old_backups", "--backup-dir", "/nonexistent/path/xyz", stdout=out)
        self.assertIn("nicht gefunden", out.getvalue())

    def test_deletes_files_older_than_cutoff(self):
        old_path = self._make_backup("db_backup_old.sql.gz", age_days=40)
        recent_path = self._make_backup("db_backup_recent.sql.gz", age_days=5)

        output = self._run()

        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(recent_path))
        self.assertIn("Gelöscht: 1 Datei(en)", output)

    def test_dry_run_does_not_delete(self):
        old_path = self._make_backup("db_backup_old.sql.gz", age_days=40)

        output = self._run("--dry-run")

        self.assertTrue(os.path.exists(old_path))
        self.assertIn("[dry-run]", output)
        self.assertIn("Würde löschen: 1 Datei(en)", output)

    def test_custom_days_threshold(self):
        path = self._make_backup("db_backup_a.sql.gz", age_days=10)

        # Default 30-day cutoff wouldn't touch a 10-day-old file.
        self._run()
        self.assertTrue(os.path.exists(path))

        # A 5-day cutoff should.
        self._run("--days", "5")
        self.assertFalse(os.path.exists(path))

    def test_matches_media_backup_patterns(self):
        tar_path = self._make_backup("media_backup_old.tar.gz", age_days=40)
        empty_path = self._make_backup("media_backup_old.empty", age_days=40)

        self._run()

        self.assertFalse(os.path.exists(tar_path))
        self.assertFalse(os.path.exists(empty_path))

    def test_ignores_non_matching_files(self):
        other_path = self._make_backup("notes.txt", age_days=40)

        output = self._run()

        self.assertTrue(os.path.exists(other_path))
        self.assertIn("Gelöscht: 0 Datei(en)", output)
