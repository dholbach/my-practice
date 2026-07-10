"""
Tests for invoice billing flows: create/edit form_valid+form_invalid paths,
delete, add-sessions helpers, and the monthly billing overview.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..models import (
    Client,
    Invoice,
    InvoiceItem,
    PendingCalendarEvent,
    Practice,
    ServiceType,
    Session,
    UserPractice,
)
from ..views.invoice_views import (
    _build_billing_summary,
    _build_client_rows,
    _determine_client_billing_status,
    _parse_billing_month,
)


class ParseBillingMonthTests(TestCase):
    """Test the _parse_billing_month helper directly."""

    def test_valid_month(self):
        self.assertEqual(_parse_billing_month("2026-03"), date(2026, 3, 1))

    def test_invalid_month_number(self):
        self.assertIsNone(_parse_billing_month("2026-13"))

    def test_non_numeric(self):
        self.assertIsNone(_parse_billing_month("2026-xx"))

    def test_missing_dash(self):
        self.assertIsNone(_parse_billing_month("202603"))

    def test_none_input(self):
        self.assertIsNone(_parse_billing_month(None))


class DetermineClientBillingStatusTests(TestCase):
    """Test the _determine_client_billing_status helper directly."""

    def test_cancelled_billed_wins_over_everything(self):
        status, _label, _icon = _determine_client_billing_status([], 5, 5, 1)
        self.assertEqual(status, "warning")

    def test_pending_beats_unbilled(self):
        status, _label, _icon = _determine_client_billing_status([], 5, 1, 0)
        self.assertEqual(status, "warning")

    def test_unbilled_only(self):
        status, _label, _icon = _determine_client_billing_status([], 1, 0, 0)
        self.assertEqual(status, "warning")

    def test_all_draft(self):
        inv = Invoice(status=Invoice.Status.DRAFT)
        status, _label, _icon = _determine_client_billing_status([inv], 0, 0, 0)
        self.assertEqual(status, "draft")

    def test_any_sent(self):
        drafts = [Invoice(status=Invoice.Status.DRAFT), Invoice(status=Invoice.Status.SENT)]
        status, _label, _icon = _determine_client_billing_status(drafts, 0, 0, 0)
        self.assertEqual(status, "sent")

    def test_all_paid(self):
        inv = Invoice(status=Invoice.Status.PAID)
        status, _label, _icon = _determine_client_billing_status([inv], 0, 0, 0)
        self.assertEqual(status, "ok")

    def test_no_invoices_no_issues(self):
        status, _label, _icon = _determine_client_billing_status([], 0, 0, 0)
        self.assertEqual(status, "ok")


class BuildClientRowsTests(TestCase):
    """Test _build_client_rows and _build_billing_summary directly."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="billing-rows",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.client_a = Client.objects.create(
            client_code="AA",
            full_name="Anna Schmidt",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        self.client_b = Client.objects.create(
            client_code="BB",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

    def test_skip_ok_filters_out_ok_rows(self):
        rows = _build_client_rows(
            [self.client_a, self.client_b],
            invoices_by_client={},
            billed_session_count_by_client={},
            unbilled_sessions_by_client={self.client_a.pk: ["session-placeholder"]},
            pending_by_client={},
            cancelled_billed_by_client={},
            skip_ok=True,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["client"], self.client_a)

    def test_primary_invoice_prefers_draft_then_sent(self):
        draft_inv = Invoice(status=Invoice.Status.DRAFT)
        sent_inv = Invoice(status=Invoice.Status.SENT)
        rows = _build_client_rows(
            [self.client_a],
            invoices_by_client={self.client_a.pk: [sent_inv, draft_inv]},
            billed_session_count_by_client={},
            unbilled_sessions_by_client={},
            pending_by_client={},
            cancelled_billed_by_client={},
        )
        self.assertEqual(rows[0]["primary_invoice"], draft_inv)

    def test_build_billing_summary_counts_by_status(self):
        rows = [{"status": "warning"}, {"status": "warning"}, {"status": "draft"}, {"status": "ok"}]
        summary = _build_billing_summary(rows)
        self.assertEqual(summary, {"total": 4, "warning": 2, "draft": 1, "sent": 0, "ok": 1})


class InvoiceCreateFormValidTests(TestCase):
    """Test InvoiceCreateView.form_valid success/error/exception branches."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="invoice-create-fv",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        self.service_type = ServiceType.objects.create(
            code="individual",
            name="60 Min Session",
            name_de="60 Min. Psychotherapie",
            default_duration=60,
            practice=self.practice,
        )
        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
            active=True,
        )

    def _formset_data(self, **overrides):
        data = {
            "client": str(self.test_client.pk),
            "invoice_number": "",
            "invoice_date": date.today().isoformat(),
            "status": Invoice.Status.DRAFT,
            "tax_rate": "0.00",
            "notes": "",
            "practice": str(self.practice.pk),
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-service_type": str(self.service_type.pk),
            "items-0-rate": "90.00",
            "items-0-session_date": date.today().isoformat(),
            "items-0-duration": "60",
        }
        data.update(overrides)
        return data

    def test_create_success_creates_invoice_and_session(self):
        response = self.client_instance.post(reverse("invoice_create"), self._formset_data())
        self.assertRedirects(response, reverse("invoice_list"))
        invoice = Invoice.objects.get(client=self.test_client)
        self.assertEqual(invoice.items.count(), 1)
        self.assertTrue(Session.objects.filter(client=self.test_client).exists())

    def test_create_invalid_formset_shows_errors_and_rerenders(self):
        # Missing rate on the one required item makes the formset invalid.
        data = self._formset_data(**{"items-0-rate": ""})
        response = self.client_instance.post(reverse("invoice_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/invoice_form.html")
        # No invoice (not even an orphan draft) should be left behind when the
        # item formset fails validation.
        self.assertFalse(Invoice.objects.filter(client=self.test_client).exists())

    def test_create_exception_path_shows_error_message(self):
        # Force an unexpected exception inside the atomic block to exercise
        # the except branch (e.g. a DB-level failure after form validation
        # already passed).
        from unittest.mock import patch

        with patch(
            "my_practice.views.invoice_views.get_next_invoice_number",
            side_effect=RuntimeError("boom"),
        ):
            response = self.client_instance.post(reverse("invoice_create"), self._formset_data())
        self.assertEqual(response.status_code, 200)
        messages = list(response.context["messages"])
        self.assertTrue(any("Fehler beim Erstellen der Rechnung" in str(m) for m in messages))
        self.assertFalse(Invoice.objects.filter(client=self.test_client).exists())


class InvoiceEditFormValidTests(TestCase):
    """Test InvoiceEditView.form_valid/form_invalid branches."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="invoice-edit-fv",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        self.service_type = ServiceType.objects.create(
            code="individual",
            name="60 Min Session",
            name_de="60 Min. Psychotherapie",
            default_duration=60,
            practice=self.practice,
        )
        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
            active=True,
        )
        self.invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            status=Invoice.Status.DRAFT,
            total=Decimal("90.00"),
            practice=self.practice,
        )
        self.session_obj = Session.objects.create(
            client=self.test_client, session_date=date.today(), duration=60
        )
        self.item = InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=self.session_obj,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
            total=Decimal("90.00"),
        )

    def _formset_data(self, **overrides):
        data = {
            "client": str(self.test_client.pk),
            "invoice_number": self.invoice.invoice_number,
            "invoice_date": self.invoice.invoice_date.isoformat(),
            "status": Invoice.Status.DRAFT,
            "tax_rate": "0.00",
            "notes": "",
            "practice": str(self.practice.pk),
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "1",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-id": str(self.item.pk),
            "items-0-service_type": str(self.service_type.pk),
            "items-0-rate": "95.00",
            "items-0-session_date": date.today().isoformat(),
            "items-0-duration": "60",
        }
        data.update(overrides)
        return data

    def test_edit_success_updates_invoice(self):
        response = self.client_instance.post(
            reverse("invoice_edit", kwargs={"pk": self.invoice.pk}), self._formset_data()
        )
        self.assertRedirects(response, reverse("invoice_detail", kwargs={"pk": self.invoice.pk}))
        self.item.refresh_from_db()
        self.assertEqual(self.item.rate, Decimal("95.00"))

    def test_edit_success_redirects_to_next_param(self):
        next_url = reverse("invoice_list")
        response = self.client_instance.post(
            reverse("invoice_edit", kwargs={"pk": self.invoice.pk}) + f"?next={next_url}",
            self._formset_data(),
        )
        self.assertRedirects(response, next_url)

    def test_edit_invalid_formset_shows_item_errors(self):
        data = self._formset_data(**{"items-0-rate": ""})
        response = self.client_instance.post(
            reverse("invoice_edit", kwargs={"pk": self.invoice.pk}), data
        )
        self.assertEqual(response.status_code, 200)
        messages = list(response.context["messages"])
        self.assertTrue(any("rate" in str(m) and "1" in str(m) for m in messages))

    def test_edit_invalid_main_form_shows_field_errors(self):
        data = self._formset_data(**{"client": ""})
        response = self.client_instance.post(
            reverse("invoice_edit", kwargs={"pk": self.invoice.pk}), data
        )
        self.assertEqual(response.status_code, 200)
        messages = list(response.context["messages"])
        self.assertTrue(len(messages) > 0)


