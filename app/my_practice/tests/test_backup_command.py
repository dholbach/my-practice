"""Tests for `prod.py backup` / `restore` (also behind scripts/backup.sh).

A backup that silently fails is found out on the day it is needed. These run
the real command against a fake `docker` that plays pg_dump, find and tar, so
every verification step is exercised without containers.
"""

import contextlib
import importlib.util
import io
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from .test_helpers import BaseTestCase
from .test_release_guardrails import REPO_ROOT

FAKE_DOCKER = """#!{python}
import os, subprocess, sys
args = sys.argv[sys.argv.index("-T") + 2:]
mode = os.environ.get("FAKE_MODE", "ok")
media = os.environ["FAKE_MEDIA_PARENT"]
if args[0] == "pg_dump":
    if mode == "dump_fails":
        sys.exit(1)
    sys.stdout.write("CREATE TABLE t (id int);\\n" * 1000)
    if mode != "dump_truncated":
        sys.stdout.write("--\\n-- PostgreSQL database dump complete\\n--\\n")
elif args[0] == "find":
    for root, _dirs, files in os.walk(os.path.join(media, "media")):
        for name in files:
            print(os.path.join(root, name))
elif args[0] == "tar":
    exclude = ["--exclude=media/b.pdf"] if mode == "tar_short" else []
    sys.exit(subprocess.call(["tar", "czf", "-", *exclude, "-C", media, "media"]))
elif args[0] == "psql":
    with open(os.environ["FAKE_PSQL_OUT"], "wb") as out:
        out.write(sys.stdin.buffer.read())
elif args[0] == "sh":
    sys.exit(subprocess.call(["tar", "xzf", "-", "-C", os.environ["FAKE_RESTORE_DIR"]]))
"""


