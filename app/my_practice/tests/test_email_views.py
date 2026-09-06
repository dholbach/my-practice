"""
Tests for email sending views.
"""

import logging
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase, override_settings
from django.urls import reverse

from my_practice.models import Client, Invoice, Practice, UserPractice
from my_practice.views.email_views import _make_from_email

User = get_user_model()


class MakeFromEmailTest(TestCase):
    """Unit tests for the _make_from_email helper."""

    def test_uses_display_name_when_set(self):
        practice = Practice.objects.create(
            name="Test Practice",
            slug="from-email-display-name-test",
            title="Test Practitioner",
            email="practice@test.com",
            email_from_name="Dr. Test Practitioner",
            city="Berlin",
        )
        self.assertEqual(_make_from_email(practice), "Dr. Test Practitioner <practice@test.com>")

    def test_bare_email_when_no_display_name(self):
        practice = Practice.objects.create(
            name="Test Practice",
            slug="from-email-bare-test",
            title="Test Practitioner",
            email="practice@test.com",
            city="Berlin",
        )
        self.assertEqual(_make_from_email(practice), "practice@test.com")


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

    def test_post_already_sent_warns_and_redirects(self):
        """POST (not just GET) on an already-sent invoice is blocked too."""
        self.invoice.status = "sent"
        self.invoice.save()

        response = self.client_http.post(
            reverse("send_invoice_email", kwargs={"invoice_id": self.invoice.pk}),
            {"quick_send": "true"},
        )
        self.assertRedirects(response, reverse("invoice_detail", kwargs={"pk": self.invoice.pk}))

    @patch("my_practice.views.email_views.SendInvoiceEmailView._generate_pdf")
    def test_pdf_generation_failure_shows_error(self, mock_generate_pdf):
        mock_generate_pdf.side_effect = RuntimeError("boom")

        response = self.client_http.post(
            reverse("send_invoice_email", kwargs={"invoice_id": self.invoice.pk}),
            {"quick_send": "true"},
        )
        self.assertRedirects(response, reverse("invoice_detail", kwargs={"pk": self.invoice.pk}))

    @patch("my_practice.views.email_views.EmailMessage")
    def test_send_exception_shows_error(self, mock_email):
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.side_effect = RuntimeError("smtp down")

        response = self.client_http.post(
            reverse("send_invoice_email", kwargs={"invoice_id": self.invoice.pk}),
            {"quick_send": "true"},
        )
        self.assertRedirects(response, reverse("invoice_detail", kwargs={"pk": self.invoice.pk}))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "draft")

    @patch("my_practice.views.email_views.EmailMessage")
    def test_send_result_not_one_shows_error_and_keeps_draft(self, mock_email):
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 0

        response = self.client_http.post(
            reverse("send_invoice_email", kwargs={"invoice_id": self.invoice.pk}),
            {"quick_send": "true"},
        )
        self.assertRedirects(response, reverse("invoice_detail", kwargs={"pk": self.invoice.pk}))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "draft")

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


