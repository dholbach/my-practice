"""Tests for the check_media management command (orphan/missing file audit)."""

import tempfile
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from ..models import CompanyExpense, ExpenseReceipt, Practice


class CheckMediaCommandTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.media_root = Path(self._tmpdir.name)
        self.practice = Practice.objects.create(
            name="Test Practice", slug="check-media-test", title="Test"
        )

    def _run(self):
        out = StringIO()
        with override_settings(MEDIA_ROOT=self.media_root):
            call_command("check_media", stdout=out)
        return out.getvalue()

    def test_missing_media_root_warns(self):
        with override_settings(MEDIA_ROOT=self.media_root / "does-not-exist"):
            out = StringIO()
            call_command("check_media", stdout=out)
        self.assertIn("MEDIA_ROOT not found", out.getvalue())

    def test_no_files_reports_clean(self):
        output = self._run()
        self.assertIn("No missing files", output)
        self.assertIn("No orphaned files", output)

    def test_reports_orphaned_file(self):
        (self.media_root / "logos").mkdir(parents=True)
        (self.media_root / "logos" / "stray.png").write_bytes(b"fake-png")

        output = self._run()
        self.assertIn("Orphaned files (1)", output)
        self.assertIn("logos/stray.png", output)

    def test_reports_missing_file(self):
        expense = CompanyExpense.objects.create(
            practice=self.practice,
            date=date(2026, 3, 1),
            amount=Decimal("50.00"),
        )
        ExpenseReceipt.objects.create(expense=expense, file="receipts/gone.pdf")

        output = self._run()
        self.assertIn("Missing files (1)", output)
        self.assertIn("[CompanyExpense] receipts/gone.pdf", output)

    def test_delete_orphans_removes_file(self):
        (self.media_root / "logos").mkdir(parents=True)
        stray = self.media_root / "logos" / "stray.png"
        stray.write_bytes(b"fake-png")

        out = StringIO()
        with override_settings(MEDIA_ROOT=self.media_root):
            call_command("check_media", "--delete-orphans", stdout=out)

        self.assertIn("1 files deleted", out.getvalue())
        self.assertFalse(stray.exists())
