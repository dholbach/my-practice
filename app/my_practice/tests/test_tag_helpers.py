"""
Tests for get_sessions_missing_log() (utils/tag_helpers.py).

Ported from the old missing-session-log ClientTag tests when that tag was
retired in favor of per-session Focus Queue tasks (P-050) — the detection
rule itself is unchanged and still shared by update_client_tags and
sync_focus_queue_tasks, so these edge cases (several of which were real
production bugs) still need covering. Covers the cases that must not be
conflated:

  1. Regular session (no log, within window)        → included
  2. Cancelled session (Session.cancelled=True)      → excluded
  3. Cancellation-fee session (billed "cancel" type) → excluded
  4. Session outside the window                      → excluded
  5. Session with a log already                      → excluded
  6. Session at/under SESSION_LOG_MIN_DURATION        → excluded
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from ..models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session, SessionLog
from ..utils.tag_helpers import (
    SESSION_LOG_MIN_DURATION,
    SESSION_LOG_WINDOW_DAYS,
    get_sessions_missing_log,
)


class GetSessionsMissingLogTest(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="sessions-missing-log-test",
            title="Dr. Test",
            email="test@practice.example",
            city="Berlin",
        )
        self.client_obj = Client.objects.create(
            client_code="ZZ-1",
            full_name="Max Mustermann",
            email="max@example.com",
            practice=self.practice,
            active=True,
        )
        self.today = timezone.now().date()
        self.recent = self.today - timedelta(days=SESSION_LOG_WINDOW_DAYS - 2)
        self.old = self.today - timedelta(days=SESSION_LOG_WINDOW_DAYS + 5)

    def _session_ids(self):
        return set(get_sessions_missing_log().values_list("id", flat=True))

    def test_regular_session_is_included(self):
        session = Session.objects.create(
            client=self.client_obj,
            session_date=self.recent,
            duration=SESSION_LOG_MIN_DURATION + 10,
            cancelled=False,
        )
        self.assertIn(session.id, self._session_ids())

    def test_cancelled_session_is_excluded(self):
        session = Session.objects.create(
            client=self.client_obj,
            session_date=self.recent,
            duration=SESSION_LOG_MIN_DURATION + 10,
            cancelled=True,
        )
        self.assertNotIn(session.id, self._session_ids())

    def test_cancellation_fee_session_is_excluded(self):
        """
        Session billed with a 'cancel' service type — has cancelled=False so
        it passes the basic filter, but the UI hides '+ Protokoll' for it;
        this was a real stale-tag bug on a production client.
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
        self.assertNotIn(session.id, self._session_ids())

    def test_session_outside_window_is_excluded(self):
        session = Session.objects.create(
            client=self.client_obj,
            session_date=self.old,
            duration=SESSION_LOG_MIN_DURATION + 10,
            cancelled=False,
        )
        self.assertNotIn(session.id, self._session_ids())

    def test_session_with_log_is_excluded(self):
        session = Session.objects.create(
            client=self.client_obj,
            session_date=self.recent,
            duration=SESSION_LOG_MIN_DURATION + 10,
            cancelled=False,
        )
        SessionLog.objects.create(session=session)
        self.assertNotIn(session.id, self._session_ids())

    def test_short_session_is_excluded(self):
        session = Session.objects.create(
            client=self.client_obj,
            session_date=self.recent,
            duration=SESSION_LOG_MIN_DURATION,
            cancelled=False,
        )
        self.assertNotIn(session.id, self._session_ids())

    def test_inactive_client_session_is_excluded(self):
        self.client_obj.active = False
        self.client_obj.save()
        session = Session.objects.create(
            client=self.client_obj,
            session_date=self.recent,
            duration=SESSION_LOG_MIN_DURATION + 10,
            cancelled=False,
        )
        self.assertNotIn(session.id, self._session_ids())

    def test_scoped_to_practice(self):
        other_practice = Practice.objects.create(name="Other", title="Other Therapeutin")
        other_client = Client.objects.create(
            client_code="ZZ-2",
            full_name="Other Client",
            practice=other_practice,
            active=True,
        )
        session = Session.objects.create(
            client=other_client,
            session_date=self.recent,
            duration=SESSION_LOG_MIN_DURATION + 10,
            cancelled=False,
        )
        self.assertNotIn(session.id, {s.id for s in get_sessions_missing_log(self.practice)})
        self.assertIn(session.id, {s.id for s in get_sessions_missing_log(other_practice)})