class SendPaymentReminderViewTest(TestCase):
    """Tests for SendPaymentReminderView."""

    def setUp(self):
        logging.getLogger("my_practice.email").setLevel(logging.ERROR)
        self.client_http = TestClient()
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="reminder-email-test-practice",
            title="Test Practitioner",
            email="practice@test.com",
            city="Berlin",
            bank_name="Testbank",
            iban="DE00 0000 0000 0000 0000 00",
            bic="TESTDEFFXXX",
        )
        self.user = User.objects.create_user(username="reminderemailuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http.login(username="reminderemailuser", password="testpass123")

    def _url(self, client_obj):
        return reverse("send_payment_reminder", kwargs={"pk": client_obj.pk})

    def test_no_open_invoices_redirects_with_warning(self):
        test_client = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )
        response = self.client_http.get(self._url(test_client))
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": test_client.pk}))

    def test_english_client_singular_wording_and_bank_details(self):
        test_client = Client.objects.create(
            client_code="EN",
            full_name="John Doe",
            email="john@example.com",
            practice=self.practice,
            language="en",
        )
        Invoice.objects.create(
            client=test_client,
            invoice_number="EN-1",
            invoice_date=date(2026, 3, 1),
            status="sent",
            total=Decimal("100.00"),
            practice=self.practice,
        )
        response = self.client_http.get(self._url(test_client))
        self.assertEqual(response.status_code, 200)
        subject = response.context["form"].initial["subject"]
        body = response.context["form"].initial["body"]
        self.assertIn("1 outstanding invoice", subject)
        self.assertIn("this invoice", body)
        self.assertIn("Testbank: DE00 0000 0000 0000 0000 00", body)
        self.assertEqual(response.context["open_invoices_total"], 100.00)

    def test_german_client_plural_wording_and_total(self):
        test_client = Client.objects.create(
            client_code="DE",
            full_name="Max Mustermann",
            email="max@example.com",
            practice=self.practice,
        )
        Invoice.objects.create(
            client=test_client,
            invoice_number="DE-1",
            invoice_date=date(2026, 3, 1),
            status="sent",
            total=Decimal("100.00"),
            practice=self.practice,
        )
        Invoice.objects.create(
            client=test_client,
            invoice_number="DE-2",
            invoice_date=date(2026, 3, 2),
            status="sent",
            total=Decimal("50.00"),
            practice=self.practice,
        )
        response = self.client_http.get(self._url(test_client))
        subject = response.context["form"].initial["subject"]
        body = response.context["form"].initial["body"]
        self.assertIn("2 offene Rechnungen", subject)
        self.assertIn("diese Rechnungen", body)
        self.assertIn("Gesamtbetrag offen: 150", body)
        self.assertEqual(response.context["open_invoices_total"], 150.00)

    def test_no_iban_omits_bank_lines(self):
        self.practice.iban = ""
        self.practice.save()
        test_client = Client.objects.create(
            client_code="NB",
            full_name="No Bank",
            email="nb@example.com",
            practice=self.practice,
        )
        Invoice.objects.create(
            client=test_client,
            invoice_number="NB-1",
            invoice_date=date(2026, 3, 1),
            status="sent",
            total=Decimal("10.00"),
            practice=self.practice,
        )
        response = self.client_http.get(self._url(test_client))
        body = response.context["form"].initial["body"]
        self.assertNotIn("Testbank", body)

    @patch("my_practice.views.email_views.EmailMessage")
    def test_post_sends_reminder(self, mock_email):
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 1

        test_client = Client.objects.create(
            client_code="SD",
            full_name="Send Client",
            email="send@example.com",
            practice=self.practice,
        )
        Invoice.objects.create(
            client=test_client,
            invoice_number="SD-1",
            invoice_date=date(2026, 3, 1),
            status="sent",
            total=Decimal("10.00"),
            practice=self.practice,
        )
        response = self.client_http.post(
            self._url(test_client),
            {"recipient": "send@example.com", "subject": "Reminder", "body": "Please pay"},
        )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": test_client.pk}))
        mock_instance.send.assert_called_once()


