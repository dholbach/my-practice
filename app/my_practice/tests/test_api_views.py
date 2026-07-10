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
        self.assertEqual(response.json()["error"], "Klienten-ID erforderlich")

    def test_next_invoice_number_invalid_client(self):
        """Test API returns 404 for non-existent client"""
        response = self.client_http.get(reverse("next_invoice_number"), {"client": 99999})

        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())
        self.assertEqual(response.json()["error"], "Klient nicht gefunden")

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


class IntakeFormPdfTest(TestCase):
    """Tests for the fillable Aufnahmebogen PDF."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="intake-pdf-test",
            title="Test Practitioner",
            email="practice@example.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="intakepdfuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http = TestClient()
        self.client_http.login(username="intakepdfuser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            email="max@example.com",
            phone="+49 123 456789",
            date_of_birth=date(1990, 1, 15),
            practice=self.practice,
        )

    def _get_form_fields(self, pdf_bytes: bytes) -> dict:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        return reader.get_fields() or {}

    def test_intake_form_pdf_download(self):
        """View returns a PDF with the expected filename."""
        response = self.client_http.get(
            reverse("intake_form_pdf", kwargs={"pk": self.test_client.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("Aufnahmebogen_TC.pdf", response["Content-Disposition"])

    def test_intake_form_pdf_has_fillable_fields(self):
        """The PDF contains AcroForm fields, pre-filled from client data."""
        response = self.client_http.get(
            reverse("intake_form_pdf", kwargs={"pk": self.test_client.pk})
        )
        fields = self._get_form_fields(response.content)

        expected = {
            "full_name",
            "date_of_birth",
            "address",
            "postal_code_city",
            "email",
            "phone",
            "cost_carrier",
            "place_date",
            "signature_patient",
        }
        self.assertEqual(set(fields), expected)
        self.assertEqual(fields["full_name"].get("/V"), "Max Mustermann")
        self.assertEqual(fields["date_of_birth"].get("/V"), "15.01.1990")
        self.assertEqual(fields["email"].get("/V"), "max@example.com")
        # Blank fields are present but empty
        self.assertEqual(fields["postal_code_city"].get("/V"), "")
        self.assertEqual(fields["signature_patient"].get("/V"), "")

    def test_intake_form_pdf_english(self):
        """?lang=en switches the filename to the English variant."""
        response = self.client_http.get(
            reverse("intake_form_pdf", kwargs={"pk": self.test_client.pk}) + "?lang=en"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("IntakeForm_TC.pdf", response["Content-Disposition"])
        self.assertTrue(self._get_form_fields(response.content))


class ContractPdfTest(TestCase):
    """Tests for the pre-filled Behandlungsvertrag PDF."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="contract-pdf-test",
            title="Heilpraktikerin für Psychotherapie",
            email="practice@example.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="contractpdfuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http = TestClient()
        self.client_http.login(username="contractpdfuser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

    def test_contract_pdf_download_german_default(self):
        response = self.client_http.get(reverse("contract_pdf", kwargs={"pk": self.test_client.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("Behandlungsvertrag_TC.pdf", response["Content-Disposition"])

    def test_contract_pdf_lang_param_switches_to_english(self):
        response = self.client_http.get(
            reverse("contract_pdf", kwargs={"pk": self.test_client.pk}) + "?lang=en"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("TreatmentContract_TC.pdf", response["Content-Disposition"])

    def test_contract_pdf_uses_client_language_when_no_param(self):
        self.test_client.language = "en"
        self.test_client.save()
        response = self.client_http.get(reverse("contract_pdf", kwargs={"pk": self.test_client.pk}))
        self.assertIn("TreatmentContract_TC.pdf", response["Content-Disposition"])

    def test_contract_pdf_404_for_nonexistent_client(self):
        response = self.client_http.get(reverse("contract_pdf", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)


class InvoicePdfGebuehTest(TestCase):
    """Test the needs_gebueh_invoice branch of invoice PDF rendering."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="invoice-pdf-gebueh",
            title="Heilpraktikerin für Psychotherapie",
            email="practice@example.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="gebuehpdfuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http = TestClient()
        self.client_http.login(username="gebuehpdfuser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
            needs_gebueh_invoice=True,
        )
        self.invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            total=Decimal("90.00"),
            practice=self.practice,
        )

    def test_invoice_pdf_renders_for_gebueh_client_with_no_leistungen(self):
        response = self.client_http.get(reverse("invoice_pdf", kwargs={"pk": self.invoice.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")


class InvoiceBatchDownloadTest(TestCase):
    """Tests for the ZIP batch-download endpoint."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="invoice-batch-download",
            title="Test Practitioner",
            email="practice@example.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="batchuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http = TestClient()
        self.client_http.login(username="batchuser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            practice=self.practice,
        )

    def test_get_not_allowed(self):
        response = self.client_http.get(reverse("invoice_batch_download"))
        self.assertEqual(response.status_code, 405)

    def test_missing_year_returns_400(self):
        response = self.client_http.post(reverse("invoice_batch_download"), {})
        self.assertEqual(response.status_code, 400)

    def test_non_numeric_year_returns_400(self):
        response = self.client_http.post(reverse("invoice_batch_download"), {"year": "abcd"})
        self.assertEqual(response.status_code, 400)

    def test_no_matching_invoices_returns_204(self):
        response = self.client_http.post(
            reverse("invoice_batch_download"), {"year": "2020", "status": "paid"}
        )
        self.assertEqual(response.status_code, 204)

    def test_downloads_zip_of_matching_invoices(self):
        Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date(2026, 3, 1),
            status=Invoice.Status.PAID,
            total=Decimal("90.00"),
            practice=self.practice,
        )
        response = self.client_http.post(
            reverse("invoice_batch_download"), {"year": "2026", "status": "paid"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("Rechnungen_2026.zip", response["Content-Disposition"])

        import zipfile
        from io import BytesIO

        zf = zipfile.ZipFile(BytesIO(response.content))
        self.assertEqual(len(zf.namelist()), 1)
        self.assertIn("TC_Rechnung_TC-1.pdf", zf.namelist()[0])


class UpdateInvoiceStatusTest(TestCase):
    """Tests for the update_invoice_status endpoint."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="update-invoice-status",
            title="Test Practitioner",
            email="practice@example.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="statususer", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http = TestClient()
        self.client_http.login(username="statususer", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            practice=self.practice,
        )
        self.invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            status=Invoice.Status.DRAFT,
            total=Decimal("90.00"),
            practice=self.practice,
        )

    def test_get_not_allowed(self):
        response = self.client_http.get(
            reverse("update_invoice_status", kwargs={"pk": self.invoice.pk})
        )
        self.assertEqual(response.status_code, 405)

    def test_invalid_status_returns_400(self):
        response = self.client_http.post(
            reverse("update_invoice_status", kwargs={"pk": self.invoice.pk}),
            {"status": "not-a-real-status"},
        )
        self.assertEqual(response.status_code, 400)

    def test_marking_paid_sets_paid_date(self):
        response = self.client_http.post(
            reverse("update_invoice_status", kwargs={"pk": self.invoice.pk}),
            {"status": Invoice.Status.PAID},
        )
        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(self.invoice.paid_date, date.today())
        self.assertEqual(response.json()["status"], Invoice.Status.PAID)

    def test_unmarking_paid_clears_paid_date(self):
        self.invoice.status = Invoice.Status.PAID
        self.invoice.paid_date = date.today()
        self.invoice.save()

        response = self.client_http.post(
            reverse("update_invoice_status", kwargs={"pk": self.invoice.pk}),
            {"status": Invoice.Status.SENT},
        )
        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertIsNone(self.invoice.paid_date)

    def test_htmx_request_returns_badge_html(self):
        response = self.client_http.post(
            reverse("update_invoice_status", kwargs={"pk": self.invoice.pk}),
            {"status": Invoice.Status.SENT},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")

    def test_next_param_redirects(self):
        next_url = reverse("invoice_detail", kwargs={"pk": self.invoice.pk})
        response = self.client_http.post(
            reverse("update_invoice_status", kwargs={"pk": self.invoice.pk}),
            {"status": Invoice.Status.SENT, "next": next_url},
        )
        self.assertRedirects(response, next_url)


class PracticeImagesTransparencyTest(TestCase):
    """Test the RGBA-composite branch of _prepare_practice_images via invoice_pdf."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="practice-logo-transparency",
            title="Test Practitioner",
            email="practice@example.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="logouser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http = TestClient()
        self.client_http.login(username="logouser", password="testpass123")

        self.practice.logo = self._transparent_png("logo.png")
        self.practice.signature = self._transparent_png("signature.png")
        self.practice.save()

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            practice=self.practice,
        )
        self.invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            total=Decimal("90.00"),
            practice=self.practice,
        )

    @staticmethod
    def _transparent_png(name: str):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        img = Image.new("RGBA", (20, 20), (255, 0, 0, 0))
        buf = BytesIO()
        img.save(buf, format="PNG")
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")

    def test_invoice_pdf_composites_transparent_logo_and_signature(self):
        response = self.client_http.get(reverse("invoice_pdf", kwargs={"pk": self.invoice.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
