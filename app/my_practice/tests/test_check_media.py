"""Tests for the check_media management command (orphan/missing file audit)."""

import tempfile
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from ..management.commands.check_media import _models_with_file_fields
from ..models import Client, ClientDocument, CompanyExpense, ExpenseReceipt, Practice


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
        self.assertIn("[ExpenseReceipt] receipts/gone.pdf", output)

    def test_delete_orphans_removes_file(self):
        (self.media_root / "logos").mkdir(parents=True)
        stray = self.media_root / "logos" / "stray.png"
        stray.write_bytes(b"fake-png")

        out = StringIO()
        with override_settings(MEDIA_ROOT=self.media_root):
            call_command("check_media", "--delete-orphans", stdout=out)

        self.assertIn("1 files deleted", out.getvalue())
        self.assertFalse(stray.exists())


class CheckMediaCoverageTests(TestCase):
    """A model this command does not know about has its files deleted.

    `--delete-orphans` removes every file no listed field references, so a
    model missing from that list is not a gap in a report — it is data loss.
    ClientDocument was missing, which put all 126 stored documents (signed
    treatment contracts, intake forms, doctors' letters) on the delete list,
    and no test noticed because none of them created a ClientDocument.
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.media_root = Path(self._tmpdir.name)
        self.practice = Practice.objects.create(
            name="Test Practice", slug="check-media-coverage", title="Test"
        )

    def test_a_stored_client_document_is_not_an_orphan(self):
        client = Client.objects.create(
            client_code="XX-1", full_name="Max Mustermann", practice=self.practice
        )
        rel_path = "clients/xx-1/2026/contract.pdf"
        stored = self.media_root / rel_path
        stored.parent.mkdir(parents=True)
        stored.write_bytes(b"%PDF-1.4 signed contract")
        ClientDocument.objects.create(
            client=client,
            document_type=ClientDocument.DocumentType.CONTRACT,
            file=rel_path,
            document_date=date(2026, 3, 1),
        )

        out = StringIO()
        with override_settings(MEDIA_ROOT=self.media_root):
            call_command("check_media", "--delete-orphans", stdout=out)

        self.assertIn("No orphaned files", out.getvalue())
        self.assertTrue(stored.exists(), "a referenced client document must not be deleted")

    def test_discovery_finds_every_model_that_stores_a_file(self):
        # Guards against anyone replacing the registry scan with a hand-list again.
        covered = {model.__name__ for model, _ in _models_with_file_fields()}
        self.assertLessEqual({"ClientDocument", "ExpenseReceipt", "Practice"}, covered)

    def test_discovery_reports_the_field_names_it_will_read(self):
        by_name = {model.__name__: fields for model, fields in _models_with_file_fields()}
        self.assertEqual(sorted(by_name["Practice"]), ["logo", "signature"])
        self.assertEqual(by_name["ClientDocument"], ["file"])
