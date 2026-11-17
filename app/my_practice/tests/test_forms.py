"""Tests for Django forms."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import translation

from my_practice.email_forms import InvoiceEmailForm
from my_practice.invoice_forms import InvoiceForm, InvoiceItemForm
from my_practice.models import Client, ServiceType, Session

from .test_helpers import create_test_practice, practice_request


class InvoiceFormTestCase(TestCase):
    """Tests for InvoiceForm"""

    def setUp(self):
        """Create test client"""
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="forms-1")

        self.client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            language="de",
            practice=self.practice,
        )

    def test_form_valid_data(self):
        """Test form with all valid data"""
        form_data = {
            "client": self.client.id,
            "invoice_number": "TC-123",
            "invoice_date": "2025-12-24",
            "status": "draft",
            "tax_rate": "0.00",
            "notes": "Test notes",
        }
        form = InvoiceForm(data=form_data, request=practice_request(self.practice))
        self.assertTrue(form.is_valid())

    def test_form_auto_generates_invoice_number(self):
        """Test that invoice_number is optional and can be auto-generated"""
        form_data = {
            "client": self.client.id,
            "invoice_number": "",  # Empty should be fine
            "invoice_date": "2025-12-24",
            "status": "draft",
            "tax_rate": "0.00",
        }
        form = InvoiceForm(data=form_data, request=practice_request(self.practice))
        self.assertTrue(form.is_valid())

    def test_form_sets_default_invoice_date(self):
        """Test that invoice_date defaults to today"""
        form = InvoiceForm(request=practice_request(self.practice))
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
        form = InvoiceForm(request=practice_request(self.practice))
        client_ids = [c.id for c in form.fields["client"].queryset]
        self.assertIn(self.client.id, client_ids)
        self.assertNotIn(inactive_client.id, client_ids)

    def test_form_offers_only_the_current_practice_clients(self):
        other = create_test_practice(name="Other Practice", slug="forms-other")
        stranger = Client.objects.create(client_code="ST", full_name="Anna Schmidt", practice=other)
        form = InvoiceForm(request=practice_request(self.practice))
        self.assertNotIn(stranger.id, [c.id for c in form.fields["client"].queryset])
        submitted = InvoiceForm(
            data={"client": stranger.id, "invoice_date": "2025-12-24", "status": "draft"},
            request=practice_request(self.practice),
        )
        self.assertFalse(submitted.is_valid())
        self.assertIn("client", submitted.errors)

    def test_form_without_a_practice_offers_no_clients(self):
        form = InvoiceForm(request=practice_request(None))
        self.assertEqual(list(form.fields["client"].queryset), [])

    def test_form_requires_a_request(self):
        with self.assertRaises(TypeError):
            InvoiceForm()

    def test_preselected_inactive_client_stays_selectable(self):
        inactive = Client.objects.create(
            client_code="IC", full_name="Inactive Client", active=False, practice=self.practice
        )
        form = InvoiceForm(initial={"client": inactive}, request=practice_request(self.practice))
        ids = [c.id for c in form.fields["client"].queryset]
        self.assertIn(inactive.id, ids)
        self.assertIn(self.client.id, ids)

    def test_submitted_inactive_client_stays_selectable(self):
        inactive = Client.objects.create(
            client_code="IC", full_name="Inactive Client", active=False, practice=self.practice
        )
        form = InvoiceForm(
            data={
                "client": inactive.id,
                "invoice_date": "2025-12-24",
                "status": "draft",
                "tax_rate": "0.00",
            },
            request=practice_request(self.practice),
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_editing_keeps_inactive_clients_of_the_practice(self):
        from my_practice.models import Invoice

        inactive = Client.objects.create(
            client_code="IC", full_name="Inactive Client", active=False, practice=self.practice
        )
        invoice = Invoice.objects.create(
            practice=self.practice,
            client=inactive,
            invoice_number="IC-1",
            invoice_date=date(2025, 12, 24),
        )
        form = InvoiceForm(instance=invoice, request=practice_request(self.practice))
        self.assertIn(inactive.id, [c.id for c in form.fields["client"].queryset])

    def test_form_invalid_without_client(self):
        """Test form validation fails without client"""
        form_data = {
            "invoice_date": "2025-12-24",
            "status": "draft",
        }
        form = InvoiceForm(data=form_data, request=practice_request(self.practice))
        self.assertFalse(form.is_valid())
        self.assertIn("client", form.errors)

    def test_form_invalid_date_format(self):
        """Test form validation fails with invalid date"""
        form_data = {
            "client": self.client.id,
            "invoice_date": "invalid-date",
            "status": "draft",
        }
        form = InvoiceForm(data=form_data, request=practice_request(self.practice))
        self.assertFalse(form.is_valid())
        self.assertIn("invoice_date", form.errors)


class InvoiceItemFormTestCase(TestCase):
    """Tests for InvoiceItemForm"""

    def setUp(self):
        """Create test data"""
        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="forms-2")

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
        """Test that a row needs a session_date (or, for practices that allow
        it, a free-text description — see P-122). Neither -> invalid."""
        form_data = {
            "service_type": self.service_type.id,
            "duration": 60,
            "rate": "90.00",
        }
        with translation.override("en"):
            form = InvoiceItemForm(data=form_data)
            self.assertFalse(form.is_valid())
            self.assertIn(
                "Enter either a session date or a free-text description.",
                form.errors.get("__all__", []),
            )

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
        self.practice = create_test_practice(name="Test Practice", slug="forms-4")

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
        }
        invoice_form = InvoiceForm(data=invoice_data, request=practice_request(self.practice))
        self.assertTrue(invoice_form.is_valid())
        invoice = invoice_form.save(commit=False)
        invoice.practice = self.practice
        invoice.save()

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
