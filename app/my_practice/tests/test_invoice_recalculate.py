"""
Tests for Invoice.recalculate_and_save().

The signals call it after every item save/delete and the invoice views call it
after bulk-adding items, so the totals and the draft invoice_date rule rest on it.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from ..models import Client, Invoice, InvoiceItem, ServiceType, Session, allow_issued_invoice_writes
from .test_helpers import create_test_practice


class InvoiceRecalculateAndSaveTests(TestCase):
    def setUp(self):
        self.practice = create_test_practice(slug="invoice-recalc-1")
        self.client_obj = Client.objects.create(
            client_code="XX-1",
            full_name="Max Mustermann",
            email="mail@example.com",
            language="de",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        self.service_type = ServiceType.objects.create(
            code="recalc_service",
            name="Recalc Service",
            name_de="Recalc Service DE",
            name_en="Recalc Service EN",
            default_duration=60,
            practice=self.practice,
        )

    def make_invoice(self, status="draft", invoice_date=None, tax_rate=Decimal("0.00")):
        return Invoice.objects.create(
            practice=self.practice,
            client=self.client_obj,
            invoice_number="INV-001",
            invoice_date=invoice_date or timezone.localdate(),
            status=status,
            tax_rate=tax_rate,
        )

    def add_item(self, invoice, session_date, rate="90.00"):
        session = Session.objects.create(
            client=self.client_obj, session_date=session_date, duration=60
        )
        return InvoiceItem.objects.create(
            invoice=invoice,
            session=session,
            service_type=self.service_type,
            rate=Decimal(rate),
            quantity=Decimal("1.00"),
        )

    def test_totals_follow_the_items(self):
        invoice = self.make_invoice(tax_rate=Decimal("19.00"))
        self.add_item(invoice, timezone.localdate() - timedelta(days=3), rate="100.00")
        self.add_item(invoice, timezone.localdate() - timedelta(days=2), rate="50.00")
        Invoice.objects.filter(pk=invoice.pk).update(
            subtotal=Decimal("0"), tax_amount=Decimal("0"), total=Decimal("0")
        )

        invoice = Invoice.objects.get(pk=invoice.pk)
        invoice.recalculate_and_save()

        invoice.refresh_from_db()
        self.assertEqual(invoice.subtotal, Decimal("150.00"))
        self.assertEqual(invoice.tax_amount, Decimal("28.50"))
        self.assertEqual(invoice.total, Decimal("178.50"))

    def test_draft_date_moves_to_the_latest_session(self):
        invoice = self.make_invoice()
        future = timezone.localdate() + timedelta(days=5)
        self.add_item(invoice, future)
        Invoice.objects.filter(pk=invoice.pk).update(invoice_date=date(2020, 1, 1))

        invoice = Invoice.objects.get(pk=invoice.pk)
        invoice.recalculate_and_save()

        invoice.refresh_from_db()
        self.assertEqual(invoice.invoice_date, future)

    def test_draft_date_is_today_when_all_sessions_are_past(self):
        invoice = self.make_invoice()
        self.add_item(invoice, timezone.localdate() - timedelta(days=10))
        Invoice.objects.filter(pk=invoice.pk).update(invoice_date=date(2020, 1, 1))

        invoice = Invoice.objects.get(pk=invoice.pk)
        invoice.recalculate_and_save()

        invoice.refresh_from_db()
        self.assertEqual(invoice.invoice_date, timezone.localdate())

    def test_issued_invoice_keeps_its_date(self):
        invoice = self.make_invoice()
        self.add_item(invoice, timezone.localdate() + timedelta(days=5))
        issued_date = date(2026, 3, 1)
        Invoice.objects.filter(pk=invoice.pk).update(status="sent", invoice_date=issued_date)

        invoice = Invoice.objects.get(pk=invoice.pk)
        with allow_issued_invoice_writes():
            invoice.recalculate_and_save()

        invoice.refresh_from_db()
        self.assertEqual(invoice.invoice_date, issued_date)

    def test_saving_an_item_triggers_it_through_the_signal(self):
        invoice = self.make_invoice()
        self.add_item(invoice, timezone.localdate() - timedelta(days=1), rate="80.00")

        invoice.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("80.00"))
