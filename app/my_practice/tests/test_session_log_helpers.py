"""Tests for session_log_helpers: duration parsing, session lookup, the billed freeze."""

from datetime import date, time
from decimal import Decimal

from django.test import TestCase, override_settings

from ..models import Client, Invoice, InvoiceItem, ServiceType, Session
from ..utils.session_log_helpers import (
    MAX_SESSION_MINUTES,
    find_or_create_session,
    is_session_billed,
    parse_duration,
    set_session_duration,
)
from .test_helpers import create_test_practice

TEST_FERNET_KEY = "7zIJPIlZkdMSPifNsPuNBjIAIqiUkFHmRJN8HGG8ytQ="  # gitleaks:allow


class ParseDurationTests(TestCase):
    def test_accepts_one_minute_up_to_a_day(self):
        self.assertEqual(parse_duration("1"), 1)
        self.assertEqual(parse_duration(" 90 "), 90)
        self.assertEqual(parse_duration(str(MAX_SESSION_MINUTES)), MAX_SESSION_MINUTES)

    def test_rejects_zero_negative_over_a_day_and_text(self):
        for raw in ("0", "-5", str(MAX_SESSION_MINUTES + 1), "abc", "", None):
            self.assertIsNone(parse_duration(raw), raw)


class SessionFixtureMixin:
    def setUp(self):
        self.practice = create_test_practice(slug="session-log-helpers-1")
        self.client_obj = Client.objects.create(
            client_code="XX-1",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        self.day = date(2026, 3, 20)

    def _bill(self, session):
        service = ServiceType.objects.create(
            code="individual", name_en="Individual Session", name_de="Einzelsitzung"
        )
        invoice = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="INV-001",
            invoice_date=self.day,
            practice=self.practice,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=service,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class FindOrCreateSessionTests(SessionFixtureMixin, TestCase):
    def test_creates_a_session_with_the_duration_when_none_exists(self):
        session = find_or_create_session(self.client_obj, self.day, 45)
        self.assertEqual((session.session_date, session.duration), (self.day, 45))
        self.assertEqual(Session.objects.filter(client=self.client_obj).count(), 1)

    def test_reuses_the_existing_session_without_changing_it(self):
        existing = Session.objects.create(
            client=self.client_obj, session_date=self.day, duration=60
        )
        self.assertEqual(find_or_create_session(self.client_obj, self.day, 45), existing)
        existing.refresh_from_db()
        self.assertEqual(existing.duration, 60)

    def test_prefers_the_unlogged_session_of_several_on_one_day(self):
        from ..models import SessionLog

        morning = Session.objects.create(
            client=self.client_obj, session_date=self.day, session_time=time(9, 0), duration=60
        )
        afternoon = Session.objects.create(
            client=self.client_obj, session_date=self.day, session_time=time(15, 0), duration=60
        )
        SessionLog.objects.create(session=morning)
        self.assertEqual(find_or_create_session(self.client_obj, self.day, 60), afternoon)

    def test_skips_a_cancelled_twin_while_a_live_session_exists(self):
        Session.objects.create(
            client=self.client_obj,
            session_date=self.day,
            session_time=time(9, 0),
            duration=60,
            cancelled=True,
        )
        live = Session.objects.create(
            client=self.client_obj, session_date=self.day, session_time=time(10, 0), duration=60
        )
        self.assertEqual(find_or_create_session(self.client_obj, self.day, 60), live)

    def test_falls_back_to_a_cancelled_session_when_it_is_the_only_one(self):
        only = Session.objects.create(
            client=self.client_obj, session_date=self.day, duration=60, cancelled=True
        )
        self.assertEqual(find_or_create_session(self.client_obj, self.day, 60), only)


class SetSessionDurationTests(SessionFixtureMixin, TestCase):
    def test_saves_the_new_duration(self):
        session = Session.objects.create(client=self.client_obj, session_date=self.day, duration=60)
        self.assertTrue(set_session_duration(session, 90))
        session.refresh_from_db()
        self.assertEqual(session.duration, 90)
        self.assertFalse(is_session_billed(session))

    def test_refuses_once_the_session_is_billed(self):
        session = Session.objects.create(client=self.client_obj, session_date=self.day, duration=60)
        self._bill(session)
        self.assertTrue(is_session_billed(session))
        self.assertFalse(set_session_duration(session, 90))
        session.refresh_from_db()
        self.assertEqual(session.duration, 60)
