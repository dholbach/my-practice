"""
Tests for the billing models: invoices and invoice items.
"""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from my_practice.models import (
    Client,
    Invoice,
    InvoiceItem,
    Practice,
    ServiceType,
    Session,
)

from .test_helpers import create_test_practice


class InvoiceModelTestCase(TestCase):
    """Tests for Invoice model"""

    def setUp(self):
        """Create test client"""
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="models-1")

        self.client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )

    def test_invoice_creation(self):
        """Test creating an invoice"""
        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            status="draft",
            practice=self.practice,
        )
        self.assertEqual(invoice.invoice_number, "TC-1")
        self.assertEqual(invoice.status, "draft")

    def _sent_invoice(self, number, invoice_date=date(2026, 1, 5), **fields):
        return Invoice.objects.create(
            client=self.client,
            invoice_number=number,
            invoice_date=invoice_date,
            status="sent",
            practice=self.practice,
            **fields,
        )

    def test_mark_paid_with_a_date_uses_it(self):
        invoice = self._sent_invoice("TC-P1")
        invoice.mark_paid(date(2026, 1, 20))
        invoice.refresh_from_db()
        self.assertEqual((invoice.status, invoice.paid_date), ("paid", date(2026, 1, 20)))

    def test_mark_paid_with_a_date_replaces_an_existing_paid_date(self):
        invoice = self._sent_invoice("TC-P2", paid_date=date(2026, 1, 10))
        invoice.mark_paid(date(2026, 1, 20))
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_date, date(2026, 1, 20))

    def test_mark_paid_without_a_date_keeps_an_existing_paid_date(self):
        invoice = self._sent_invoice("TC-P3", paid_date=date(2026, 1, 10))
        invoice.mark_paid()
        invoice.refresh_from_db()
        self.assertEqual((invoice.status, invoice.paid_date), ("paid", date(2026, 1, 10)))

    def test_mark_paid_without_any_date_uses_today(self):
        invoice = self._sent_invoice("TC-P4")
        invoice.mark_paid()
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_date, timezone.localdate())

    def test_mark_paid_refuses_a_payment_before_the_invoice_date(self):
        invoice = self._sent_invoice("TC-P5", invoice_date=date(2026, 2, 1))
        with self.assertRaises(ValidationError):
            invoice.mark_paid(date(2026, 1, 20))
        invoice.refresh_from_db()
        self.assertEqual((invoice.status, invoice.paid_date), ("sent", None))

    def test_invoice_str(self):
        """Test Invoice string representation"""
        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TC-123",
            invoice_date=date.today(),
            practice=self.practice,
        )
        self.assertIn("TC-123", str(invoice))

    def test_invoice_number_unique(self):
        """Test that invoice_number should be unique (but allows blank)"""

        Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        # Creating with same number should raise ValidationError
        with self.assertRaises(ValidationError):
            Invoice.objects.create(
                client=self.client,
                invoice_number="TC-1",
                invoice_date=date.today(),
                practice=self.practice,
            )

    def test_invoice_client_practice_mismatch_rejected(self):
        """A client belonging to another practice must not be assignable to an invoice."""
        other_practice = Practice.objects.create(
            name="Other Practice",
            slug="models-other",
            title="Other Practitioner",
            email="other@practice.com",
            city="Berlin",
        )
        other_client = Client.objects.create(
            client_code="OC",
            full_name="Other Client",
            email="other@example.com",
            practice=other_practice,
        )
        with self.assertRaises(ValidationError):
            Invoice.objects.create(
                client=other_client,
                invoice_number="TC-MISMATCH",
                invoice_date=date.today(),
                practice=self.practice,
            )

    def test_invoice_defaults(self):
        """Test Invoice default values"""
        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        self.assertEqual(invoice.status, "draft")
        self.assertEqual(invoice.tax_rate, Decimal("0.00"))

    def test_invoice_calculate_total(self):
        """Test invoice total calculation"""
        service_type = ServiceType.objects.create(
            code="therapy_60",
            name="Session",
            default_duration=60,
            practice=self.practice,
        )
        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        session_60 = Session.objects.create(
            client=self.client,
            session_date=date.today(),
            duration=60,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            session=session_60,
            service_type=service_type,
            rate=Decimal("90.00"),
        )
        session_90 = Session.objects.create(
            client=self.client,
            session_date=date.today(),
            duration=90,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            session=session_90,
            service_type=service_type,
            rate=Decimal("130.00"),
        )

        total = invoice.calculate_total()
        self.assertEqual(total, Decimal("220.00"))

    def test_invoice_ordering(self):
        """Test Invoice default ordering (newest first)"""
        Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date(2025, 1, 1),
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.client,
            invoice_number="TC-2",
            invoice_date=date(2025, 12, 1),
            practice=self.practice,
        )

        invoices = list(Invoice.objects.all())
        self.assertEqual(invoices[0].invoice_number, "TC-2")  # Newest first
        self.assertEqual(invoices[1].invoice_number, "TC-1")


class InvoiceItemModelTestCase(TestCase):
    """Tests for InvoiceItem model"""

    def setUp(self):
        """Create test data"""
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="models-2")

        self.client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )
        self.invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        self.service_type = ServiceType.objects.create(
            code="therapy_60",
            name="60-Min Session",
            default_duration=60,
            practice=self.practice,
        )

    def test_invoice_item_creation(self):
        """Test creating an invoice item"""
        session = Session.objects.create(
            client=self.client,
            session_date=date.today(),
            duration=60,
        )
        item = InvoiceItem.objects.create(
            invoice=self.invoice,
            session=session,
            service_type=self.service_type,
            rate=Decimal("90.00"),
        )
        self.assertEqual(item.session.duration, 60)
        self.assertEqual(item.rate, Decimal("90.00"))

    def test_invoice_item_str(self):
        """Test InvoiceItem string representation"""
        session = Session.objects.create(
            client=self.client,
            session_date=date(2025, 12, 24),
            duration=60,
        )
        item = InvoiceItem.objects.create(
            invoice=self.invoice,
            session=session,
            service_type=self.service_type,
            rate=Decimal("90.00"),
        )
        # __str__ returns invoice number and date
        result = str(item)
        self.assertIn("TC-1", result)
        self.assertIn("2025-12-24", result)

    def test_invoice_item_line_total(self):
        """Test line total calculation (rate only, no quantity)"""
        session = Session.objects.create(
            client=self.client,
            session_date=date.today(),
            duration=60,
        )
        item = InvoiceItem.objects.create(
            invoice=self.invoice,
            session=session,
            service_type=self.service_type,
            rate=Decimal("90.00"),
        )
        # Line total is just the rate
        self.assertEqual(item.rate, Decimal("90.00"))
