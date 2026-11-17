"""
Tests for the client record actions: onboarding steps, documents and GDPR erasure.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import (
    BankTransaction,
    Client,
    ClientAlias,
    ClientDocument,
    ClientInquiry,
    ClientTag,
    GebuhZiffer,
    InquiryStatus,
    Leistungserfassung,
    PendingCalendarEvent,
    Practice,
    Session,
)
from .test_helpers import create_test_practice, create_test_user, make_pdf_bytes


class ClientOnboardingStepTest(TestCase):
    """Test the client_onboarding_step view."""

    def setUp(self):
        self.practice = create_test_practice(name="Test Practice", slug="onboarding-step")
        self.user = create_test_user(self.practice, username="onboarduser", password="testpass123")
        self.http = TestClient()
        self.http.login(username="onboarduser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            practice=self.practice,
        )

    def test_get_not_allowed(self):
        response = self.http.get(
            reverse("client_onboarding_step", kwargs={"pk": self.test_client.pk})
        )
        self.assertEqual(response.status_code, 405)

    def test_marks_intake_step_complete(self):
        response = self.http.post(
            reverse("client_onboarding_step", kwargs={"pk": self.test_client.pk}),
            {"step": "intake"},
        )
        self.assertEqual(response.status_code, 302)
        self.test_client.refresh_from_db()
        self.assertEqual(self.test_client.intake_sent_date, date.today())

    def test_resets_intake_step(self):
        self.test_client.intake_sent_date = date.today()
        self.test_client.save()
        self.http.post(
            reverse("client_onboarding_step", kwargs={"pk": self.test_client.pk}),
            {"step": "intake", "reset": "1"},
        )
        self.test_client.refresh_from_db()
        self.assertIsNone(self.test_client.intake_sent_date)

    def test_unknown_step_is_a_noop(self):
        response = self.http.post(
            reverse("client_onboarding_step", kwargs={"pk": self.test_client.pk}),
            {"step": "not-a-real-step"},
        )
        self.assertEqual(response.status_code, 302)

    def test_completing_removes_incomplete_intake_tag(self):
        tag = ClientTag.objects.create(name="incomplete-intake", slug="incomplete-intake")
        self.test_client.tags.add(tag)
        self.http.post(
            reverse("client_onboarding_step", kwargs={"pk": self.test_client.pk}),
            {"step": "complete"},
        )
        self.assertNotIn(tag, self.test_client.tags.all())


class ClientDocumentUploadTest(TestCase):
    """Test the client_document_upload and client_document_delete views."""

    def setUp(self):
        self.practice = create_test_practice(name="Test Practice", slug="doc-upload")
        self.user = create_test_user(self.practice, username="docuser", password="testpass123")
        self.http = TestClient()
        self.http.login(username="docuser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            practice=self.practice,
        )

    def _pdf_file(self, name="beleg.pdf"):
        # Must be a real PDF: process_upload() rejects anything pypdf cannot read.
        return SimpleUploadedFile(name, make_pdf_bytes(), content_type="application/pdf")

    def test_get_not_allowed(self):
        response = self.http.get(
            reverse("client_document_upload", kwargs={"pk": self.test_client.pk})
        )
        self.assertEqual(response.status_code, 405)

    def test_no_file_returns_400(self):
        response = self.http.post(
            reverse("client_document_upload", kwargs={"pk": self.test_client.pk}), {}
        )
        self.assertEqual(response.status_code, 400)

    def test_rejected_extension_returns_400(self):
        bad_file = SimpleUploadedFile("evil.svg", b"<svg></svg>", content_type="image/svg+xml")
        response = self.http.post(
            reverse("client_document_upload", kwargs={"pk": self.test_client.pk}),
            {"file": bad_file},
        )
        self.assertEqual(response.status_code, 400)

    def test_uploads_document_and_returns_metadata(self):
        response = self.http.post(
            reverse("client_document_upload", kwargs={"pk": self.test_client.pk}),
            {
                "file": self._pdf_file(),
                "document_type": ClientDocument.DocumentType.OTHER,
                "description": "Test-Beleg",
                "document_date": "2026-01-15",
            },
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["document_type"], ClientDocument.DocumentType.OTHER)
        self.assertEqual(data["description"], "Test-Beleg")
        self.assertIsNone(data["onboarding_step_completed"])
        self.assertTrue(ClientDocument.objects.filter(client=self.test_client).exists())

    def test_invalid_document_date_falls_back_to_today(self):
        response = self.http.post(
            reverse("client_document_upload", kwargs={"pk": self.test_client.pk}),
            {"file": self._pdf_file(), "document_date": "not-a-date"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["document_date"], str(date.today()))

    def test_unknown_document_type_falls_back_to_other(self):
        response = self.http.post(
            reverse("client_document_upload", kwargs={"pk": self.test_client.pk}),
            {"file": self._pdf_file(), "document_type": "not-a-real-type"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["document_type"], ClientDocument.DocumentType.OTHER)

    def test_intake_upload_marks_onboarding_step_complete(self):
        response = self.http.post(
            reverse("client_document_upload", kwargs={"pk": self.test_client.pk}),
            {"file": self._pdf_file(), "document_type": ClientDocument.DocumentType.INTAKE},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["onboarding_step_completed"], "intake")
        self.test_client.refresh_from_db()
        self.assertIsNotNone(self.test_client.intake_sent_date)

    def test_intake_upload_does_not_overwrite_existing_step_date(self):
        self.test_client.intake_sent_date = date(2020, 1, 1)
        self.test_client.save()
        response = self.http.post(
            reverse("client_document_upload", kwargs={"pk": self.test_client.pk}),
            {"file": self._pdf_file(), "document_type": ClientDocument.DocumentType.INTAKE},
        )
        self.assertIsNone(response.json()["onboarding_step_completed"])
        self.test_client.refresh_from_db()
        self.assertEqual(self.test_client.intake_sent_date, date(2020, 1, 1))

    def test_delete_removes_document(self):
        upload_response = self.http.post(
            reverse("client_document_upload", kwargs={"pk": self.test_client.pk}),
            {"file": self._pdf_file()},
        )
        doc_id = upload_response.json()["id"]

        response = self.http.post(reverse("client_document_delete", kwargs={"pk": doc_id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})
        self.assertFalse(ClientDocument.objects.filter(pk=doc_id).exists())

    def test_delete_wrong_practice_raises_permission_denied(self):
        other_practice = Practice.objects.create(
            name="Other Practice",
            slug="doc-upload-other",
            title="Other Practitioner",
            email="other@practice.com",
            city="Hamburg",
        )
        other_client = Client.objects.create(
            client_code="OC",
            full_name="Anna Schmidt",
            practice=other_practice,
        )
        doc = ClientDocument.objects.create(
            client=other_client,
            document_type=ClientDocument.DocumentType.OTHER,
            file=self._pdf_file(),
            document_date=date.today(),
        )
        response = self.http.post(reverse("client_document_delete", kwargs={"pk": doc.pk}))
        self.assertEqual(response.status_code, 403)


class ClientGdprDeleteTest(TestCase):
    """Test client_gdpr_delete_confirm and client_gdpr_delete views."""

    def setUp(self):
        self.practice = create_test_practice(name="Test Practice", slug="gdpr-delete")
        self.user = create_test_user(self.practice, username="gdpruser", password="testpass123")
        self.http = TestClient()
        self.http.login(username="gdpruser", password="testpass123")

        self.old_date = date.today() - timedelta(days=365 * 11)
        self.eligible_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            email="max@example.com",
            practice=self.practice,
            active=False,
        )
        Session.objects.create(client=self.eligible_client, session_date=self.old_date, duration=60)

    def test_confirm_page_for_eligible_client(self):
        response = self.http.get(
            reverse("client_gdpr_delete_confirm", kwargs={"pk": self.eligible_client.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/client_gdpr_delete_confirm.html")

    def test_confirm_page_rejects_active_client(self):
        self.eligible_client.active = True
        self.eligible_client.save()
        response = self.http.get(
            reverse("client_gdpr_delete_confirm", kwargs={"pk": self.eligible_client.pk})
        )
        self.assertRedirects(response, reverse("client_list"))

    def test_confirm_page_rejects_recent_session(self):
        recent_client = Client.objects.create(
            client_code="RC",
            full_name="Anna Schmidt",
            practice=self.practice,
            active=False,
        )
        Session.objects.create(client=recent_client, session_date=date.today(), duration=60)
        response = self.http.get(
            reverse("client_gdpr_delete_confirm", kwargs={"pk": recent_client.pk})
        )
        self.assertRedirects(response, reverse("client_list"))

    def test_delete_get_not_allowed(self):
        response = self.http.get(
            reverse("client_gdpr_delete", kwargs={"pk": self.eligible_client.pk})
        )
        self.assertEqual(response.status_code, 405)

    def test_delete_rejects_ineligible_client(self):
        self.eligible_client.active = True
        self.eligible_client.save()
        response = self.http.post(
            reverse("client_gdpr_delete", kwargs={"pk": self.eligible_client.pk})
        )
        self.assertRedirects(response, reverse("client_list"))
        self.assertTrue(Client.objects.filter(pk=self.eligible_client.pk).exists())

    @patch("my_practice.views.client_views.EmailMessage.send")
    def test_delete_erases_client_and_sends_notification(self, mock_send):
        client_pk = self.eligible_client.pk
        content = b"%PDF-1.0\n1 0 obj<</Type /Catalog>>endobj\n"
        ClientDocument.objects.create(
            client=self.eligible_client,
            document_type=ClientDocument.DocumentType.OTHER,
            file=SimpleUploadedFile("beleg.pdf", content, content_type="application/pdf"),
            document_date=date.today(),
        )
        response = self.http.post(reverse("client_gdpr_delete", kwargs={"pk": client_pk}))
        self.assertRedirects(response, reverse("client_list"))
        self.assertFalse(Client.objects.filter(pk=client_pk).exists())
        mock_send.assert_called_once()

    @patch(
        "my_practice.views.client_views.EmailMessage.send",
        side_effect=RuntimeError("smtp down"),
    )
    def test_delete_continues_when_email_send_fails(self, mock_send):
        client_pk = self.eligible_client.pk
        response = self.http.post(
            reverse("client_gdpr_delete", kwargs={"pk": client_pk}), follow=True
        )
        self.assertFalse(Client.objects.filter(pk=client_pk).exists())
        page_messages = list(response.context["messages"])
        self.assertTrue(any("konnte nicht gesendet werden" in str(m) for m in page_messages))

    @patch("my_practice.views.client_views.EmailMessage.send")
    def test_delete_anonymises_source_inquiry_and_drops_calendar_events(self, mock_send):
        inquiry = ClientInquiry.objects.create(
            practice=self.practice,
            full_name="Max Mustermann",
            email="max@example.com",
            phone="+49 123 456789",
            source=ClientInquiry._meta.get_field("source").choices[0][0],
            status=InquiryStatus.CONVERTED,
            converted_client=self.eligible_client,
        )
        PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="evt-gdpr-1",
            summary="TC",
            event_date=self.old_date,
            duration_minutes=60,
            matched_client=self.eligible_client,
        )

        self.http.post(reverse("client_gdpr_delete", kwargs={"pk": self.eligible_client.pk}))

        inquiry.refresh_from_db()
        self.assertEqual((inquiry.full_name, inquiry.email, inquiry.phone), ("", "", ""))
        self.assertIsNotNone(inquiry.anonymised_at)
        self.assertFalse(PendingCalendarEvent.objects.filter(google_event_id="evt-gdpr-1").exists())

    def _event(self, event_id, summary):
        return PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id=event_id,
            summary=summary,
            event_date=self.old_date,
            duration_minutes=60,
        )

    @patch("my_practice.views.client_views.EmailMessage.send")
    def test_delete_drops_unmatched_events_naming_the_client(self, mock_send):
        # The sync matches by code only, so these have no link to the client.
        ClientAlias.objects.create(client=self.eligible_client, alias_name="Hans Mustermann")
        self._event("by-name", "max mustermann Sitzung")
        self._event("by-code", "TC (online)")
        self._event("by-alias", "Hans Mustermann")
        self._event("unrelated", "Anna Schmidt")
        self._event("code-inside-word", "TCX")

        self.http.post(reverse("client_gdpr_delete", kwargs={"pk": self.eligible_client.pk}))

        self.assertEqual(
            sorted(PendingCalendarEvent.objects.values_list("google_event_id", flat=True)),
            ["code-inside-word", "unrelated"],
        )

    @patch("my_practice.views.client_views.EmailMessage.send")
    def test_delete_keeps_bank_transactions_and_says_so(self, mock_send):
        BankTransaction.objects.create(
            practice=self.practice,
            transaction_date=self.old_date,
            value_date=self.old_date,
            payer_name="Max Mustermann",
            payer_iban="DE00123456789",
            reference="INV-001",
            amount=Decimal("80.00"),
            balance_after=Decimal("900.00"),
            account_iban="",
        )
        confirm = self.http.get(
            reverse("client_gdpr_delete_confirm", kwargs={"pk": self.eligible_client.pk})
        )
        self.assertContains(confirm, "Bankbuchungen")

        with patch("my_practice.views.client_views.EmailMessage") as message:
            self.http.post(reverse("client_gdpr_delete", kwargs={"pk": self.eligible_client.pk}))

        self.assertTrue(BankTransaction.objects.filter(payer_name="Max Mustermann").exists())
        self.assertIn("Kontoauszügen", message.call_args.kwargs["body"])

    @patch("my_practice.views.client_views.EmailMessage.send")
    def test_delete_succeeds_for_client_with_gebueh_services(self, mock_send):
        # Leistungserfassung.session is PROTECT: it used to abort the erasure
        # after the "your data has been deleted" email had already gone out.
        ziffer = GebuhZiffer.objects.create(
            nummer="T1", bezeichnung="Test", satz_min=Decimal("10"), satz_max=Decimal("50")
        )
        Leistungserfassung.objects.create(
            session=self.eligible_client.sessions.get(),
            ziffer=ziffer,
            betrag=Decimal("50"),
            vereinbarter_betrag=Decimal("80"),
        )
        client_pk = self.eligible_client.pk

        response = self.http.post(reverse("client_gdpr_delete", kwargs={"pk": client_pk}))

        self.assertRedirects(response, reverse("client_list"))
        self.assertFalse(Client.objects.filter(pk=client_pk).exists())
        mock_send.assert_called_once()

    @patch("my_practice.views.client_views.EmailMessage.send")
    def test_no_notification_when_erasure_fails(self, mock_send):
        with (
            patch.object(Client, "delete", side_effect=RuntimeError("db down")),
            self.assertRaises(RuntimeError),
        ):
            self.http.post(reverse("client_gdpr_delete", kwargs={"pk": self.eligible_client.pk}))
        mock_send.assert_not_called()
        self.assertTrue(Client.objects.filter(pk=self.eligible_client.pk).exists())

    def test_delete_client_without_email_skips_notification(self):
        self.eligible_client.email = ""
        self.eligible_client.save()
        with patch("my_practice.views.client_views.EmailMessage.send") as mock_send:
            response = self.http.post(
                reverse("client_gdpr_delete", kwargs={"pk": self.eligible_client.pk})
            )
        self.assertRedirects(response, reverse("client_list"))
        mock_send.assert_not_called()
