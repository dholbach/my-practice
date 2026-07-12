"""Tests for billing_helpers: session-to-InvoiceItem creation utilities."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from ..models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session
from ..utils.billing_helpers import (
    build_service_type_map,
    create_invoice_item_for_session,
    is_session_already_billed,
    resolve_session_rate,
)


def _make_practice():
    return Practice.objects.create(
        name="Billing Test Practice",
        slug="billing-helpers-test",
        email="billing@example.com",
    )


def _make_service_types(practice):
    st60 = ServiceType.objects.create(
        code="therapy_60",
        name="60-Min Therapy",
        default_duration=60,
        practice=practice,
    )
    st90 = ServiceType.objects.create(
        code="therapy_90",
        name="90-Min Therapy",
        default_duration=90,
        practice=practice,
    )
    st_free = ServiceType.objects.create(
        code="therapy_free",
        name="Free Consultation",
        default_duration=20,
        practice=practice,
    )
    st15 = ServiceType.objects.create(
        code="checkin_15",
        name="15-Min Check-In",
        default_duration=15,
        practice=practice,
    )
    return st60, st90, st_free, st15


def _make_client(practice):
    return Client.objects.create(
        client_code="BH",
        full_name="Max Mustermann",
        practice=practice,
        hourly_rate_60=Decimal("100.00"),
        hourly_rate_90=Decimal("150.00"),
    )


def _make_invoice(client, status=Invoice.Status.DRAFT):
    return Invoice.objects.create(
        practice=client.practice,
        client=client,
        invoice_number="BH-1",
        invoice_date=date.today(),
        status=status,
    )


def _make_session(client, duration=60):
    return Session.objects.create(
        client=client,
        session_date=date.today(),
        duration=duration,
    )


class BuildServiceTypeMapTests(TestCase):
    def setUp(self):
        self.practice = _make_practice()
        self.st60, self.st90, self.st_free, self.st15 = _make_service_types(self.practice)

    def test_maps_duration_to_service_type(self):
        m = build_service_type_map(self.practice)
        self.assertEqual(m[60], self.st60)
        self.assertEqual(m[90], self.st90)
        self.assertEqual(m[20], self.st_free)

    def test_deterministic_on_duplicate_duration(self):
        # Dict is built in ascending code order; the last entry (higher code) wins.
        ServiceType.objects.create(
            code="aaa_therapy_60",
            name="Earlier code",
            default_duration=60,
            practice=self.practice,
        )
        m = build_service_type_map(self.practice)
        # "therapy_60" > "aaa_therapy_60" alphabetically → it wins.
        self.assertEqual(m[60].code, "therapy_60")

    def test_includes_global_service_types(self):
        global_st = ServiceType.objects.create(
            code="zzz_global",
            name="Global Type",
            default_duration=45,
            practice=None,
        )
        m = build_service_type_map(self.practice)
        self.assertEqual(m[45], global_st)


class ResolveSessionRateTests(TestCase):
    def setUp(self):
        self.practice = _make_practice()
        self.st60, self.st90, self.st_free, self.st15 = _make_service_types(self.practice)
        self.client = _make_client(self.practice)

    def test_therapy_free_returns_zero(self):
        self.assertEqual(resolve_session_rate(self.client, self.st_free), Decimal("0"))

    def test_60min_uses_hourly_rate_60(self):
        self.assertEqual(resolve_session_rate(self.client, self.st60), Decimal("100.00"))

    def test_90min_uses_hourly_rate_90(self):
        self.assertEqual(resolve_session_rate(self.client, self.st90), Decimal("150.00"))

    def test_90min_falls_back_to_60_when_90_is_zero(self):
        # hourly_rate_90 = 0 is falsy → falls back to hourly_rate_60.
        self.client.hourly_rate_90 = Decimal("0")
        self.client.save()
        self.assertEqual(resolve_session_rate(self.client, self.st90), Decimal("100.00"))

    def test_15min_is_prorated_to_a_quarter_of_60min_rate(self):
        self.assertEqual(resolve_session_rate(self.client, self.st15), Decimal("25.00"))

    def test_30min_is_prorated_to_half_of_60min_rate(self):
        st30 = ServiceType.objects.create(
            code="therapy_30",
            name="30-Min Therapy",
            default_duration=30,
            practice=self.practice,
        )
        self.assertEqual(resolve_session_rate(self.client, st30), Decimal("50.00"))


class IsSessionAlreadyBilledTests(TestCase):
    def setUp(self):
        self.practice = _make_practice()
        self.st60, _, _, _ = _make_service_types(self.practice)
        self.client = _make_client(self.practice)

    def test_unbilled_session_returns_false(self):
        session = _make_session(self.client)
        self.assertFalse(is_session_already_billed(session))

    def test_session_on_active_invoice_returns_true(self):
        session = _make_session(self.client)
        invoice = _make_invoice(self.client)
        InvoiceItem.objects.create(
            invoice=invoice,
            session=session,
            service_type=self.st60,
            rate=Decimal("100.00"),
            quantity=Decimal("1.00"),
            total=Decimal("100.00"),
        )
        self.assertTrue(is_session_already_billed(session))

    def test_session_on_cancelled_invoice_returns_false(self):
        session = _make_session(self.client)
        invoice = _make_invoice(self.client, status=Invoice.Status.CANCELLED)
        InvoiceItem.objects.create(
            invoice=invoice,
            session=session,
            service_type=self.st60,
            rate=Decimal("100.00"),
            quantity=Decimal("1.00"),
            total=Decimal("100.00"),
        )
        # Cancelled invoice does not count as billed.
        self.assertFalse(is_session_already_billed(session))


class CreateInvoiceItemForSessionTests(TestCase):
    def setUp(self):
        self.practice = _make_practice()
        self.st60, self.st90, self.st_free, self.st15 = _make_service_types(self.practice)
        self.client = _make_client(self.practice)
        self.invoice = _make_invoice(self.client)
        self.service_type_map = {60: self.st60, 90: self.st90, 20: self.st_free}

    def test_creates_item_for_unbilled_session(self):
        session = _make_session(self.client, duration=60)
        item = create_invoice_item_for_session(self.invoice, session, self.service_type_map)
        self.assertIsNotNone(item)
        self.assertEqual(item.rate, Decimal("100.00"))
        self.assertEqual(item.service_type, self.st60)

    def test_returns_none_for_already_billed_session(self):
        session = _make_session(self.client, duration=60)
        InvoiceItem.objects.create(
            invoice=self.invoice,
            session=session,
            service_type=self.st60,
            rate=Decimal("100.00"),
            quantity=Decimal("1.00"),
            total=Decimal("100.00"),
        )
        item = create_invoice_item_for_session(self.invoice, session, self.service_type_map)
        self.assertIsNone(item)

    def test_session_on_cancelled_invoice_can_be_rebilled(self):
        session = _make_session(self.client, duration=60)
        cancelled_invoice = Invoice.objects.create(
            practice=self.client.practice,
            client=self.client,
            invoice_number="BH-99",
            invoice_date=date.today(),
            status=Invoice.Status.CANCELLED,
        )
        InvoiceItem.objects.create(
            invoice=cancelled_invoice,
            session=session,
            service_type=self.st60,
            rate=Decimal("100.00"),
            quantity=Decimal("1.00"),
            total=Decimal("100.00"),
        )
        item = create_invoice_item_for_session(self.invoice, session, self.service_type_map)
        self.assertIsNotNone(item)

    def test_returns_none_when_no_service_type(self):
        session = _make_session(self.client, duration=75)
        item = create_invoice_item_for_session(self.invoice, session, self.service_type_map)
        self.assertIsNone(item)

    def test_uses_fallback_service_type(self):
        session = _make_session(self.client, duration=75)
        item = create_invoice_item_for_session(
            self.invoice, session, self.service_type_map, fallback_service_type=self.st60
        )
        self.assertIsNotNone(item)
        self.assertEqual(item.service_type, self.st60)

    def test_therapy_free_creates_zero_rate_item(self):
        session = _make_session(self.client, duration=20)
        item = create_invoice_item_for_session(self.invoice, session, self.service_type_map)
        self.assertIsNotNone(item)
        self.assertEqual(item.rate, Decimal("0"))

    def test_90min_session_uses_90min_rate(self):
        session = _make_session(self.client, duration=90)
        item = create_invoice_item_for_session(self.invoice, session, self.service_type_map)
        self.assertIsNotNone(item)
        self.assertEqual(item.rate, Decimal("150.00"))

    def test_item_quantity_is_one(self):
        session = _make_session(self.client, duration=60)
        item = create_invoice_item_for_session(self.invoice, session, self.service_type_map)
        self.assertEqual(item.quantity, Decimal("1.00"))

    def test_item_total_equals_rate(self):
        session = _make_session(self.client, duration=60)
        item = create_invoice_item_for_session(self.invoice, session, self.service_type_map)
        self.assertEqual(item.total, item.rate)
