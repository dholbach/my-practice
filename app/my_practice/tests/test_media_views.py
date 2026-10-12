"""Tests for authenticated media serving (views/media_views.py).

Uploaded files are Art. 9 health data at guessable paths, so the contract is:
served only to a logged-in member of the practice whose row references the
file, 404 for everything else.
"""

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from ..management.commands.check_media import _models_with_file_fields
from ..models import Client, ClientDocument, CompanyExpense, ExpenseReceipt
from ..views.media_views import MEDIA_FILE_OWNERS
from .test_helpers import BaseTestCase, create_test_practice, link_user_to_practice

DOC_PATH = "clients/xx-1/2026/contract-2026-03-01.pdf"
DOC_BYTES = b"%PDF-1.4 signed contract"


class ServeMediaTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.media_root = Path(self._tmpdir.name) / "media"
        self.media_root.mkdir()
        settings_override = override_settings(MEDIA_ROOT=self.media_root)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

        self.client_obj = Client.objects.create(
            client_code="XX-1", full_name="Max Mustermann", practice=self.practice
        )
        self._store(DOC_PATH, DOC_BYTES)
        ClientDocument.objects.create(
            client=self.client_obj,
            document_type=ClientDocument.DocumentType.CONTRACT,
            file=DOC_PATH,
            document_date=date(2026, 3, 1),
        )
        self.client.login(username="testuser", password="testpass123")

    def _store(self, rel_path: str, data: bytes) -> None:
        target = self.media_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def _url(self, rel_path: str) -> str:
        return reverse("serve_media", kwargs={"path": rel_path})

    def test_member_gets_client_document(self):
        response = self.client.get(self._url(DOC_PATH))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), DOC_BYTES)
        self.assertEqual(response["Content-Type"], "application/pdf")
        # (DEBUG's NoCacheMiddleware rewrites the header; no-store survives either way.)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("inline", response["Content-Disposition"])

    def test_model_url_resolves_to_this_view(self):
        # Templates link via FieldFile.url; that must land here, not on a static route.
        doc = ClientDocument.objects.get(file=DOC_PATH)
        self.assertEqual(self.client.get(doc.file.url).status_code, 200)

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()

        response = self.client.get(self._url(DOC_PATH))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_member_of_another_practice_gets_404(self):
        other = User.objects.create_user(username="other", password="otherpass123")
        link_user_to_practice(other, create_test_practice("Other Practice", slug="other"))
        self.client.force_login(other)

        self.assertEqual(self.client.get(self._url(DOC_PATH)).status_code, 404)

    def test_user_without_practice_gets_404(self):
        loner = User.objects.create_user(username="loner", password="lonerpass123")
        self.client.force_login(loner)

        self.assertEqual(self.client.get(self._url(DOC_PATH)).status_code, 404)

    def test_file_no_row_references_is_not_served(self):
        # Exactly the files a /media/ alias would leak: orphans, leftovers, guesses.
        self._store("clients/xx-1/2026/stray.pdf", b"%PDF-1.4 orphan")

        self.assertEqual(self.client.get(self._url("clients/xx-1/2026/stray.pdf")).status_code, 404)

    def test_row_without_file_on_disk_is_404(self):
        ClientDocument.objects.create(
            client=self.client_obj,
            document_type=ClientDocument.DocumentType.CONTRACT,
            file="clients/xx-1/2026/gone.pdf",
        )

        self.assertEqual(self.client.get(self._url("clients/xx-1/2026/gone.pdf")).status_code, 404)

    def test_path_escaping_media_root_is_404_even_with_a_row(self):
        (self.media_root.parent / "outside.pdf").write_bytes(b"not media")
        ClientDocument.objects.create(
            client=self.client_obj,
            document_type=ClientDocument.DocumentType.CONTRACT,
            file="../outside.pdf",
        )

        self.assertEqual(self.client.get(self._url("../outside.pdf")).status_code, 404)

    def test_post_is_rejected(self):
        self.assertEqual(self.client.post(self._url(DOC_PATH)).status_code, 405)

    def test_expense_receipt_is_served_to_member(self):
        expense = CompanyExpense.objects.create(
            practice=self.practice, date=date(2026, 3, 1), amount=Decimal("50.00")
        )
        self._store("receipts/2026/beleg.pdf", b"%PDF-1.4 receipt")
        ExpenseReceipt.objects.create(expense=expense, file="receipts/2026/beleg.pdf")

        self.assertEqual(self.client.get(self._url("receipts/2026/beleg.pdf")).status_code, 200)

    def test_practice_logo_is_served_to_member(self):
        self._store("practice/logo.png", b"\x89PNG fake")
        self.practice.logo = "practice/logo.png"
        self.practice.save()

        response = self.client.get(self._url("practice/logo.png"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")


class MediaOwnerCoverageTests(TestCase):
    def test_every_file_field_has_an_owner_lookup(self):
        # A FileField missing from MEDIA_FILE_OWNERS fails closed — its uploads
        # 404 for everyone. This catches a new upload field before users do.
        registry = {
            (model, field) for model, fields in _models_with_file_fields() for field in fields
        }
        self.assertEqual(set(MEDIA_FILE_OWNERS), registry)
