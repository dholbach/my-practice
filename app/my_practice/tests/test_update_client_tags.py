"""
Tests for the update_client_tags management command (no-next-session,
incomplete-intake tags; missing-session-log was retired in favor of
per-session Focus Queue tasks — see test_tag_helpers.py for that coverage).
"""

from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ..models import Client, ClientTag, Practice, Session, UserPractice
from ..utils.tag_helpers import RECENT_ACTIVITY_WINDOW_DAYS, sync_no_next_session_tag


class UpdateClientTagsTestBase(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="update-tags-test",
            title="Dr. Test",
            email="test@practice.example",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="tagtestuser", password="pass")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

        self.client_obj = Client.objects.create(
            client_code="ZZ-1",
            full_name="Max Mustermann",
            email="max@example.com",
            practice=self.practice,
            active=True,
        )

        self.today = timezone.now().date()

    def _run(self):
        call_command("update_client_tags", stdout=StringIO(), stderr=StringIO())

    def _has_tag(self, slug):
        return self.client_obj.tags.filter(slug=slug).exists()


class SyncNoNextSessionTagTest(UpdateClientTagsTestBase):
    """Tests for the per-client sync_no_next_session_tag helper."""

    def setUp(self):
        super().setUp()
        self.tag = ClientTag.objects.create(
            slug="no-next-session",
            name="no-next-session",
            color="orange",
            category="attention",
            is_system=True,
        )

    def _has_no_next_tag(self):
        return self._has_tag("no-next-session")

    def test_removes_tag_when_future_session_exists(self):
        self.client_obj.tags.add(self.tag)
        Session.objects.create(
            client=self.client_obj,
            session_date=self.today + timedelta(days=7),
            duration=60,
            cancelled=False,
        )
        self.assertIs(sync_no_next_session_tag(self.client_obj), False)
        self.assertFalse(self._has_no_next_tag())

    def test_adds_tag_for_recently_active_client_without_future_session(self):
        Session.objects.create(
            client=self.client_obj,
            session_date=self.today - timedelta(days=10),
            duration=60,
            cancelled=False,
        )
        self.assertIs(sync_no_next_session_tag(self.client_obj), True)
        self.assertTrue(self._has_no_next_tag())

    def test_does_not_add_tag_when_not_recently_active(self):
        Session.objects.create(
            client=self.client_obj,
            session_date=self.today - timedelta(days=RECENT_ACTIVITY_WINDOW_DAYS + 10),
            duration=60,
            cancelled=False,
        )
        self.assertIsNone(sync_no_next_session_tag(self.client_obj))
        self.assertFalse(self._has_no_next_tag())

    def test_cancelled_future_session_does_not_count(self):
        Session.objects.create(
            client=self.client_obj,
            session_date=self.today - timedelta(days=10),
            duration=60,
            cancelled=False,
        )
        Session.objects.create(
            client=self.client_obj,
            session_date=self.today + timedelta(days=7),
            duration=60,
            cancelled=True,
        )
        self.assertIs(sync_no_next_session_tag(self.client_obj), True)
        self.assertTrue(self._has_no_next_tag())

    def test_removes_tag_from_inactive_client(self):
        self.client_obj.active = False
        self.client_obj.save()
        self.client_obj.tags.add(self.tag)
        self.assertIs(sync_no_next_session_tag(self.client_obj), False)
        self.assertFalse(self._has_no_next_tag())

    def test_noop_when_tag_does_not_exist(self):
        self.tag.delete()
        self.assertIsNone(sync_no_next_session_tag(self.client_obj))
