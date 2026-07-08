"""
Tests for email sending views.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from my_practice.models import Client, Invoice, Practice, UserPractice

User = get_user_model()


class SendInvoiceEmailViewTest(TestCase):
    """Tests for SendInvoiceEmailView"""

    def setUp(self):
        """Set up test data"""
        # Reduce logging noise during tests
        logging.getLogger("my_practice.email").setLevel(logging.ERROR)

        self.client_http = TestClient()

        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="email-test-practice",  # Unique slug for this test
            title="Test Practitioner",
            email="practice@test.com",
            city="Berlin",
        )

        # Create and login user
        self.user = User.objects.create_user(username="emailuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http.login(username="emailuser", password="testpass123")

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
            status="draft",  # Can be sent
            total=Decimal("100.00"),
            practice=self.practice,
        )

    def test_send_email_form_loads(self):
        """Test email customization form loads"""
        response = self.client_http.get(
            reverse("send_invoice_email", kwargs={"invoice_id": self.invoice.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/send_invoice_email.html")
        self.assertIn("form", response.context)
        self.assertIn("invoice", response.context)

    def test_send_email_form_prefilled(self):
        """Test form is pre-filled with default content"""
        response = self.client_http.get(
            reverse("send_invoice_email", kwargs={"invoice_id": self.invoice.pk})
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]

        # Check initial values
        self.assertEqual(form.initial["recipient"], "test@example.com")
        self.assertIn("subject", form.initial)
        self.assertIn("body", form.initial)

    def test_send_email_already_sent_warning(self):
        """Test warning when invoice already sent"""
        self.invoice.status = "sent"
        self.invoice.save()

        response = self.client_http.get(
            reverse("send_invoice_email", kwargs={"invoice_id": self.invoice.pk})
        )

        # Should redirect with warning
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("invoice_detail", kwargs={"pk": self.invoice.pk}))

    def test_send_email_minimal_practice(self):
        """Form loads even when practice has minimal configuration (e.g. no email set)."""
        self.practice.email = ""
        self.practice.save()

        response = self.client_http.get(
            reverse("send_invoice_email", kwargs={"invoice_id": self.invoice.pk})
        )

        # Invoice is scoped to current practice — form loads regardless of practice config
        self.assertEqual(response.status_code, 200)

    def test_send_email_404(self):
        """Test 404 for non-existent invoice"""
        response = self.client_http.get(reverse("send_invoice_email", kwargs={"invoice_id": 99999}))

        self.assertEqual(response.status_code, 404)

    @patch("my_practice.views.email_views.EmailMessage")
    def test_send_email_quick_mode(self, mock_email):
        """Test quick send without customization"""
        # Mock email sending
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 1

        response = self.client_http.post(
            reverse("send_invoice_email", kwargs={"invoice_id": self.invoice.pk}),
            {"quick_send": "true"},
        )

        # Should redirect after sending
        self.assertIn(response.status_code, [200, 302])  # 200 if form error, 302 if success

        # Check email was called
        self.assertTrue(mock_email.called)
        mock_instance.send.assert_called_once()

    @patch("my_practice.views.email_views.EmailMessage")
    def test_send_email_custom_mode(self, mock_email):
        """Test sending with custom content"""
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 1

        data = {
            "recipient": "custom@example.com",
            "subject": "Custom Subject",
            "body": "Custom email body",
        }

        response = self.client_http.post(
            reverse("send_invoice_email", kwargs={"invoice_id": self.invoice.pk}), data
        )

        # Should redirect after sending
        self.assertIn(response.status_code, [200, 302])  # 200 if form error, 302 if success

        # Check email was created with custom content
        self.assertTrue(mock_email.called)
        call_kwargs = mock_email.call_args.kwargs
        self.assertEqual(call_kwargs.get("subject"), "Custom Subject")

    def test_send_email_invalid_data(self):
        """Test form validation with invalid data"""
        data = {
            "recipient": "invalid-email",  # Invalid email
            "subject": "",  # Required field
            "body": "",
        }

        response = self.client_http.post(
            reverse("send_invoice_email", kwargs={"invoice_id": self.invoice.pk}), data
        )

        # Should show form again with errors
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertTrue(response.context["form"].errors)

    @patch("my_practice.views.email_views.EmailMessage")
    def test_send_email_updates_invoice_date_to_today(self, mock_email):
        """Test that invoice date is updated to today when sending email"""
        # Set invoice date to yesterday
        yesterday = date.today() - timedelta(days=1)
        self.invoice.invoice_date = yesterday
        self.invoice.save()

        # Mock email sending
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 1

        self.client_http.post(
            reverse("send_invoice_email", kwargs={"invoice_id": self.invoice.pk}),
            {"quick_send": "true"},
        )

        # Reload invoice from database
        self.invoice.refresh_from_db()

        # Invoice date should now be today
        self.assertEqual(self.invoice.invoice_date, date.today())

    @patch("my_practice.views.email_views.EmailMessage")
    def test_send_email_keeps_current_date_if_today(self, mock_email):
        """Test that invoice date is not modified if already today"""
        # Invoice date is already today (from setUp)
        original_date = self.invoice.invoice_date
        self.assertEqual(original_date, date.today())

        # Mock email sending
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 1

        self.client_http.post(
            reverse("send_invoice_email", kwargs={"invoice_id": self.invoice.pk}),
            {"quick_send": "true"},
        )

        # Reload invoice from database
        self.invoice.refresh_from_db()

        # Invoice date should still be today
        self.assertEqual(self.invoice.invoice_date, date.today())


class SendIntakeFormEmailViewTest(TestCase):
    """Tests for SendIntakeFormEmailView"""

    def setUp(self):
        logging.getLogger("my_practice.email").setLevel(logging.ERROR)

        self.client_http = TestClient()
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="intake-email-test-practice",
            title="Test Practitioner",
            email="practice@test.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="intakeemailuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http.login(username="intakeemailuser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            email="max@example.com",
            practice=self.practice,
        )

    def test_form_loads_prefilled(self):
        """GET renders the form with default subject/body and recipient."""
        response = self.client_http.get(
            reverse("send_intake_form_email", kwargs={"pk": self.test_client.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/send_intake_form_email.html")
        form = response.context["form"]
        self.assertEqual(form.initial["recipient"], "max@example.com")
        self.assertEqual(form.initial["subject"], "Aufnahmebogen")
        self.assertEqual(response.context["filename"], "Aufnahmebogen_TC.pdf")

    def test_redirects_without_client_email(self):
        """Client without email → redirect to client detail with error."""
        self.test_client.email = ""
        self.test_client.save()

        response = self.client_http.get(
            reverse("send_intake_form_email", kwargs={"pk": self.test_client.pk})
        )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": self.test_client.pk}))

    @patch("my_practice.views.email_views.EmailMessage")
    def test_send_attaches_pdf_and_sets_intake_sent_date(self, mock_email):
        """POST sends the email with the fillable PDF attached and marks the step done."""
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 1

        self.assertIsNone(self.test_client.intake_sent_date)

        response = self.client_http.post(
            reverse("send_intake_form_email", kwargs={"pk": self.test_client.pk}),
            {
                "recipient": "max@example.com",
                "subject": "Aufnahmebogen",
                "body": "Hallo",
            },
        )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": self.test_client.pk}))
        mock_instance.send.assert_called_once()

        # PDF attachment
        mock_instance.attach.assert_called_once()
        fname, fbytes, fmime = mock_instance.attach.call_args.args
        self.assertEqual(fname, "Aufnahmebogen_TC.pdf")
        self.assertEqual(fmime, "application/pdf")
        self.assertTrue(fbytes.startswith(b"%PDF"))

        # Onboarding step marked as done
        self.test_client.refresh_from_db()
        self.assertEqual(self.test_client.intake_sent_date, date.today())
