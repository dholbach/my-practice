"""Tests for Django forms."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from my_practice.email_forms import InvoiceEmailForm
from my_practice.invoice_forms import InvoiceForm, InvoiceItemForm
from my_practice.models import Client, Practice, ServiceType, Session


class InvoiceFormTestCase(TestCase):
    """Tests for InvoiceForm"""

    def setUp(self):
        """Create test client"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="forms-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            language="de",
            practice=self.practice,
        )

    def test_form_valid_data(self):
        """Test form with all valid data"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        form_data = {
            "client": self.client.id,
            "invoice_number": "TC-123",
            "invoice_date": "2025-12-24",
            "status": "draft",
            "tax_rate": "0.00",
            "notes": "Test notes",
            "practice": self.practice.id,
        }
        form = InvoiceForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_auto_generates_invoice_number(self):
        """Test that invoice_number is optional and can be auto-generated"""
        form_data = {
            "client": self.client.id,
            "invoice_number": "",  # Empty should be fine
            "invoice_date": "2025-12-24",
            "status": "draft",
            "tax_rate": "0.00",
            "practice": self.practice.id,
        }
        form = InvoiceForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_sets_default_invoice_date(self):
        """Test that invoice_date defaults to today"""
        form = InvoiceForm()
        self.assertEqual(form.fields["invoice_date"].initial, date.today())

    def test_form_only_shows_active_clients(self):
        """Test that only active clients appear in queryset"""
        inactive_client = Client.objects.create(
            client_code="IC",
            full_name="Inactive Client",
            email="inactive@example.com",
            active=False,
            practice=self.practice,
        )
        form = InvoiceForm()
        client_ids = [c.id for c in form.fields["client"].queryset]
        self.assertIn(self.client.id, client_ids)
        self.assertNotIn(inactive_client.id, client_ids)

    def test_form_invalid_without_client(self):
        """Test form validation fails without client"""
        form_data = {
            "invoice_date": "2025-12-24",
            "status": "draft",
        }
        form = InvoiceForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("client", form.errors)

    def test_form_invalid_date_format(self):
        """Test form validation fails with invalid date"""
        form_data = {
            "client": self.client.id,
            "invoice_date": "invalid-date",
            "status": "draft",
        }
        form = InvoiceForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("invoice_date", form.errors)


class InvoiceItemFormTestCase(TestCase):
    """Tests for InvoiceItemForm"""

    def setUp(self):
        """Create test data"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="forms-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.service_type = ServiceType.objects.create(
            code="therapy_60",
            name="60-Min Session",
            default_duration=60,
            practice=self.practice,
        )

    def test_form_valid_data(self):
        """Test form with valid data"""
        form_data = {
            "session_date": "2025-12-24",
            "service_type": self.service_type.id,
            "duration": 60,
            "rate": "90.00",
            "description": "Test session",
        }
        form = InvoiceItemForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_valid_without_description(self):
        """Test that description is optional"""
        form_data = {
            "session_date": "2025-12-24",
            "service_type": self.service_type.id,
            "duration": 60,
            "rate": "90.00",
        }
        form = InvoiceItemForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_requires_session_date(self):
        """Test that session_date is required"""
        form_data = {
            "service_type": self.service_type.id,
            "duration": 60,
            "rate": "90.00",
        }
        form = InvoiceItemForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("session_date", form.errors)

    def test_form_sets_default_duration(self):
        """Test that duration defaults to 60"""
        form = InvoiceItemForm()
        # Check widget attributes for default
        self.assertEqual(form.fields["duration"].widget.attrs.get("value"), "60")


class InvoiceEmailFormTestCase(TestCase):
    """Tests for InvoiceEmailForm"""

    def test_form_valid_data(self):
        """Test form with valid email data"""
        form_data = {
            "recipient": "client@example.com",
            "subject": "Invoice #TC-123",
            "body": "Please find your invoice attached.",
        }
        form = InvoiceEmailForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_invalid_email(self):
        """Test form validation fails with invalid email"""
        form_data = {
            "recipient": "not-an-email",
            "subject": "Test",
            "body": "Test message",
        }
        form = InvoiceEmailForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("recipient", form.errors)

    def test_form_requires_all_fields(self):
        """Test that all fields are required"""
        form = InvoiceEmailForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn("recipient", form.errors)
        self.assertIn("subject", form.errors)
        self.assertIn("body", form.errors)

    def test_form_trims_whitespace(self):
        """Test that form trims whitespace from inputs"""
        form_data = {
            "recipient": "  client@example.com  ",
            "subject": "  Invoice  ",
            "body": "  Message  ",
        }
        form = InvoiceEmailForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["recipient"], "client@example.com")
        self.assertEqual(form.cleaned_data["subject"], "Invoice")
        self.assertEqual(form.cleaned_data["body"], "Message")


class InvoiceFormIntegrationTestCase(TestCase):
    """Integration tests for Invoice and InvoiceItem forms together"""

    def setUp(self):
        """Create test data"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="forms-4",
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
        self.service_type = ServiceType.objects.create(
            code="therapy_60",
            name="60-Min Session",
            default_duration=60,
            practice=self.practice,
        )

    def test_create_invoice_with_items(self):
        """Test creating invoice with items using forms"""
        # Create invoice
        invoice_data = {
            "client": self.client.id,
            "invoice_number": "TC-123",
            "invoice_date": "2025-12-24",
            "status": "draft",
            "tax_rate": "0.00",
            "practice": self.practice.id,
        }
        invoice_form = InvoiceForm(data=invoice_data)
        self.assertTrue(invoice_form.is_valid())
        invoice = invoice_form.save()

        # Create invoice item
        session_obj = Session.objects.create(
            client=self.client,
            session_date=date(2025, 12, 20),
            duration=60,
        )
        item_data = {
            "service_type": self.service_type.id,
            "rate": "90.00",
            "description": "First session",
            "session_date": "2025-12-20",
            "duration": "60",
        }
        item_form = InvoiceItemForm(data=item_data)
        self.assertTrue(item_form.is_valid())
        item = item_form.save(commit=False)
        item.invoice = invoice
        item.session = session_obj
        item.save()

        # Verify
        self.assertEqual(invoice.items.count(), 1)
        self.assertEqual(invoice.items.first().session.duration, 60)
        self.assertEqual(invoice.items.first().rate, Decimal("90.00"))