class InvoiceDeleteTests(TestCase):
    """Test invoice_delete GET (confirmation) and POST (deletion)."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="invoice-delete",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        self.invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            total=Decimal("90.00"),
            practice=self.practice,
        )

    def test_get_shows_confirmation_page(self):
        response = self.client_instance.get(
            reverse("invoice_delete", kwargs={"pk": self.invoice.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/invoice_confirm_delete.html")

    def test_post_deletes_invoice_and_redirects(self):
        response = self.client_instance.post(
            reverse("invoice_delete", kwargs={"pk": self.invoice.pk})
        )
        self.assertRedirects(response, reverse("invoice_list"))
        self.assertFalse(Invoice.objects.filter(pk=self.invoice.pk).exists())

    def test_post_redirects_to_next_param(self):
        next_url = reverse("client_detail", kwargs={"pk": self.test_client.pk})
        response = self.client_instance.post(
            reverse("invoice_delete", kwargs={"pk": self.invoice.pk}) + f"?next={next_url}"
        )
        self.assertRedirects(response, next_url)


class AddSessionsToInvoiceTests(TestCase):
    """Test add_sessions_to_invoice view."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="add-sessions",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        self.service_type = ServiceType.objects.create(
            code="individual",
            name="60 Min Session",
            default_duration=60,
            practice=self.practice,
        )
        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        self.invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            status=Invoice.Status.DRAFT,
            total=Decimal("0.00"),
            practice=self.practice,
        )
        self.session1 = Session.objects.create(
            client=self.test_client, session_date=date.today(), duration=60
        )
        self.session2 = Session.objects.create(
            client=self.test_client, session_date=date.today() - timedelta(days=1), duration=60
        )

    def test_no_session_ids_shows_warning(self):
        response = self.client_instance.post(
            reverse("invoice_add_sessions", kwargs={"pk": self.invoice.pk}), follow=True
        )
        self.assertRedirects(response, reverse("invoice_detail", kwargs={"pk": self.invoice.pk}))
        messages = list(response.context["messages"])
        self.assertTrue(any("Keine Sitzungen angegeben" in str(m) for m in messages))

    def test_adds_sessions_and_recalculates_total(self):
        response = self.client_instance.post(
            reverse("invoice_add_sessions", kwargs={"pk": self.invoice.pk}),
            {"session_ids": [self.session1.pk, self.session2.pk]},
        )
        self.assertRedirects(response, reverse("invoice_detail", kwargs={"pk": self.invoice.pk}))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.items.count(), 2)
        self.assertEqual(self.invoice.total, Decimal("180.00"))

    def test_already_billed_sessions_add_nothing(self):
        # Bill session1 elsewhere first via a separate non-cancelled invoice item.
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=self.session1,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
            total=Decimal("90.00"),
        )
        response = self.client_instance.post(
            reverse("invoice_add_sessions", kwargs={"pk": self.invoice.pk}),
            {"session_ids": [self.session1.pk]},
            follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("Keine neuen Sitzungen hinzugefügt" in str(m) for m in messages))

    def test_get_request_redirects_without_action(self):
        response = self.client_instance.get(
            reverse("invoice_add_sessions", kwargs={"pk": self.invoice.pk})
        )
        self.assertRedirects(response, reverse("invoice_detail", kwargs={"pk": self.invoice.pk}))


