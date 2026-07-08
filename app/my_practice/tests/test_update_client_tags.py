"""
Tests for the update_client_tags management command.

Focuses on the missing-session-log tag, which has had several correctness
fixes. Covers the three cases that must not be conflated:

  1. Regular session (no log, within window)  → tag fires
  2. Cancelled session (Session.cancelled=True) → no tag
  3. Cancellation-fee session (billed with "cancel" service type) → no tag
  4. Session outside the window → no tag
  5. Session with a log already → no tag
"""

from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ..models import (
    Client,
    ClientTag,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
    SessionLog,
    UserPractice,
)
from ..utils.tag_helpers import (
    RECENT_ACTIVITY_WINDOW_DAYS,
    SESSION_LOG_MIN_DURATION,
    SESSION_LOG_WINDOW_DAYS,
    sync_no_next_session_tag,
)


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
        # A date inside the SESSION_LOG_WINDOW_DAYS window
        self.recent = self.today - timedelta(days=SESSION_LOG_WINDOW_DAYS - 2)
        # A date outside the window
        self.old = self.today - timedelta(days=SESSION_LOG_WINDOW_DAYS + 5)

    def _run(self):
        call_command("update_client_tags", stdout=StringIO(), stderr=StringIO())

    def _has_tag(self, slug):
        return self.client_obj.tags.filter(slug=slug).exists()

    def _missing_log_tag(self):
        return self._has_tag("missing-session-log")


class MissingSessionLogTagTest(UpdateClientTagsTestBase):
    def test_regular_session_triggers_tag(self):
        """Non-cancelled session without a log within the window → tag fires."""
        Session.objects.create(
            client=self.client_obj,
            session_date=self.recent,
            duration=SESSION_LOG_MIN_DURATION + 10,
            cancelled=False,
        )
        self._run()
        self.assertTrue(self._missing_log_tag())

    def test_cancelled_session_does_not_trigger_tag(self):
        """Session.cancelled=True → tag must not fire."""
        Session.objects.create(
            client=self.client_obj,
            session_date=self.recent,
            duration=SESSION_LOG_MIN_DURATION + 10,
            cancelled=True,
        )
        self._run()
        self.assertFalse(self._missing_log_tag())

    def test_cancellation_fee_session_does_not_trigger_tag(self):
        """Session billed with a 'cancel' service type → tag must not fire.

        This is the case that caused a stale tag on a real client: the session
        has cancelled=False so it passes the basic filter, but the UI correctly
        hides the '+ Protokoll' button for it — the tag logic must match.
        """
        cancel_type = ServiceType.objects.create(code="cancel_fee", name="Cancellation Fee")
        invoice = Invoice.objects.create(
            client=self.client_obj,
            invoice_date=self.recent,
            practice=self.practice,
        )
        session = Session.objects.create(
            client=self.client_obj,
            session_date=self.recent,
            duration=SESSION_LOG_MIN_DURATION + 10,
            cancelled=False,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            session=session,
            service_type=cancel_type,
            quantity=1,
            rate=80,
        )
        self._run()
        self.assertFalse(self._missing_log_tag())

    def test_session_outside_window_does_not_trigger_tag(self):
        """Session older than SESSION_LOG_WINDOW_DAYS → tag must not fire."""
        Session.objects.create(
            client=self.client_obj,
            session_date=self.old,
            duration=SESSION_LOG_MIN_DURATION + 10,
            cancelled=False,
        )
        self._run()
        self.assertFalse(self._missing_log_tag())

    def test_session_with_log_does_not_trigger_tag(self):
        """Session that already has a SessionLog → tag must not fire."""
        session = Session.objects.create(
            client=self.client_obj,
            session_date=self.recent,
            duration=SESSION_LOG_MIN_DURATION + 10,
            cancelled=False,
        )
        SessionLog.objects.create(session=session)
        self._run()
        self.assertFalse(self._missing_log_tag())

    def test_short_session_does_not_trigger_tag(self):
        """Session at or below SESSION_LOG_MIN_DURATION → tag must not fire."""
        Session.objects.create(
            client=self.client_obj,
            session_date=self.recent,
            duration=SESSION_LOG_MIN_DURATION,
            cancelled=False,
        )
        self._run()
        self.assertFalse(self._missing_log_tag())

    def test_tag_removed_once_log_exists(self):
        """Tag is cleared on next run once a log is added."""
        session = Session.objects.create(
            client=self.client_obj,
            session_date=self.recent,
            duration=SESSION_LOG_MIN_DURATION + 10,
            cancelled=False,
        )
        # First run: tag fires
        self._run()
        self.assertTrue(self._missing_log_tag())

        # Add a log and re-run: tag is cleared
        SessionLog.objects.create(session=session)
        self._run()
        self.assertFalse(self._missing_log_tag())

    def test_inactive_client_never_gets_tag(self):
        """Inactive clients are exempt from all system tags."""
        self.client_obj.active = False
        self.client_obj.save()
        Session.objects.create(
            client=self.client_obj,
            session_date=self.recent,
            duration=SESSION_LOG_MIN_DURATION + 10,
            cancelled=False,
        )
        self._run()
        self.assertFalse(self._missing_log_tag())


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
