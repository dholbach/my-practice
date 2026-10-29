"""Tests for field encryption: coverage, key rotation, wrong-key errors, migration."""

import importlib
from io import StringIO

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.checks import run_checks
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings

from ..fields import EncryptionKeyError, encrypted_fields
from ..models import Client, ClientInquiry, GoogleCalendarToken, Practice

# The fields that must never be stored in clear. A field leaving this set is a
# privacy regression a reviewer cannot see: the page still renders the same.
REQUIRED_ENCRYPTED = {
    ("Client", "notes"),
    ("ClientInquiry", "notes"),
    ("ClientInquiry", "initial_contact_notes"),
    ("ClientProfile", "intake_notes"),
    ("ClientProfile", "case_notes"),
    ("ClientProfile", "arbeitsdiagnose"),
    ("SessionLog", "content"),
    ("SessionLog", "interventions"),
    ("SessionLog", "therapist_reflection"),
    ("SessionLog", "next_session_ideas"),
    ("SupervisionItem", "content"),
    ("SupervisionItem", "resolution_notes"),
    ("ClientNote", "content"),
    ("GoogleCalendarToken", "token"),
    ("GoogleCalendarToken", "refresh_token"),
    ("GoogleCalendarToken", "client_secret"),
}


def _raw(model, pk, field):
    column = model._meta.get_field(field).column
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {column} FROM {model._meta.db_table} WHERE id = %s",  # noqa: S608
            [pk],
        )
        return cursor.fetchone()[0]


class EncryptionTestBase(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(name="Test Practice")
        self.client_obj = Client.objects.create(
            practice=self.practice,
            client_code="XX-1",
            full_name="Max Mustermann",
            notes="Sleeps badly since the accident",
        )


class EncryptedFieldCoverageTests(TestCase):
    def test_sensitive_fields_are_encrypted(self):
        actual = {(model.__name__, name) for model, name in encrypted_fields()}
        self.assertEqual(REQUIRED_ENCRYPTED - actual, set())


class EncryptedStorageTests(EncryptionTestBase):
    def test_client_notes_stored_as_ciphertext(self):
        raw = _raw(Client, self.client_obj.pk, "notes")
        self.assertTrue(raw.startswith("gAAAAA"))
        self.assertNotIn("accident", raw)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.notes, "Sleeps badly since the accident")

    def test_inquiry_notes_stored_as_ciphertext(self):
        inquiry = ClientInquiry.objects.create(
            practice=self.practice,
            full_name="Anna Schmidt",
            notes="Panic attacks",
            initial_contact_notes="Referred by GP",
        )
        self.assertTrue(_raw(ClientInquiry, inquiry.pk, "notes").startswith("gAAAAA"))
        self.assertTrue(
            _raw(ClientInquiry, inquiry.pk, "initial_contact_notes").startswith("gAAAAA")
        )

    def test_calendar_credentials_stored_as_ciphertext(self):
        token = GoogleCalendarToken.objects.create(
            practice=self.practice,
            token="access-token-value",
            refresh_token="refresh-token-value",
            client_id="client-id",
            client_secret="client-secret-value",
        )
        for field in ("token", "refresh_token", "client_secret"):
            self.assertTrue(_raw(GoogleCalendarToken, token.pk, field).startswith("gAAAAA"))
        token.refresh_from_db()
        self.assertEqual(token.client_secret, "client-secret-value")

    def test_blank_values_stay_blank(self):
        client = Client.objects.create(practice=self.practice, client_code="YY-2")
        self.assertEqual(_raw(Client, client.pk, "notes"), "")