def _load_prod():
    spec = importlib.util.spec_from_file_location("prod_under_test", REPO_ROOT / "prod.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BackupCommandTests(SimpleTestCase):
    def setUp(self):
        self.prod = _load_prod()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.backup_dir = self.root / "backups"
        media = self.root / "app" / "media"
        media.mkdir(parents=True)
        (media / "a.pdf").write_bytes(b"%PDF a")
        (media / "b.pdf").write_bytes(b"%PDF b")

        docker = self.root / "docker"
        docker.write_text(FAKE_DOCKER.format(python=sys.executable))
        docker.chmod(docker.stat().st_mode | stat.S_IEXEC)
        self.compose = [str(docker), "compose", "-f", "unused.yml"]

        self.env = {"FAKE_MEDIA_PARENT": str(self.root / "app"), "FAKE_MODE": "ok"}
        self.old_env = {
            k: os.environ.get(k) for k in [*self.env, "FAKE_PSQL_OUT", "FAKE_RESTORE_DIR"]
        }
        os.environ.update(self.env)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _backup(self, mode="ok", passphrase_file=None):
        os.environ["FAKE_MODE"] = mode
        return self.prod.run_backup(self.compose, str(self.backup_dir), passphrase_file)

    def _listing(self):
        return sorted(p.name for p in self.backup_dir.iterdir()) if self.backup_dir.exists() else []

    def test_successful_backup_writes_verified_private_archives(self):
        finals = self._backup()

        names = [Path(p).name for p in finals]
        self.assertTrue(names[0].startswith("db_backup_") and names[0].endswith(".sql.gz"))
        self.assertTrue(names[1].startswith("media_backup_") and names[1].endswith(".tar.gz"))
        with tarfile.open(finals[1]) as tar:
            self.assertEqual(
                sorted(m.name for m in tar if m.isfile()), ["media/a.pdf", "media/b.pdf"]
            )
        self.assertEqual(stat.S_IMODE(os.stat(finals[0]).st_mode), 0o600)
        self.assertEqual(self._listing(), sorted(names))  # no temp files left

    def test_backup_directory_is_owner_only(self):
        # A plaintext archive is protected only by its directory.
        self.backup_dir.mkdir(mode=0o755)
        os.chmod(self.backup_dir, 0o755)
        self._backup()
        self.assertEqual(stat.S_IMODE(os.stat(self.backup_dir).st_mode), 0o700)

    def test_failures_leave_nothing_that_looks_like_a_backup(self):
        for mode, message in [
            ("dump_fails", "pg_dump"),
            ("dump_truncated", "trailer missing"),
            ("tar_short", "holds 1 files, expected 2"),
        ]:
            with self.subTest(mode=mode):
                shutil.rmtree(self.backup_dir, ignore_errors=True)
                with self.assertRaisesMessage(self.prod.BackupError, message):
                    self._backup(mode)
                self.assertFalse([n for n in self._listing() if n.startswith("media_backup_")])
                if mode != "tar_short":
                    self.assertEqual(self._listing(), [])

    def test_failed_run_does_not_prune_old_backups(self):
        self.backup_dir.mkdir()
        old = self.backup_dir / "db_backup_20200101_000000.sql.gz"
        old.write_bytes(b"old")
        ancient = time.time() - 60 * 86400
        os.utime(old, (ancient, ancient))

        with self.assertRaises(self.prod.BackupError):
            self._backup("dump_fails")
        self.assertTrue(old.exists())

        self._backup()
        self.assertFalse(old.exists())

    @unittest.skipUnless(shutil.which("gpg"), "gpg not installed")
    def test_encrypted_backup_restores(self):
        gnupg_home = tempfile.TemporaryDirectory()
        self.addCleanup(gnupg_home.cleanup)
        os.environ["GNUPGHOME"] = gnupg_home.name
        self.addCleanup(os.environ.pop, "GNUPGHOME", None)
        passphrase = self.root / "passphrase"
        passphrase.write_text("correct horse battery staple\n")

        finals = self._backup(passphrase_file=str(passphrase))

        self.assertTrue(all(p.endswith(".gpg") for p in finals))
        self.assertFalse(Path(finals[0]).read_bytes().startswith(b"\x1f\x8b"))  # not plain gzip

        os.environ["FAKE_PSQL_OUT"] = str(self.root / "restored.sql")
        os.environ["FAKE_RESTORE_DIR"] = str(self.root / "restored")
        (self.root / "restored").mkdir()
        os.environ["BACKUP_PASSPHRASE_FILE"] = str(passphrase)
        self.addCleanup(os.environ.pop, "BACKUP_PASSPHRASE_FILE", None)
        original_compose_cmd = self.prod._compose_cmd
        self.prod._compose_cmd = lambda _args: self.compose
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = self.prod.cmd_restore([*finals, "--yes"])
        finally:
            self.prod._compose_cmd = original_compose_cmd

        self.assertEqual(result.returncode, 0)
        self.assertIn(b"database dump complete", (self.root / "restored.sql").read_bytes())
        self.assertEqual((self.root / "restored" / "media" / "a.pdf").read_bytes(), b"%PDF a")


class UpdateBackupTests(SimpleTestCase):
    """`prod.py update` migrates on restart with no way back, so it backs up first."""

    def setUp(self):
        self.prod = _load_prod()
        self.calls = []
        for patcher in [
            mock.patch.object(self.prod, "_require_secrets"),
            mock.patch.object(self.prod, "_require_no_foreign_containers"),
            mock.patch.object(self.prod, "_ensure_bind_address"),
            mock.patch.object(self.prod, "_warn_if_proxy_bypassable"),
            mock.patch.object(self.prod, "_passphrase_file", return_value=None),
            mock.patch.object(self.prod, "compose", side_effect=self._compose),
            mock.patch("urllib.request.urlopen", side_effect=OSError("offline")),
        ]:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _compose(self, *args):
        self.calls.append(args[0])
        return subprocess.CompletedProcess(args=[], returncode=0)

    def _update(self, *args, backup_error=None):
        def backup(*_args):
            self.calls.append("backup")
            if backup_error:
                raise self.prod.BackupError(backup_error)

        with (
            mock.patch.object(self.prod, "run_backup", side_effect=backup),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            result = self.prod.cmd_update(["--yes", *args])
        return result, err.getvalue()

    def test_backs_up_after_pull_and_before_restart(self):
        result, _ = self._update()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.calls, ["pull", "backup", "up"])

    def test_failed_backup_aborts_before_restart(self):
        result, err = self._update(backup_error="Database backup failed")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("up", self.calls)
        self.assertIn("--skip-backup", err)

    def test_skip_backup(self):
        result, _ = self._update("--skip-backup")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.calls, ["pull", "up"])


class DashboardBackupWarningTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.backup_dir = Path(tmp.name)
        override = override_settings(BACKUP_DIR=str(self.backup_dir), BACKUP_MAX_AGE_HOURS=48)
        override.enable()
        self.addCleanup(override.disable)
        self.client.login(username="testuser", password="testpass123")

    def _backup_aged(self, days, suffix=".sql.gz"):
        path = self.backup_dir / f"db_backup_20260101_000000{suffix}"
        path.write_bytes(b"x")
        then = time.time() - days * 86400
        os.utime(path, (then, then))

    def _dashboard(self, language="en"):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = language
        return self.client.get(reverse("dashboard"))

    def _warning(self):
        return self._dashboard().context["backup_warning"]

    def test_no_backup_at_all_warns(self):
        self.assertEqual(self._warning(), {"latest": None})
        self.assertContains(self._dashboard(), "No backup has been made yet.")

    def test_recent_backup_is_quiet(self):
        self._backup_aged(0.5)
        self.assertIsNone(self._warning())

    def test_old_backup_warns_with_its_age(self):
        self._backup_aged(3, suffix=".sql.gz.gpg")
        self.assertEqual(self._warning()["days"], 3)
        self.assertContains(self._dashboard("de"), "vor 3 Tagen")

    def test_temp_files_do_not_count(self):
        (self.backup_dir / ".db_backup_20260101_000000.abc").write_bytes(b"x")
        self.assertEqual(self._warning(), {"latest": None})

    @override_settings(BACKUP_MAX_AGE_HOURS=0)
    def test_check_can_be_turned_off(self):
        self.assertIsNone(self._warning())