class SendCancellationEmailViewTest(TestCase):
    """Tests for SendCancellationEmailView."""

    def setUp(self):
        logging.getLogger("my_practice.email").setLevel(logging.ERROR)
        self.client_http = TestClient()
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="cancellation-email-test-practice",
            title="Test Practitioner",
            email="practice@test.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(
            username="cancellationemailuser", password="testpass123"
        )
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http.login(username="cancellationemailuser", password="testpass123")

    def _url(self, client_obj):
        return reverse("send_cancellation_email", kwargs={"pk": client_obj.pk})

    def test_german_content_default(self):
        test_client = Client.objects.create(
            client_code="DE",
            full_name="Anna Schmidt",
            email="anna@example.com",
            practice=self.practice,
        )
        response = self.client_http.get(self._url(test_client))
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["subject"], "Absage unserer morgigen Sitzung")
        self.assertIn("Liebe/r Anna,", form.initial["body"])

    def test_english_content(self):
        test_client = Client.objects.create(
            client_code="EN",
            full_name="Jane Doe",
            email="jane@example.com",
            practice=self.practice,
            language="en",
        )
        response = self.client_http.get(self._url(test_client))
        form = response.context["form"]
        self.assertEqual(form.initial["subject"], "Cancellation of tomorrow's session")
        self.assertIn("Dear Jane,", form.initial["body"])

    def test_custom_salutation_overrides_default_greeting(self):
        test_client = Client.objects.create(
            client_code="SA",
            full_name="Someone Else",
            email="someone@example.com",
            practice=self.practice,
            salutation="Hallo Herr Else",
        )
        response = self.client_http.get(self._url(test_client))
        form = response.context["form"]
        self.assertIn("Hallo Herr Else,", form.initial["body"])

    @patch("my_practice.views.email_views.EmailMessage")
    def test_post_sends_cancellation(self, mock_email):
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 1

        test_client = Client.objects.create(
            client_code="SD",
            full_name="Send Client",
            email="send@example.com",
            practice=self.practice,
        )
        response = self.client_http.post(
            self._url(test_client),
            {"recipient": "send@example.com", "subject": "Absage", "body": "Leider..."},
        )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": test_client.pk}))
        mock_instance.send.assert_called_once()

    def test_post_invalid_form_rerenders(self):
        """Shared BaseClientEmailView.post(): invalid form re-renders instead of redirecting."""
        test_client = Client.objects.create(
            client_code="IV",
            full_name="Invalid Client",
            email="invalid@example.com",
            practice=self.practice,
        )
        response = self.client_http.post(
            self._url(test_client),
            {"recipient": "not-an-email", "subject": "", "body": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

    @patch("my_practice.views.email_views.EmailMessage")
    def test_send_result_not_one_shows_error(self, mock_email):
        """Shared _dispatch_email(): a non-1 send result shows an error, still redirects."""
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 0

        test_client = Client.objects.create(
            client_code="FL",
            full_name="Fail Client",
            email="fail@example.com",
            practice=self.practice,
        )
        response = self.client_http.post(
            self._url(test_client),
            {"recipient": "fail@example.com", "subject": "Absage", "body": "Leider..."},
            follow=True,
        )
        messages_list = list(response.context["messages"])
        self.assertTrue(any(m.tags == "error" for m in messages_list))

    @patch("my_practice.views.email_views.EmailMessage")
    def test_send_exception_shows_error(self, mock_email):
        """Shared _dispatch_email(): an exception during send() is caught and shown."""
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.side_effect = RuntimeError("smtp down")

        test_client = Client.objects.create(
            client_code="EX",
            full_name="Exception Client",
            email="exception@example.com",
            practice=self.practice,
        )
        response = self.client_http.post(
            self._url(test_client),
            {"recipient": "exception@example.com", "subject": "Absage", "body": "Leider..."},
            follow=True,
        )
        messages_list = list(response.context["messages"])
        self.assertTrue(any(m.tags == "error" for m in messages_list))


class SendQuestionnaireEmailViewTest(TestCase):
    """Tests for SendQuestionnaireEmailView — the Anamnesebogen .docx flow.

    Uses a scratch MY_PRACTICE_DATA_DIR so the test is deterministic
    regardless of whether a real instance's documents/ happens to be
    mounted — never read or depend on real practice data.
    """

    def setUp(self):
        logging.getLogger("my_practice.email").setLevel(logging.ERROR)
        self.client_http = TestClient()
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="questionnaire-email-test-practice",
            title="Test Practitioner",
            email="practice@test.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(
            username="questionnaireemailuser", password="testpass123"
        )
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http.login(username="questionnaireemailuser", password="testpass123")
        self.test_client = Client.objects.create(
            client_code="QC",
            full_name="Quest Client",
            email="quest@example.com",
            practice=self.practice,
        )
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.data_dir = Path(self._tmpdir.name)

    def _url(self):
        return reverse("send_questionnaire_docx", kwargs={"pk": self.test_client.pk})

    def test_redirects_with_error_when_docx_missing(self):
        with override_settings(MY_PRACTICE_DATA_DIR=self.data_dir):
            response = self.client_http.get(self._url())
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": self.test_client.pk}))

    def test_get_form_loads_prefilled_when_docx_present(self):
        docs_dir = self.data_dir / "documents"
        docs_dir.mkdir(parents=True)
        (docs_dir / "Anamnesebogen.docx").write_bytes(b"fake-docx-bytes")

        with override_settings(MY_PRACTICE_DATA_DIR=self.data_dir):
            response = self.client_http.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["docx_name"], "Anamnesebogen.docx")
        self.assertEqual(response.context["form"].initial["recipient"], "quest@example.com")

    @patch("my_practice.views.email_views.EmailMessage")
    def test_post_attaches_docx_and_sets_questionnaire_sent_date(self, mock_email):
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 1

        docs_dir = self.data_dir / "documents"
        docs_dir.mkdir(parents=True)
        (docs_dir / "Anamnesebogen.docx").write_bytes(b"fake-docx-bytes")

        self.assertIsNone(self.test_client.questionnaire_sent_date)

        with override_settings(MY_PRACTICE_DATA_DIR=self.data_dir):
            response = self.client_http.post(
                self._url(),
                {"recipient": "quest@example.com", "subject": "Fragebogen", "body": "Hallo"},
            )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": self.test_client.pk}))
        mock_instance.attach.assert_called_once()
        fname, fbytes, _fmime = mock_instance.attach.call_args.args
        self.assertEqual(fname, "Anamnesebogen.docx")
        self.assertEqual(fbytes, b"fake-docx-bytes")

        self.test_client.refresh_from_db()
        self.assertEqual(self.test_client.questionnaire_sent_date, date.today())