class KeyRotationTests(EncryptionTestBase):
    def test_wrong_key_names_the_field(self):
        with (
            override_settings(FERNET_KEY=Fernet.generate_key().decode()),
            self.assertRaisesMessage(EncryptionKeyError, "Client.notes"),
        ):
            Client.objects.get(pk=self.client_obj.pk)

    def test_old_key_still_decrypts_behind_a_new_one(self):
        keys = f"{Fernet.generate_key().decode()},{settings.FERNET_KEY}"
        with override_settings(FERNET_KEY=keys):
            self.client_obj.refresh_from_db()
            self.assertEqual(self.client_obj.notes, "Sleeps badly since the accident")

    def test_rotate_then_drop_old_key(self):
        new_key = Fernet.generate_key().decode()
        with override_settings(FERNET_KEY=f"{new_key},{settings.FERNET_KEY}"):
            call_command("encryption", "rotate", stdout=StringIO())

        with override_settings(FERNET_KEY=new_key):
            self.client_obj.refresh_from_db()
            self.assertEqual(self.client_obj.notes, "Sleeps badly since the accident")
            call_command("encryption", "check", stdout=StringIO())

    def test_rotate_does_not_touch_updated_at(self):
        before = Client.objects.get(pk=self.client_obj.pk).updated_at
        call_command("encryption", "rotate", stdout=StringIO())
        self.assertEqual(Client.objects.get(pk=self.client_obj.pk).updated_at, before)

    def test_check_fails_when_a_key_is_missing(self):
        with (
            override_settings(FERNET_KEY=Fernet.generate_key().decode()),
            self.assertRaisesMessage(CommandError, "cannot be opened"),
        ):
            call_command("encryption", "check", stdout=StringIO())

    def test_rotate_refuses_and_changes_nothing_without_the_old_key(self):
        before = _raw(Client, self.client_obj.pk, "notes")
        with (
            override_settings(FERNET_KEY=Fernet.generate_key().decode()),
            self.assertRaises(CommandError),
        ):
            call_command("encryption", "rotate", stdout=StringIO())
        self.assertEqual(_raw(Client, self.client_obj.pk, "notes"), before)


class MigrationTests(EncryptionTestBase):
    def test_existing_plaintext_rows_are_encrypted_once(self):
        migration = importlib.import_module(
            "my_practice.migrations.0005_encrypt_notes_and_calendar_credentials"
        )
        already_encrypted = _raw(Client, self.client_obj.pk, "notes")
        plain = Client.objects.create(practice=self.practice, client_code="AB-3")
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {Client._meta.db_table} SET notes = %s WHERE id = %s",  # noqa: S608
                ["Written before encryption", plain.pk],
            )

        from django.apps import apps

        with connection.schema_editor() as editor:
            migration.encrypt_existing(apps, editor)

        plain.refresh_from_db()
        self.assertEqual(plain.notes, "Written before encryption")
        self.assertTrue(_raw(Client, plain.pk, "notes").startswith("gAAAAA"))
        # A row that was already ciphertext is left as it was, not double-encrypted.
        self.assertEqual(_raw(Client, self.client_obj.pk, "notes"), already_encrypted)


class FernetKeyCheckTests(TestCase):
    def _ids(self, **kwargs):
        return {message.id for message in run_checks(**kwargs)}

    def test_configured_key_passes(self):
        ids = self._ids(include_deployment_checks=True)
        self.assertFalse({"my_practice.W001", "my_practice.E001", "my_practice.E002"} & ids)

    @override_settings(FERNET_KEY="")
    def test_missing_key_warns_and_fails_deploy_check(self):
        self.assertIn("my_practice.W001", self._ids())
        self.assertIn("my_practice.E002", self._ids(include_deployment_checks=True))

    @override_settings(FERNET_KEY="not-a-key")
    def test_malformed_key_is_an_error(self):
        self.assertIn("my_practice.E001", self._ids())


class SecretKeyCheckTests(TestCase):
    def _ids(self):
        return {message.id for message in run_checks()}

    @override_settings(DEBUG=False, RUNNING_TESTS=False, SECRET_KEY="django-insecure-dev-key")
    def test_placeholder_key_without_debug_is_an_error(self):
        self.assertIn("my_practice.E003", self._ids())

    @override_settings(DEBUG=True, RUNNING_TESTS=False, SECRET_KEY="django-insecure-dev-key")
    def test_placeholder_key_is_fine_in_debug(self):
        self.assertNotIn("my_practice.E003", self._ids())

    @override_settings(DEBUG=False, RUNNING_TESTS=False, SECRET_KEY="a-real-generated-key")
    def test_real_key_passes(self):
        self.assertNotIn("my_practice.E003", self._ids())
