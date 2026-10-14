"""Tests for encrypted client-document storage (storage.py)."""

import importlib
import io
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path

from cryptography.fernet import Fernet
from django.apps import apps
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from ..fields import EncryptionKeyError
from ..models import Client, ClientDocument
from ..storage import EncryptedFileSystemStorage, is_encrypted
from .test_helpers import BaseTestCase

LEGACY_PATH = "clients/xx-1/2026/intake-2026-01-15.pdf"
LEGACY_BYTES = b"%PDF-1.4 intake form written before encryption"


def _png_upload() -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 120, 80)).save(buffer, format="PNG")
    return SimpleUploadedFile("scan.png", buffer.getvalue(), content_type="image/png")


class DocumentEncryptionTestBase(BaseTestCase):
    def setUp(self):
        super().setUp()
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        self.media_root = Path(tmpdir.name)
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)

        self.client_obj = Client.objects.create(
            client_code="XX-1", full_name="Max Mustermann", practice=self.practice
        )
        self.client.login(username="testuser", password="testpass123")

    def _on_disk(self, name: str) -> bytes:
        return (self.media_root / name).read_bytes()

    def _legacy_document(self) -> ClientDocument:
        target = self.media_root / LEGACY_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(LEGACY_BYTES)
        return ClientDocument.objects.create(
            client=self.client_obj,
            document_type=ClientDocument.DocumentType.INTAKE,
            file=LEGACY_PATH,
            document_date=date(2026, 1, 15),
        )

    def _upload(self) -> ClientDocument:
        response = self.client.post(
            reverse("client_document_upload", args=[self.client_obj.pk]),
            {"file": _png_upload(), "document_type": "intake"},
        )
        self.assertEqual(response.status_code, 201)
        return ClientDocument.objects.get(pk=response.json()["id"])


class EncryptedUploadTests(DocumentEncryptionTestBase):
    def test_document_field_uses_encrypted_storage(self):
        storage = ClientDocument._meta.get_field("file").storage
        self.assertIsInstance(storage, EncryptedFileSystemStorage)

    def test_upload_is_ciphertext_on_disk_and_plain_when_served(self):
        doc = self._upload()

        self.assertTrue(is_encrypted(self._on_disk(doc.file.name)))
        response = self.client.get(doc.file.url)
        self.assertEqual(response.status_code, 200)
        served = b"".join(response.streaming_content)
        self.assertTrue(served.startswith(b"\xff\xd8"))  # JPEG after upload compression
        self.assertEqual(response["Content-Type"], "image/jpeg")

    def test_wrong_key_names_the_file(self):
        doc = self._upload()
        with (
            override_settings(FERNET_KEY=Fernet.generate_key().decode()),
            self.assertRaisesMessage(EncryptionKeyError, doc.file.name),
        ):
            doc.file.open("rb")

    def test_legacy_plaintext_file_still_served(self):
        doc = self._legacy_document()
        response = self.client.get(doc.file.url)
        self.assertEqual(b"".join(response.streaming_content), LEGACY_BYTES)

    def test_storage_refuses_write_mode(self):
        doc = self._upload()
        with self.assertRaises(ValueError):
            doc.file.storage.open(doc.file.name, "wb")


class DocumentMigrationAndRotationTests(DocumentEncryptionTestBase):
    def test_migration_encrypts_legacy_files_once(self):
        migration = importlib.import_module(
            "my_practice.migrations.0006_encrypt_client_document_files"
        )
        doc = self._legacy_document()
        already = self._upload()
        already_bytes = self._on_disk(already.file.name)

        migration.encrypt_files(apps, None)
        migration.encrypt_files(apps, None)

        self.assertTrue(is_encrypted(self._on_disk(LEGACY_PATH)))
        self.assertEqual(self._on_disk(already.file.name), already_bytes)
        with doc.file.open("rb") as handle:
            self.assertEqual(handle.read(), LEGACY_BYTES)

        migration.decrypt_files(apps, None)
        self.assertEqual(self._on_disk(LEGACY_PATH), LEGACY_BYTES)

    def test_check_reports_plaintext_and_rotate_encrypts_it(self):
        self._legacy_document()
        out = StringIO()
        call_command("encryption", "check", stdout=out)
        self.assertIn("not encrypted yet", out.getvalue())

        call_command("encryption", "rotate", stdout=StringIO())

        self.assertTrue(is_encrypted(self._on_disk(LEGACY_PATH)))

    def test_rotate_then_drop_old_key(self):
        doc = self._upload()
        original = doc.file.open("rb").read()
        new_key = Fernet.generate_key().decode()
        with override_settings(FERNET_KEY=f"{new_key},{settings.FERNET_KEY}"):
            call_command("encryption", "rotate", stdout=StringIO())

        with override_settings(FERNET_KEY=new_key):
            call_command("encryption", "check", stdout=StringIO())
            self.assertEqual(doc.file.open("rb").read(), original)

    def test_unreadable_file_aborts_rotate_before_any_change(self):
        doc = self._upload()
        legacy = self._legacy_document()
        before = self._on_disk(doc.file.name)
        with (
            override_settings(FERNET_KEY=Fernet.generate_key().decode()),
            self.assertRaisesMessage(CommandError, "Nothing was changed"),
        ):
            call_command("encryption", "rotate", stdout=StringIO())
        self.assertEqual(self._on_disk(doc.file.name), before)
        self.assertEqual(self._on_disk(legacy.file.name), LEGACY_BYTES)

    def test_compress_media_skips_encrypted_documents(self):
        doc = self._upload()
        before = self._on_disk(doc.file.name)
        call_command("compress_media", "--force", stdout=StringIO())
        self.assertEqual(self._on_disk(doc.file.name), before)
