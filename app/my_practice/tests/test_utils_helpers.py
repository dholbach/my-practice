"""
Tests for utility helper functions.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from my_practice.models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session
from my_practice.utils.calculations import (
    count_sessions,
    count_sessions_rounded,
    to_float,
)
from my_practice.utils.invoice_helpers import get_next_invoice_number


class ToFloatTest(TestCase):
    """Tests for to_float() helper function"""

    def test_to_float_decimal(self):
        """Test conversion from Decimal"""
        self.assertEqual(to_float(Decimal("1.5")), 1.5)
        self.assertEqual(to_float(Decimal("90.00")), 90.0)

    def test_to_float_int(self):
        """Test conversion from int"""
        self.assertEqual(to_float(60), 60.0)
        self.assertEqual(to_float(0), 0.0)

    def test_to_float_float(self):
        """Test conversion from float (passthrough)"""
        self.assertEqual(to_float(1.5), 1.5)

    def test_to_float_string(self):
        """Test conversion from valid string"""
        self.assertEqual(to_float("1.5"), 1.5)
        self.assertEqual(to_float("60"), 60.0)

    def test_to_float_invalid(self):
        """Test invalid values return 0.0"""
        self.assertEqual(to_float("invalid"), 0.0)
        self.assertEqual(to_float(None), 0.0)
        self.assertEqual(to_float(""), 0.0)


class CountSessionsTest(TestCase):
    """Tests for count_sessions() helper function"""

    def setUp(self):
        """Set up test data"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="utils_helpers-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

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
            code="session", name="Session", practice=self.practice
        )

        self.cancel_service_type = ServiceType.objects.create(
            code="cancel_fee", name="Cancellation Fee", practice=self.practice
        )

    def test_count_sessions_60_min(self):
        """Test counting 60-minute sessions"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        InvoiceItem.objects.create(
            invoice=self.invoice,
            session=Session.objects.create(
                client=self.client,
                session_date=date.today(),
                duration=60,
            ),
            service_type=self.service_type,
            rate=Decimal("90.00"),
        )

        items = self.invoice.items.all()
        self.assertEqual(count_sessions(items), 1.0)

    def test_count_sessions_90_min(self):
        """Test counting 90-minute sessions"""
        InvoiceItem.objects.create(
            invoice=self.invoice,
            session=Session.objects.create(
                client=self.client,
                session_date=date.today(),
                duration=90,
            ),
            service_type=self.service_type,
            rate=Decimal("130.00"),
        )

        items = self.invoice.items.all()
        self.assertEqual(count_sessions(items), 1.5)

    def test_count_sessions_mixed(self):
        """Test counting mixed duration sessions"""
        InvoiceItem.objects.create(
            invoice=self.invoice,
            session=Session.objects.create(
                client=self.client,
                session_date=date.today(),
                duration=60,
            ),
            service_type=self.service_type,
            rate=Decimal("90.00"),
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            session=Session.objects.create(
                client=self.client,
                session_date=date.today(),
                duration=90,
            ),
            service_type=self.service_type,
            rate=Decimal("130.00"),
        )

        items = self.invoice.items.all()
        self.assertEqual(count_sessions(items), 2.5)

    def test_count_sessions_exclude_cancellations(self):
        """Test excluding cancellation items"""
        InvoiceItem.objects.create(
            invoice=self.invoice,
            session=Session.objects.create(
                client=self.client,
                session_date=date.today(),
                duration=60,
            ),
            service_type=self.service_type,
            rate=Decimal("90.00"),
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            session=Session.objects.create(
                client=self.client,
                session_date=date.today(),
                duration=60,
            ),
            service_type=self.cancel_service_type,
            rate=Decimal("90.00"),
        )

        items = self.invoice.items.all()

        # With exclusion (default)
        self.assertEqual(count_sessions(items, exclude_cancellations=True), 1.0)

        # Without exclusion
        self.assertEqual(count_sessions(items, exclude_cancellations=False), 2.0)

    def test_count_sessions_rounded(self):
        """Test rounding behavior"""
        InvoiceItem.objects.create(
            invoice=self.invoice,
            session=Session.objects.create(
                client=self.client,
                session_date=date.today(),
                duration=75,
            ),
            service_type=self.service_type,
            rate=Decimal("110.00"),
        )

        items = self.invoice.items.all()

        # Exact count
        self.assertEqual(count_sessions(items), 1.25)

        # Rounded count
        self.assertEqual(count_sessions_rounded(items), 1.0)


class GetNextInvoiceNumberTest(TestCase):
    """Tests for get_next_invoice_number() helper function"""

    def setUp(self):
        """Set up test client"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="utils_helpers-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )

    def test_first_invoice_number(self):
        """Test first invoice number for new client"""
        result = get_next_invoice_number(self.client)
        self.assertEqual(result, "TC-1")

    def test_sequential_numbers(self):
        """Test sequential invoice numbers"""
        Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )

        result = get_next_invoice_number(self.client)
        self.assertEqual(result, "TC-2")

    def test_with_gaps(self):
        """Test handling gaps in invoice numbers"""
        Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.client,
            invoice_number="TC-5",
            invoice_date=date.today(),
            practice=self.practice,
        )

        # Should return max + 1, not fill gap
        result = get_next_invoice_number(self.client)
        self.assertEqual(result, "TC-6")

    def test_malformed_numbers(self):
        """Test handling malformed invoice numbers"""
        Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.client,
            invoice_number="TC-invalid",
            invoice_date=date.today(),
            practice=self.practice,
        )

        # Should ignore malformed and use valid max
        result = get_next_invoice_number(self.client)
        self.assertEqual(result, "TC-2")

    def test_multiple_clients(self):
        """Test invoice numbers are client-specific"""
        # Create another client
        other_client = Client.objects.create(
            client_code="OC",
            full_name="Other Client",
            email="other@example.com",
            practice=self.practice,
        )

        # Create invoices for both clients
        Invoice.objects.create(
            client=self.client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        Invoice.objects.create(
            client=other_client,
            invoice_number="OC-10",
            invoice_date=date.today(),
            practice=self.practice,
        )

        # Each client should have independent numbering
        self.assertEqual(get_next_invoice_number(self.client), "TC-2")
        self.assertEqual(get_next_invoice_number(other_client), "OC-11")
