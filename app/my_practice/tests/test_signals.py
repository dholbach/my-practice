"""
Tests for invoice signals (automatic total and date calculation).
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.files.storage import default_storage
from django.test import TestCase
from my_practice.models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session


class InvoiceSignalTests(TestCase):
    """Test automatic invoice total and date updates via signals."""

    def setUp(self):
        """Create test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="signals-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client = Client.objects.create(
            client_code="TEST001",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("100.00"),
            practice=self.practice,
        )
        self.service_type = ServiceType.objects.create(
            name="Test Service",
            name_de="Testservice",
            name_en="Test Service",
            practice=self.practice,
        )

    def test_total_calculated_on_item_save(self):
        """Test that invoice total is recalculated when an item is saved."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-001",
            invoice_date=date.today(),
            status="draft",
            practice=self.practice,
        )

        # Add first item
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date.today(),
                duration=60,
            ),
            quantity=Decimal("1.00"),
            rate=Decimal("100.00"),
        )

        # Check total was calculated
        invoice.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("100.00"))

        # Add second item
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date.today(),
                duration=60,
            ),
            quantity=Decimal("1.00"),
            rate=Decimal("100.00"),
        )

        # Check total was recalculated
        invoice.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("200.00"))

    def test_total_calculated_on_item_delete(self):
        """Test that invoice total is recalculated when an item is deleted."""
        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-002",
            invoice_date=date.today(),
            status="draft",
            practice=self.practice,
        )

        # Add two items
        item1 = InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date.today(),
                duration=60,
            ),
            quantity=Decimal("1.00"),
            rate=Decimal("100.00"),
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date.today(),
                duration=60,
            ),
            quantity=Decimal("1.00"),
            rate=Decimal("100.00"),
        )

        # Check total
        invoice.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("200.00"))

        # Delete one item
        item1.delete()

        # Check total was recalculated
        invoice.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("100.00"))

    def test_draft_invoice_date_updates_to_latest_item_date(self):
        """Test that draft invoice date is updated to latest item date."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-003",
            invoice_date=yesterday,
            status="draft",
            practice=self.practice,
        )

        # Add item with today's date
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=today,
                duration=60,
            ),
            quantity=Decimal("1.00"),
            rate=Decimal("100.00"),
        )

        # Check invoice date was updated to today
        invoice.refresh_from_db()
        self.assertEqual(invoice.invoice_date, today)

        # Add item with tomorrow's date
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=tomorrow,
                duration=60,
            ),
            quantity=Decimal("1.00"),
            rate=Decimal("100.00"),
        )

        # Check invoice date was updated to tomorrow
        invoice.refresh_from_db()
        self.assertEqual(invoice.invoice_date, tomorrow)

    def test_sent_invoice_date_not_updated(self):
        """Test that sent invoice date is NOT updated automatically."""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        original_date = today - timedelta(days=5)

        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-004",
            invoice_date=original_date,
            status="sent",
            practice=self.practice,
        )

        # Add item with tomorrow's date
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=tomorrow,
                duration=60,
            ),
            quantity=Decimal("1.00"),
            rate=Decimal("100.00"),
        )

        # Check invoice date was NOT changed
        invoice.refresh_from_db()
        self.assertEqual(invoice.invoice_date, original_date)

    def test_draft_invoice_date_uses_today_for_past_dates(self):
        """Test that draft invoice uses today if all items are in the past."""
        today = date.today()
        past_date = today - timedelta(days=10)

        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-005",
            invoice_date=past_date,
            status="draft",
            practice=self.practice,
        )

        # Add item with past date
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=past_date,
                duration=60,
            ),
            quantity=Decimal("1.00"),
            rate=Decimal("100.00"),
        )

        # Check invoice date was updated to today (not the past date)
        invoice.refresh_from_db()
        self.assertEqual(invoice.invoice_date, today)

    def test_quantity_affects_total(self):
        """Test that item quantity is correctly included in total calculation."""
        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-006",
            invoice_date=date.today(),
            status="draft",
            practice=self.practice,
        )

        # Add item with quantity 2.5
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date.today(),
                duration=60,
            ),
            quantity=Decimal("2.5"),
            rate=Decimal("100.00"),
        )

        # Check total includes quantity
        invoice.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("250.00"))

    def test_formset_save_triggers_signals(self):
        """Test that saving via formset triggers signals correctly."""
        from django.db import transaction

        invoice = Invoice.objects.create(
            client=self.client,
            invoice_number="TEST-007",
            invoice_date=date.today(),
            status="draft",
            practice=self.practice,
        )

        # Initial item
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=Session.objects.create(
                client=self.client,
                session_date=date.today(),
                duration=60,
            ),
            quantity=Decimal("1.00"),
            rate=Decimal("100.00"),
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("100.00"))

        # Simulate formset save with additional item
        with transaction.atomic():
            # Create formset with POST data simulating adding an item
            InvoiceItem.objects.create(
                invoice=invoice,
                service_type=self.service_type,
                session=Session.objects.create(
                    client=self.client,
                    session_date=date.today(),
                    duration=60,
                ),
                quantity=Decimal("1.00"),
                rate=Decimal("100.00"),
            )

        # Total should be updated
        invoice.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("200.00"))


class PracticeImageCleanupSignalTests(TestCase):
    """Tests for the logo/signature filesystem cleanup signals."""

    @staticmethod
    def _png(name: str):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        img = Image.new("RGB", (10, 10), (255, 0, 0))
        buf = BytesIO()
        img.save(buf, format="PNG")
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Signal Test Practice",
            slug="signal-image-cleanup",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

    def test_replacing_logo_deletes_old_file(self):
        self.practice.logo = self._png("first.png")
        self.practice.save()
        old_name = self.practice.logo.name
        self.assertTrue(default_storage.exists(old_name))

        self.practice.logo = self._png("second.png")
        self.practice.save()

        self.assertFalse(default_storage.exists(old_name))
        self.assertTrue(default_storage.exists(self.practice.logo.name))

    def test_saving_without_changing_image_does_not_delete_it(self):
        self.practice.logo = self._png("keep.png")
        self.practice.save()
        logo_name = self.practice.logo.name

        self.practice.title = "Updated Title"
        self.practice.save()

        self.assertTrue(default_storage.exists(logo_name))

    def test_deleting_practice_deletes_logo_and_signature(self):
        self.practice.logo = self._png("logo.png")
        self.practice.signature = self._png("sig.png")
        self.practice.save()
        logo_name = self.practice.logo.name
        signature_name = self.practice.signature.name

        self.practice.delete()

        self.assertFalse(default_storage.exists(logo_name))
        self.assertFalse(default_storage.exists(signature_name))
