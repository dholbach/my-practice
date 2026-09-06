"""Tests for the setup_practice management command (first-run wizard)."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ..models import Practice, UserPractice

User = get_user_model()


class SetupPracticeCommandTests(TestCase):
    def test_no_input_creates_practice_with_defaults(self):
        out = StringIO()
        call_command("setup_practice", "--no-input", stdout=out)

        practice = Practice.objects.get(slug="anna-mustermann")
        self.assertEqual(practice.name, "Anna Mustermann")
        self.assertEqual(practice.email, "mail@example.com")
        self.assertFalse(practice.is_kleinunternehmer)
        self.assertIn("Created practice", out.getvalue())

    def test_assigns_practice_to_existing_superusers(self):
        superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="testpass123"
        )
        regular_user = User.objects.create_user(username="regular", password="testpass123")

        call_command("setup_practice", "--no-input", stdout=StringIO())

        practice = Practice.objects.get(slug="anna-mustermann")
        self.assertTrue(
            UserPractice.objects.filter(user=superuser, practice=practice, is_owner=True).exists()
        )
        self.assertFalse(UserPractice.objects.filter(user=regular_user, practice=practice).exists())

    def test_duplicate_slug_raises_command_error(self):
        Practice.objects.create(name="Anna Mustermann", slug="anna-mustermann", title="Existing")

        with self.assertRaises(CommandError):
            call_command("setup_practice", "--no-input", stdout=StringIO())