class CreateInvoiceWithSessionsTests(TestCase):
    """Test create_invoice_with_sessions view."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="create-with-sessions",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        ServiceType.objects.create(
            code="individual",
            name="60 Min Session",
            default_duration=60,
            practice=self.practice,
        )
        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        self.session1 = Session.objects.create(
            client=self.test_client, session_date=date.today(), duration=60
        )

    def test_no_sessions_shows_warning_redirects_to_list(self):
        response = self.client_instance.post(
            reverse("invoice_create_with_sessions"), {"client_id": self.test_client.pk}
        )
        self.assertRedirects(response, reverse("invoice_list"))

    def test_creates_draft_invoice_with_sessions(self):
        response = self.client_instance.post(
            reverse("invoice_create_with_sessions"),
            {"client_id": self.test_client.pk, "session_ids": [self.session1.pk]},
        )
        invoice = Invoice.objects.get(client=self.test_client)
        self.assertRedirects(response, reverse("invoice_detail", kwargs={"pk": invoice.pk}))
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)
        self.assertEqual(invoice.items.count(), 1)

    def test_get_request_redirects_to_list(self):
        response = self.client_instance.get(reverse("invoice_create_with_sessions"))
        self.assertRedirects(response, reverse("invoice_list"))


class MonthlyBillingOverviewTests(TestCase):
    """Test monthly_billing_overview and billing_open_overview."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="monthly-billing",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )

    def test_invalid_month_redirects(self):
        response = self.client_instance.get(
            reverse("monthly_billing_overview", kwargs={"month": "not-a-month"})
        )
        # monthly_billing itself redirects on to the current month, so don't
        # fetch the target (that's covered by test_redirect_view_uses_current_month).
        self.assertRedirects(response, reverse("monthly_billing"), fetch_redirect_response=False)

    def test_redirect_view_uses_current_month(self):
        response = self.client_instance.get(reverse("monthly_billing"))
        today = date.today()
        self.assertRedirects(
            response,
            reverse(
                "monthly_billing_overview", kwargs={"month": f"{today.year}-{today.month:02d}"}
            ),
        )

    def test_shows_unbilled_session_as_warning_row(self):
        today = date.today()
        Session.objects.create(client=self.test_client, session_date=today, duration=60)
        month_str = f"{today.year}-{today.month:02d}"
        response = self.client_instance.get(
            reverse("monthly_billing_overview", kwargs={"month": month_str})
        )
        self.assertEqual(response.status_code, 200)
        rows = response.context["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "warning")
        self.assertEqual(rows[0]["unbilled_count"], 1)

    def test_pending_calendar_event_counts_as_pending(self):
        today = date.today()
        PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="evt-1",
            summary="Termin",
            event_date=today,
            duration_minutes=60,
            matched_client=self.test_client,
            status=PendingCalendarEvent.Status.PENDING,
        )
        month_str = f"{today.year}-{today.month:02d}"
        response = self.client_instance.get(
            reverse("monthly_billing_overview", kwargs={"month": month_str})
        )
        rows = response.context["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pending_count"], 1)

    def test_billing_open_overview_aggregates_open_months(self):
        today = date.today()
        Session.objects.create(client=self.test_client, session_date=today, duration=60)
        response = self.client_instance.get(reverse("billing_open_overview"))
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.context["total_unresolved"], 1)

    def test_billing_open_overview_skips_fully_ok_months(self):
        # No open invoices, no unbilled sessions, no pending events anywhere.
        response = self.client_instance.get(reverse("billing_open_overview"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_unresolved"], 0)
