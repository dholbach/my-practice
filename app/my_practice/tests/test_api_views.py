"""
Tests for API views.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from my_practice.models import Client, Invoice, Practice, UserPractice

User = get_user_model()


class NextInvoiceNumberAPITest(TestCase):
    """Tests for next_invoice_number API endpoint"""

    def setUp(self):
        """Set up test client and data"""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="api_views-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        # Create and login user
        self.user = User.objects.create_user(username="apiuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

        self.client_http = TestClient()
        self.client_http.login(username="apiuser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )

    def test_next_invoice_number_no_client_id(self):
        """Test API returns error when no client ID provided"""
        response = self.client_http.get(reverse("next_invoice_number"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        self.assertEqual(response.json()["error"], "Client ID required")

    def test_next_invoice_number_invalid_client(self):
        """Test API returns 404 for non-existent client"""
        response = self.client_http.get(reverse("next_invoice_number"), {"client": 99999})

        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())
        self.assertEqual(response.json()["error"], "Client not found")

    def test_next_invoice_number_first_invoice(self):
        """Test API returns correct number for first invoice"""
        response = self.client_http.get(
            reverse("next_invoice_number"), {"client": self.test_client.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["suggested_number"], "TC-1")

    def test_next_invoice_number_sequential(self):
        """Test API returns sequential numbers"""
        # Create existing invoices
        Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-2",
            invoice_date=date.today(),
            practice=self.practice,
        )

        response = self.client_http.get(
            reverse("next_invoice_number"), {"client": self.test_client.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["suggested_number"], "TC-3")

    def test_next_invoice_number_with_gaps(self):
        """Test API handles gaps in invoice numbers"""
        Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-5",
            invoice_date=date.today(),
            practice=self.practice,
        )

        response = self.client_http.get(
            reverse("next_invoice_number"), {"client": self.test_client.pk}
        )

        # Should return max + 1, not fill the gap
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["suggested_number"], "TC-6")


class InvoicePDFViewTest(TestCase):
    """Tests for invoice PDF generation"""

    def setUp(self):
        """Set up test data"""
        # Create practice settings
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="api-views-fix",
            title="Test Practitioner",
            email="practice@example.com",
            city="Berlin",
        )

        # Create user and link to practice (needed for middleware)
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

        # Create authenticated client
        self.client_http = TestClient()
        self.client_http.login(username="testuser", password="testpass123")

        # Create test client and invoice
        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )

        self.invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            total=Decimal("100.00"),
            practice=self.practice,
        )

    def test_invoice_pdf_generation(self):
        """Test PDF is generated successfully"""
        response = self.client_http.get(reverse("invoice_pdf", kwargs={"pk": self.invoice.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

        # Check filename in Content-Disposition
        content_disposition = response["Content-Disposition"]
        self.assertIn("Rechnung_TC-1.pdf", content_disposition)

    def test_invoice_pdf_404(self):
        """Test PDF generation returns 404 for non-existent invoice"""
        response = self.client_http.get(reverse("invoice_pdf", kwargs={"pk": 99999}))

        self.assertEqual(response.status_code, 404)

    def test_invoice_pdf_english_client(self):
        """Test PDF filename for English-speaking client"""
        # Create English client
        english_client = Client.objects.create(
            client_code="EN",
            full_name="English Client",
            email="english@example.com",
            language="en",
            practice=self.practice,
        )

        english_invoice = Invoice.objects.create(
            client=english_client,
            invoice_number="EN-1",
            invoice_date=date.today(),
            total=Decimal("100.00"),
            practice=self.practice,
        )

        response = self.client_http.get(reverse("invoice_pdf", kwargs={"pk": english_invoice.pk}))

        self.assertEqual(response.status_code, 200)
        content_disposition = response["Content-Disposition"]
        self.assertIn("Invoice_EN-1.pdf", content_disposition)

    def test_invoice_pdf_creates_default_practice(self):
        """Test PDF generation works with practice having all fields configured"""
        # This test originally tested auto-creation of default practice.
        # With multi-practice support, we test PDF generation with complete practice data.

        # Update practice with full configuration (logo/signature would be tested elsewhere)
        self.practice.subtitle_de = "praxis für psychotherapie"
        self.practice.subtitle_en = "therapy practice"
        self.practice.save()

        # Create another client and invoice to test with
        client = Client.objects.create(
            client_code="TC2",
            full_name="Second Client",
            practice=self.practice,
        )
        invoice = Invoice.objects.create(
            client=client,
            invoice_number="TC2-1",
            invoice_date=date.today(),
            practice=self.practice,
        )

        response = self.client_http.get(reverse("invoice_pdf", kwargs={"pk": invoice.pk}))

        # Should work with configured practice
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
