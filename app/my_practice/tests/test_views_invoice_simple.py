"""
Simplified tests for invoice views based on actual implementation.
"""

import json
import re
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import Client, Invoice, InvoiceItem, ServiceType, Session, UserPractice
from .test_helpers import (
    create_test_client,
    create_test_invoice,
    create_test_practice,
    create_test_user,
    login_to_practice,
)


class InvoiceListViewSimpleTest(TestCase):
    """Simplified test for invoice list view."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        # Create practice
        self.practice = create_test_practice(name="Test Practice", slug="views_invoice_simple-1")

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
        self.practice = create_test_practice(name="Test Practice", slug="views_invoice_simple-2")

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
        self.practice = create_test_practice(name="Test Practice", slug="views_invoice_simple-3")

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


class InvoiceFormClientRatesTest(TestCase):
    """Both invoice forms hand invoice_items.js the practice's client rates as JSON."""

    def setUp(self):
        self.practice = create_test_practice(slug="invoice-client-rates")
        self.http = login_to_practice(create_test_user(self.practice), self.practice)
        self.max = create_test_client(self.practice, "XX-1", hourly_rate_60=Decimal("90.00"))
        self.anna = create_test_client(
            self.practice,
            "YY-2",
            "Anna Schmidt",
            hourly_rate_60=Decimal("100.00"),
            hourly_rate_90=Decimal("140.50"),
        )
        other = create_test_practice(name="Other Practice", slug="invoice-client-rates-2")
        create_test_client(other, "ZZ-3", hourly_rate_60=Decimal("55.00"))
        self.invoice = create_test_invoice(self.max, "XX-1-1")

    def rates(self, url):
        response = self.http.get(url)
        self.assertEqual(response.status_code, 200)
        match = re.search(
            r'<script type="application/json" id="client-rates-data">(.*?)</script>',
            response.content.decode(),
            re.S,
        )
        self.assertIsNotNone(match, "the rates script is missing")
        return json.loads(match.group(1))

    def assert_rates(self, rates):
        self.assertEqual(rates[str(self.max.pk)]["code"], "XX-1")
        self.assertEqual(rates[str(self.anna.pk)]["rate_90"], 140.5)
        self.assertEqual(len(rates), 2, "only the current practice's clients")

    def test_new_invoice_form_lists_the_practice_clients_with_rates(self):
        self.assert_rates(self.rates(reverse("invoice_create")))

    def test_edit_invoice_form_lists_the_practice_clients_with_rates(self):
        self.assert_rates(self.rates(reverse("invoice_edit", args=[self.invoice.pk])))
