"""
Tests for the session-log reminders and thresholds on the client pages.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import (
    Client,
    Invoice,
    InvoiceItem,
    ServiceType,
    Session,
    allow_issued_invoice_writes,
)
from ..utils.tag_helpers import SESSION_LOG_MIN_DURATION
from .test_helpers import create_test_practice, create_test_user, select_practice


class ReminderUrgencyTest(TestCase):
    """
    reminder_urgency (client_detail_builder._build_billing_context) should be
    driven by practice.overdue_after_days / payment_terms_days rather than
    hardcoded 30/14-day cutoffs (#195).
    """

    def setUp(self):
        self.practice = create_test_practice(name="Test Practice", slug="views_client-reminder")
        self.user = create_test_user(self.practice, username="testuser2", password="testpass123")
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser2", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="RU",
            full_name="Reminder Client",
            email="reminder@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

    def _make_sent_invoice(self, days_old: int) -> None:
        Invoice.objects.create(
            client=self.test_client,
            invoice_number=f"RU-{days_old}",
            invoice_date=date.today() - timedelta(days=days_old),
            total=Decimal("90.00"),
            status="sent",
            practice=self.practice,
        )

    def _get_urgency(self):
        response = self.client_instance.get(
            reverse("client_detail", kwargs={"pk": self.test_client.pk})
        )
        return response.context["reminder_urgency"]

    def test_no_sent_invoices_is_none(self):
        self.assertIsNone(self._get_urgency())

    def test_default_thresholds_match_previous_hardcoded_30_and_14_days(self):
        self._make_sent_invoice(days_old=31)
        self.assertEqual(self._get_urgency(), "high")

    def test_custom_overdue_threshold_is_respected(self):
        """An invoice at 15 days is 'medium' by default but 'high' with a lower threshold."""
        self._make_sent_invoice(days_old=15)
        self.assertEqual(self._get_urgency(), "medium")

        self.practice.overdue_after_days = 10
        self.practice.save()
        self.assertEqual(self._get_urgency(), "high")

    def test_custom_payment_terms_threshold_is_respected(self):
        """An invoice at 10 days is 'low' by default but 'medium' with a lower payment term."""
        self._make_sent_invoice(days_old=10)
        self.assertEqual(self._get_urgency(), "low")

        self.practice.payment_terms_days = 5
        self.practice.save()
        self.assertEqual(self._get_urgency(), "medium")


class NoLogNeededSessionIdsTest(TestCase):
    """
    Regression tests for no_log_needed_session_ids in client_detail context.

    When client.cancellation_fee equals the regular session rate, the old
    rate-based detection incorrectly suppressed + Protokoll on all billed
    sessions. Now detection uses service_type__name__icontains='cancel'.
    """

    @allow_issued_invoice_writes()
    def setUp(self):
        self.practice = create_test_practice(name="Test Practice", slug="no-log-test")
        self.user = create_test_user(self.practice, username="nluser", password="testpass123")
        self.http = TestClient()
        self.http.login(username="nluser", password="testpass123")

        # Both service types billed at the SAME rate — the historical bug trigger
        self.stype_regular = ServiceType.objects.create(
            code="regular",
            name="60-Min Therapy Session",
            practice=self.practice,
        )
        self.stype_cancel = ServiceType.objects.create(
            code="cancel",
            name="Cancellation Fee",
            practice=self.practice,
        )

        # Client with cancellation_fee == regular session rate
        self.pat = Client.objects.create(
            client_code="NL1",
            full_name="Max Mustermann",
            email="nl@example.com",
            hourly_rate_60=Decimal("80.00"),
            cancellation_fee=Decimal("80.00"),
            practice=self.practice,
        )

        invoice = Invoice.objects.create(
            client=self.pat,
            invoice_number="NL-1",
            invoice_date=date.today() - timedelta(days=30),
            status="paid",
            total=Decimal("240.00"),
            practice=self.practice,
        )

        # Regular session billed at 80.00 — must NOT end up in no_log_needed
        self.regular_session = Session.objects.create(
            client=self.pat,
            session_date=date.today() - timedelta(days=20),
            duration=60,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.stype_regular,
            session=self.regular_session,
            rate=Decimal("80.00"),
            quantity=Decimal("1.00"),
            total=Decimal("80.00"),
        )

        # Cancellation session billed at 80.00 with Cancellation Fee type — MUST be in no_log_needed
        self.cancel_session = Session.objects.create(
            client=self.pat,
            session_date=date.today() - timedelta(days=10),
            duration=60,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.stype_cancel,
            session=self.cancel_session,
            rate=Decimal("80.00"),
            quantity=Decimal("1.00"),
            total=Decimal("80.00"),
        )

        # Explicitly cancelled session — must be in no_log_needed regardless of service type
        self.cancelled_session = Session.objects.create(
            client=self.pat,
            session_date=date.today() - timedelta(days=5),
            duration=60,
            cancelled=True,
        )

    def _get_no_log_ids(self):
        response = self.http.get(reverse("client_detail", kwargs={"pk": self.pat.pk}))
        self.assertEqual(response.status_code, 200)
        return response.context["no_log_needed_session_ids"]

    def test_regular_session_not_in_no_log_needed(self):
        """Regular session at same rate as cancellation_fee must NOT be suppressed."""
        ids = self._get_no_log_ids()
        self.assertNotIn(self.regular_session.pk, ids)

    def test_cancellation_fee_session_in_no_log_needed(self):
        """Session billed with 'Cancellation Fee' service type must be suppressed."""
        ids = self._get_no_log_ids()
        self.assertIn(self.cancel_session.pk, ids)

    def test_explicitly_cancelled_session_in_no_log_needed(self):
        """Session with cancelled=True must always be suppressed."""
        ids = self._get_no_log_ids()
        self.assertIn(self.cancelled_session.pk, ids)


class SessionLogDurationThresholdTest(TestCase):
    """
    Regression tests for the SESSION_LOG_MIN_DURATION threshold.

    Short sessions (duration <= SESSION_LOG_MIN_DURATION, typically intro calls
    imported from Google Calendar at ~20-30 min) must NOT cause the 📝 indicator
    on the client list.  Only sessions longer than the threshold need a log entry.
    """

    def setUp(self):
        self.practice = create_test_practice(name="Test Practice", slug="log-duration-test")
        self.user = create_test_user(self.practice, username="duruser", password="testpass123")
        self.http = TestClient()
        self.http.login(username="duruser", password="testpass123")
        select_practice(self.http, self.practice)

        self.pat = Client.objects.create(
            client_code="DT1",
            full_name="Anna Schmidt",
            email="dur@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
            active=True,
        )

        # Place both sessions well within the window (5 days ago)
        self.recent_date = date.today() - timedelta(days=5)

    def _clients_needing_log(self):
        response = self.http.get(reverse("client_list"))
        self.assertEqual(response.status_code, 200)
        return response.context.get("clients_needing_log", set())

    def test_short_session_does_not_trigger_log_indicator(self):
        """A session at exactly SESSION_LOG_MIN_DURATION minutes must NOT flag the client."""
        Session.objects.create(
            client=self.pat,
            session_date=self.recent_date,
            duration=SESSION_LOG_MIN_DURATION,  # at threshold — should be excluded
            cancelled=False,
        )
        self.assertNotIn(self.pat.pk, self._clients_needing_log())

    def test_long_session_without_log_triggers_indicator(self):
        """A session longer than SESSION_LOG_MIN_DURATION with no log must flag the client."""
        Session.objects.create(
            client=self.pat,
            session_date=self.recent_date,
            duration=SESSION_LOG_MIN_DURATION + 1,  # just above threshold
            cancelled=False,
        )
        self.assertIn(self.pat.pk, self._clients_needing_log())

    def test_short_session_below_threshold_does_not_trigger(self):
        """A session well below the threshold (e.g. 20 min) must NOT flag the client."""
        Session.objects.create(
            client=self.pat,
            session_date=self.recent_date,
            duration=20,
            cancelled=False,
        )
        self.assertNotIn(self.pat.pk, self._clients_needing_log())
