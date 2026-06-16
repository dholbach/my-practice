"""
Tests for calendar_import_helpers utility (moved from views/ to utils/).
Covers: create_invoice_items_from_events, get_or_create_invoice_for_month, bill_session.
"""

from datetime import date as date_cls, datetime
from decimal import Decimal
from unittest.mock import Mock

from django.test import TestCase

from ..models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session
from ..utils.calendar_import_helpers import (
    bill_session,
    create_invoice_items_from_events,
    get_or_create_invoice_for_month,
)


def _make_practice(slug="test-cal"):
    return Practice.objects.create(name="Test Praxis", slug=slug)


def _make_client(practice, code="TC", hourly_rate_60=90):
    return Client.objects.create(
        client_code=code,
        full_name="Test Klient",
        email=f"{code.lower()}@example.com",
        hourly_rate_60=hourly_rate_60,
        practice=practice,
    )


def _make_service_type(code="therapy_60", duration=60, practice=None):
    obj, _ = ServiceType.objects.get_or_create(
        code=code,
        defaults={
            "name": f"Therapiesitzung ({duration} Min)",
            "default_duration": duration,
            "practice": practice,
        },
    )
    return obj


def _make_request(practice):
    request = Mock()
    request.current_practice = practice
    return request


class GetOrCreateInvoiceForMonthTest(TestCase):
    """Tests for get_or_create_invoice_for_month."""

    def setUp(self):
        self.practice = _make_practice("inv-month")
        self.client_obj = _make_client(self.practice)

    def test_creates_new_draft_invoice(self):
        event_dt = datetime(2026, 4, 15, 10, 0)
        invoice = get_or_create_invoice_for_month(self.client_obj, event_dt)

        self.assertEqual(invoice.status, "draft")
        self.assertEqual(invoice.client, self.client_obj)
        # Invoice.save() sets invoice_date to date.today() for new drafts
        self.assertEqual(invoice.invoice_date, date_cls.today())

    def test_returns_existing_draft(self):
        event_dt = datetime(2026, 4, 15, 10, 0)
        first = get_or_create_invoice_for_month(self.client_obj, event_dt)
        second = get_or_create_invoice_for_month(self.client_obj, event_dt)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Invoice.objects.filter(client=self.client_obj).count(), 1)

    def test_invoice_number_is_set(self):
        invoice = get_or_create_invoice_for_month(self.client_obj, datetime(2026, 4, 1))
        self.assertTrue(invoice.invoice_number, "Invoice number should be set")


