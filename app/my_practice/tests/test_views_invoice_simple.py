"""
Simplified tests for invoice views based on actual implementation.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session, UserPractice


class InvoiceListViewSimpleTest(TestCase):
    """Simplified test for invoice list view."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_invoice_simple-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.service_type = ServiceType.objects.create(
            code="individual",
            name="60 Min Session",
            name_de="60 Min. Psychotherapie",
            practice=self.practice,
        )

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

        Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            total=Decimal("180.00"),
            status="draft",
            practice=self.practice,
        )

        Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-2",
            invoice_date=date.today(),
            total=Decimal("90.00"),
            status="sent",
            practice=self.practice,
        )

    def test_invoice_list_loads(self):
        """Test that invoice list loads successfully."""
        response = self.client_instance.get(reverse("invoice_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/invoice_list.html")

    def test_invoice_list_shows_invoices(self):
        """Test that invoice list displays invoices."""
        response = self.client_instance.get(reverse("invoice_list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("invoices", response.context or response.context["page_obj"])

    def test_invoice_list_status_filter(self):
        """Test status filtering."""
        response = self.client_instance.get(reverse("invoice_list") + "?status=draft")
        self.assertEqual(response.status_code, 200)
        # Page loads successfully with filter

    def test_invoice_list_year_filter(self):
        """Test year filtering."""
        current_year = date.today().year
        response = self.client_instance.get(reverse("invoice_list") + f"?year={current_year}")
        self.assertEqual(response.status_code, 200)
        # Page loads successfully with filter


class InvoiceDetailViewSimpleTest(TestCase):
    """Simplified test for invoice detail view."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client_instance = TestClient()

        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_invoice_simple-2",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Link user to practice
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

        self.client_instance.login(username="testuser", password="testpass123")

        self.service_type = ServiceType.objects.create(
            code="individual",
            name="60 Min Session",
            name_de="60 Min. Psychotherapie",
            practice=self.practice,
        )

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

        self.invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            total=Decimal("180.00"),
            practice=self.practice,
        )

        self.session_obj = Session.objects.create(
            client=self.test_client, session_date=date.today(), duration=60
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=self.session_obj,
            rate=Decimal("90.00"),  # Field is 'rate', not 'unit_price'
            quantity=Decimal("2.00"),
            total=Decimal("180.00"),
        )

    def test_invoice_detail_loads(self):
        """Test that invoice detail loads successfully."""
        response = self.client_instance.get(
            reverse("invoice_detail", kwargs={"pk": self.invoice.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/invoice_detail.html")

    def test_invoice_detail_has_invoice(self):
        """Test that invoice is in context."""
        response = self.client_instance.get(
            reverse("invoice_detail", kwargs={"pk": self.invoice.pk})
        )
        self.assertIn("invoice", response.context)
        self.assertEqual(response.context["invoice"].invoice_number, "TC-1")

    def test_invoice_detail_shows_items(self):
        """Test that invoice items are accessible."""
        response = self.client_instance.get(
            reverse("invoice_detail", kwargs={"pk": self.invoice.pk})
        )
        invoice_obj = response.context["invoice"]
        # Items accessible via related_name='items'
        items_count = invoice_obj.items.count()
        self.assertEqual(items_count, 1)

    def test_invoice_detail_404(self):
        """Test 404 for non-existent invoice."""
        response = self.client_instance.get(reverse("invoice_detail", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)


class InvoiceCreateViewSimpleTest(TestCase):
    """Simplified test for invoice creation view."""

    def setUp(self):
        """Set up test data."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="views_invoice_simple-3",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

    def test_invoice_create_loads(self):
        """Test that invoice create form loads."""
        response = self.client_instance.get(reverse("invoice_create"))
        self.assertEqual(response.status_code, 200)
        # Form should load (template may vary)

    def test_invoice_create_with_client_param(self):
        """Test invoice create with client parameter."""
        response = self.client_instance.get(
            reverse("invoice_create") + f"?client={self.test_client.pk}"
        )
        self.assertEqual(response.status_code, 200)
        # Page loads successfully with client parameter