class SendContractEmailViewTest(TestCase):
    """Tests for SendContractEmailView."""

    def setUp(self):
        logging.getLogger("my_practice.email").setLevel(logging.ERROR)
        self.client_http = TestClient()
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="contract-email-test-practice",
            title="Test Practitioner",
            email="practice@test.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="contractemailuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http.login(username="contractemailuser", password="testpass123")
        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Contract Client",
            email="contract@example.com",
            practice=self.practice,
        )

    def test_form_loads_with_filename(self):
        response = self.client_http.get(
            reverse("send_contract_email", kwargs={"pk": self.test_client.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filename"], "Behandlungsvertrag_TC.pdf")

    @patch("my_practice.views.email_views.EmailMessage")
    def test_post_attaches_pdf_and_sends(self, mock_email):
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance
        mock_instance.send.return_value = 1

        response = self.client_http.post(
            reverse("send_contract_email", kwargs={"pk": self.test_client.pk}),
            {
                "recipient": "contract@example.com",
                "subject": "Behandlungsvertrag",
                "body": "Hallo",
            },
        )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": self.test_client.pk}))
        mock_instance.attach.assert_called_once()
        fname, fbytes, fmime = mock_instance.attach.call_args.args
        self.assertEqual(fname, "Behandlungsvertrag_TC.pdf")
        self.assertEqual(fmime, "application/pdf")
        self.assertTrue(fbytes.startswith(b"%PDF"))

    @patch("my_practice.views.email_views.generate_contract_pdf_bytes")
    def test_post_attachment_generation_failure_redirects_with_error(self, mock_generate):
        """Shared BaseClientEmailView.post(): get_attachment() raising is caught."""
        mock_generate.side_effect = RuntimeError("PDF engine crashed")

        response = self.client_http.post(
            reverse("send_contract_email", kwargs={"pk": self.test_client.pk}),
            {"recipient": "contract@example.com", "subject": "x", "body": "y"},
        )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": self.test_client.pk}))


class SendQuestionnairePdfEmailViewTest(TestCase):
    """Tests for SendQuestionnairePdfEmailView."""

    def setUp(self):
        logging.getLogger("my_practice.email").setLevel(logging.ERROR)
        self.client_http = TestClient()
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="questionnaire-pdf-email-test-practice",
            title="Test Practitioner",
            email="practice@test.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(
            username="questionnairepdfemailuser", password="testpass123"
        )
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_http.login(username="questionnairepdfemailuser", password="testpass123")
        self.test_client = Client.objects.create(
            client_code="QP",
            full_name="Questionnaire Pdf Client",
            email="qp@example.com",
            practice=self.practice,
        )

    def test_unknown_questionnaire_code_redirects_with_error(self):
        response = self.client_http.get(
            reverse(
                "send_questionnaire_pdf_email",
                kwargs={"pk": self.test_client.pk, "code": "does-not-exist"},
            )
        )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": self.test_client.pk}))