class CreateInvoiceItemsFromEventsTest(TestCase):
    """Tests for create_invoice_items_from_events."""

    def setUp(self):
        self.practice = _make_practice("create-events")
        self.client_obj = _make_client(self.practice)
        self.therapy_60 = _make_service_type("therapy_60", 60)
        self.therapy_90 = _make_service_type("therapy_90", 90)
        self.request = _make_request(self.practice)

    def _make_event(self, dt=None, client=None, service_type=None, event_id="evt1"):
        dt = dt or datetime(2026, 4, 14, 14, 0)
        return {
            "id": event_id,
            "summary": f"{self.client_obj.client_code} Session",
            "start": dt,
            "matched_client": client or self.client_obj,
            "suggested_service_type_obj": service_type or self.therapy_60,
            "is_cancelled": False,
        }

    def test_creates_one_item(self):
        created, skipped, errors = create_invoice_items_from_events(
            approved_events=[self._make_event()],
            user_overrides={},
            request=self.request,
        )

        self.assertEqual(created, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(errors, [])
        self.assertEqual(InvoiceItem.objects.count(), 1)

    def test_skip_action(self):
        event = self._make_event()
        created, skipped, errors = create_invoice_items_from_events(
            approved_events=[event],
            user_overrides={"evt1": {"action": "skip"}},
            request=self.request,
        )

        self.assertEqual(created, 0)
        self.assertEqual(skipped, 1)
        self.assertEqual(InvoiceItem.objects.count(), 0)

    def test_no_client_skips_with_error(self):
        event = {
            "id": "evt-no-client",
            "summary": "Unknown Session",
            "start": datetime(2026, 4, 14, 14, 0),
            "matched_client": None,
            "suggested_service_type_obj": self.therapy_60,
        }
        created, skipped, errors = create_invoice_items_from_events(
            approved_events=[event],
            user_overrides={},
            request=self.request,
        )

        self.assertEqual(created, 0)
        self.assertEqual(skipped, 1)
        self.assertEqual(len(errors), 1)

    def test_duplicate_skipped(self):
        """Second import of same event on same date is skipped as duplicate."""
        event = self._make_event(event_id="dup1")
        create_invoice_items_from_events([event], {}, self.request)
        created, skipped, errors = create_invoice_items_from_events([event], {}, self.request)

        self.assertEqual(created, 0)
        self.assertEqual(skipped, 1)
        self.assertIn("Duplikat", errors[0])

    def test_uses_90min_rate_for_90min_service(self):
        client_90 = _make_client(self.practice, code="T9", hourly_rate_60=90)
        client_90.hourly_rate_90 = 130
        client_90.save()

        event = self._make_event(client=client_90, service_type=self.therapy_90, event_id="ev90")
        create_invoice_items_from_events([event], {}, self.request)

        item = InvoiceItem.objects.get()
        self.assertEqual(item.rate, Decimal("130"))

    def test_client_override_resolves_client(self):
        other_client = _make_client(self.practice, code="OC")
        event = {
            "id": "ev-override",
            "summary": "OC Session",
            "start": datetime(2026, 4, 15, 10, 0),
            "matched_client": None,
            "suggested_service_type_obj": self.therapy_60,
        }
        created, skipped, errors = create_invoice_items_from_events(
            approved_events=[event],
            user_overrides={"ev-override": {"client_id": other_client.pk}},
            request=self.request,
        )

        self.assertEqual(created, 1)
        item = InvoiceItem.objects.get()
        self.assertEqual(item.invoice.client, other_client)

    def test_no_rate_set_skips_with_error(self):
        penniless = Client.objects.create(
            client_code="NR",
            full_name="No Rate",
            email="no@example.com",
            practice=self.practice,
            hourly_rate_60=Decimal("0"),
        )
        event = self._make_event(client=penniless, event_id="ev-norat")
        created, skipped, errors = create_invoice_items_from_events([event], {}, self.request)

        self.assertEqual(created, 0)
        self.assertEqual(skipped, 1)
        self.assertIn("hourly rate", errors[0])

    def test_session_record_created(self):
        create_invoice_items_from_events([self._make_event()], {}, self.request)
        self.assertEqual(Session.objects.count(), 1)
        session = Session.objects.get()
        self.assertEqual(session.session_date, datetime(2026, 4, 14).date())


class BillSessionTest(TestCase):
    """Tests for bill_session."""

    def setUp(self):
        self.practice = _make_practice("bill-session")
        self.client_obj = _make_client(self.practice)
        self.therapy_60 = _make_service_type("therapy_60", 60)

        # Create a session directly
        self.session = Session.objects.create(
            client=self.client_obj,
            session_date=datetime(2026, 4, 10).date(),
            duration=60,
        )

    def test_bills_unbilled_session(self):
        success, msg = bill_session(self.session, self.practice)
        self.assertTrue(success, msg)
        self.assertEqual(InvoiceItem.objects.count(), 1)

    def test_guard_against_double_billing(self):
        bill_session(self.session, self.practice)
        success, msg = bill_session(self.session, self.practice)

        self.assertFalse(success)
        self.assertIn("abgerechnet", msg)
        self.assertEqual(InvoiceItem.objects.count(), 1)  # still only one

    def test_no_service_type_fails(self):
        """If no service type exists returns failure message."""
        ServiceType.objects.filter(code="therapy_60").delete()
        success, msg = bill_session(self.session, self.practice)
        self.assertFalse(success)

    def test_no_rate_fails(self):
        penniless_session = Session.objects.create(
            client=Client.objects.create(
                client_code="PR",
                full_name="Penniless",
                email="p@example.com",
                practice=self.practice,
                hourly_rate_60=Decimal("0"),
            ),
            session_date=datetime(2026, 4, 11).date(),
            duration=60,
        )
        success, msg = bill_session(penniless_session, self.practice)
        self.assertFalse(success)
        self.assertIn("Stundensatz", msg)
