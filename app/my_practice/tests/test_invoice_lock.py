"""Tests for the issued-invoice lock (models/invoice.py, signals.py).

Once an invoice leaves DRAFT, what the client was sent — number, client, date,
tax rate, totals and line items — is frozen, and the invoice can only be
deleted after its § 147 AO retention period. A mistake is corrected by
cancelling the invoice and correcting a copy.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.db import transaction
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from ..admin.invoice import InvoiceAdmin, InvoiceAdminForm, InvoiceItemInline
from ..models import (
    INVOICE_RETENTION_YEARS,
    Client,
    Invoice,
    InvoiceItem,
    InvoiceLockedError,
    ServiceType,
    Session,
    allow_issued_invoice_writes,
)
from .test_helpers import BaseTestCase


class InvoiceLockFixtureMixin:
    """A client, a service type and a helper for invoices with one item."""

    def setUp(self):
        super().setUp()
        self.service_type = ServiceType.objects.create(
            code="individual",
            name="60 Min Session",
            default_duration=60,
            practice=self.practice,
        )
        self.client_obj = Client.objects.create(
            client_code="XX",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        self._number = 0

    def make_invoice(self, status=Invoice.Status.DRAFT, invoice_date=None, with_item=True):
        """Build as a draft, then issue — the way the app itself does it."""
        self._number += 1
        invoice = Invoice.objects.create(
            practice=self.practice,
            client=self.client_obj,
            invoice_number=f"XX-{self._number}",
        )
        if with_item:
            self.add_item(invoice)
        invoice.refresh_from_db()
        if invoice_date or status != Invoice.Status.DRAFT:
            invoice.invoice_date = invoice_date or invoice.invoice_date
            invoice.status = status
            invoice.save()
        return invoice

    def add_item(self, invoice, days_ago=1):
        session = Session.objects.create(
            client=self.client_obj,
            session_date=timezone.localdate() - timedelta(days=days_ago + self._number * 10),
            duration=60,
        )
        return InvoiceItem.objects.create(
            invoice=invoice,
            session=session,
            service_type=self.service_type,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )

    def expired_date(self):
        """An invoice date whose retention period has run out."""
        return date(timezone.localdate().year - INVOICE_RETENTION_YEARS - 1, 6, 1)


class InvoiceModelLockTests(InvoiceLockFixtureMixin, BaseTestCase):
    def test_draft_is_freely_editable_and_deletable(self):
        invoice = self.make_invoice()
        invoice.tax_rate = Decimal("19.00")
        invoice.save()
        self.add_item(invoice, days_ago=3)
        invoice.items.first().delete()
        invoice.delete()
        self.assertFalse(Invoice.objects.filter(pk=invoice.pk).exists())

    def test_issuing_save_may_still_carry_content(self):
        # The draft -> sent save itself is checked against the stored draft.
        invoice = self.make_invoice()
        invoice.status = Invoice.Status.SENT
        invoice.invoice_date = date(2026, 1, 15)
        invoice.save()
        invoice.refresh_from_db()
        self.assertEqual(invoice.invoice_date, date(2026, 1, 15))

    def test_issued_content_fields_are_frozen(self):
        invoice = self.make_invoice(Invoice.Status.SENT)
        changes = {
            "invoice_number": "XX-99",
            "invoice_date": invoice.invoice_date - timedelta(days=1),
            "tax_rate": Decimal("19.00"),
            "total": invoice.total + 1,
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                stale = Invoice.objects.get(pk=invoice.pk)
                setattr(stale, field, value)
                with self.assertRaises(InvoiceLockedError):
                    stale.save(skip_validation=True)

    def test_issued_client_is_frozen(self):
        invoice = self.make_invoice(Invoice.Status.SENT)
        other = Client.objects.create(
            client_code="YY", full_name="Anna Schmidt", practice=self.practice
        )
        invoice.client = other
        with self.assertRaises(InvoiceLockedError):
            invoice.save()

    def test_status_paid_date_and_notes_stay_editable(self):
        invoice = self.make_invoice(Invoice.Status.SENT)
        invoice.status = Invoice.Status.PAID
        invoice.paid_date = timezone.localdate()
        invoice.notes = "Paid in cash"
        invoice.save()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(invoice.notes, "Paid in cash")

    def test_issued_invoice_cannot_go_back_to_draft(self):
        invoice = self.make_invoice(Invoice.Status.SENT)
        invoice.status = Invoice.Status.DRAFT
        with self.assertRaises(InvoiceLockedError):
            invoice.save()

    def test_update_fields_save_ignores_unwritten_stale_fields(self):
        # e.g. a bank import saving only the status of an instance whose total
        # was computed differently in memory — nothing locked gets written.
        invoice = self.make_invoice(Invoice.Status.SENT)
        invoice.total = Decimal("1.00")
        invoice.status = Invoice.Status.PAID
        invoice.save(update_fields=["status"])
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(invoice.total, Decimal("90.00"))

    def test_items_of_issued_invoice_are_frozen(self):
        invoice = self.make_invoice(Invoice.Status.SENT)
        item = invoice.items.get()

        with self.assertRaises(InvoiceLockedError):
            self.add_item(invoice, days_ago=5)
        item.rate = Decimal("1.00")
        with self.assertRaises(InvoiceLockedError):
            item.save()
        # Deletes raise inside Django's own atomic block; the savepoint keeps
        # the test transaction usable afterwards.
        with self.assertRaises(InvoiceLockedError), transaction.atomic():
            InvoiceItem.objects.get(pk=item.pk).delete()
        with self.assertRaises(InvoiceLockedError), transaction.atomic():
            InvoiceItem.objects.filter(pk=item.pk).delete()

    def test_item_cannot_be_moved_off_an_issued_invoice(self):
        issued = self.make_invoice(Invoice.Status.SENT)
        draft = self.make_invoice(with_item=False)
        item = issued.items.get()
        item.invoice = draft
        with self.assertRaises(InvoiceLockedError):
            item.save()

    def test_issued_invoice_cannot_be_deleted_within_retention(self):
        invoice = self.make_invoice(Invoice.Status.PAID)
        with self.assertRaises(InvoiceLockedError), transaction.atomic():
            invoice.delete()
        with self.assertRaises(InvoiceLockedError), transaction.atomic():
            Invoice.objects.filter(pk=invoice.pk).delete()
        self.assertTrue(Invoice.objects.filter(pk=invoice.pk).exists())

    def test_cancelled_invoice_is_kept_too(self):
        invoice = self.make_invoice(Invoice.Status.CANCELLED)
        with self.assertRaises(InvoiceLockedError), transaction.atomic():
            invoice.delete()

    def test_issued_invoice_past_retention_can_be_deleted_with_its_items(self):
        invoice = self.make_invoice(Invoice.Status.PAID, invoice_date=self.expired_date())
        self.assertFalse(invoice.is_protected)
        Invoice.objects.filter(pk=invoice.pk).delete()
        self.assertFalse(InvoiceItem.objects.filter(invoice_id=invoice.pk).exists())

    def test_retention_counts_from_the_end_of_the_issue_year(self):
        invoice = Invoice(invoice_date=date(2026, 12, 31), status=Invoice.Status.SENT)
        self.assertEqual(invoice.retention_end_year, 2036)
        self.assertFalse(invoice.retention_expired(today=date(2036, 12, 31)))
        self.assertTrue(invoice.retention_expired(today=date(2037, 1, 1)))

    def test_historical_writes_can_bypass_the_lock_explicitly(self):
        invoice = self.make_invoice(Invoice.Status.PAID)
        with allow_issued_invoice_writes():
            self.add_item(invoice, days_ago=5)
        self.assertEqual(invoice.items.count(), 2)
        # ...and only inside the block.
        with self.assertRaises(InvoiceLockedError):
            self.add_item(invoice, days_ago=7)


class InvoiceViewLockTests(InvoiceLockFixtureMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="testuser", password="testpass123")

    def _form_data(self, invoice=None, **overrides):
        item = invoice.items.first() if invoice else None
        data = {
            "client": str(self.client_obj.pk),
            "invoice_number": invoice.invoice_number if invoice else "",
            "invoice_date": "2026-03-01",
            "status": Invoice.Status.DRAFT,
            "tax_rate": "0.00",
            "notes": "",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "1" if item else "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-service_type": str(self.service_type.pk),
            "items-0-rate": "95.00",
            "items-0-session_date": "2026-02-27",
            "items-0-duration": "60",
        }
        if item:
            data["items-0-id"] = str(item.pk)
        data.update(overrides)
        return data

    def test_edit_page_of_issued_invoice_redirects_to_detail(self):
        invoice = self.make_invoice(Invoice.Status.SENT)
        url = reverse("invoice_edit", kwargs={"pk": invoice.pk})
        detail = reverse("invoice_detail", kwargs={"pk": invoice.pk})

        self.assertRedirects(self.client.get(url), detail)
        self.assertRedirects(self.client.post(url, self._form_data(invoice)), detail)
        self.assertEqual(invoice.items.get().rate, Decimal("90.00"))

    def test_create_as_sent_saves_items_and_keeps_the_entered_date(self):
        response = self.client.post(
            reverse("invoice_create"), self._form_data(status=Invoice.Status.SENT)
        )
        self.assertRedirects(response, reverse("invoice_list"))
        invoice = Invoice.objects.get(client=self.client_obj)
        self.assertEqual(invoice.status, Invoice.Status.SENT)
        self.assertEqual(invoice.items.count(), 1)
        self.assertEqual(invoice.total, Decimal("95.00"))
        self.assertEqual(invoice.invoice_date, date(2026, 3, 1))

    def test_editing_a_draft_and_issuing_it_in_one_submit(self):
        invoice = self.make_invoice()
        response = self.client.post(
            reverse("invoice_edit", kwargs={"pk": invoice.pk}),
            self._form_data(invoice, status=Invoice.Status.SENT),
        )
        self.assertRedirects(response, reverse("invoice_detail", kwargs={"pk": invoice.pk}))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.SENT)
        self.assertEqual(invoice.total, Decimal("95.00"))

    def test_delete_refuses_issued_invoice(self):
        invoice = self.make_invoice(Invoice.Status.SENT)
        response = self.client.post(reverse("invoice_delete", kwargs={"pk": invoice.pk}))
        self.assertRedirects(response, reverse("invoice_detail", kwargs={"pk": invoice.pk}))
        self.assertTrue(Invoice.objects.filter(pk=invoice.pk).exists())

    def test_delete_still_works_for_drafts(self):
        invoice = self.make_invoice()
        self.client.post(reverse("invoice_delete", kwargs={"pk": invoice.pk}))
        self.assertFalse(Invoice.objects.filter(pk=invoice.pk).exists())

    def test_status_endpoint_refuses_back_to_draft(self):
        invoice = self.make_invoice(Invoice.Status.SENT)
        url = reverse("update_invoice_status", kwargs={"pk": invoice.pk})

        self.assertEqual(self.client.post(url, {"status": "draft"}).status_code, 400)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.SENT)

        self.assertEqual(self.client.post(url, {"status": "paid"}).status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    def test_cancel_and_correct_creates_editable_copy(self):
        invoice = self.make_invoice(Invoice.Status.SENT)

        response = self.client.post(
            reverse("invoice_cancel_and_correct", kwargs={"pk": invoice.pk})
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.CANCELLED)
        self.assertEqual(invoice.items.count(), 1, "the cancelled original keeps its items")
        copy = Invoice.objects.exclude(pk=invoice.pk).get(client=self.client_obj)
        self.assertEqual(copy.status, Invoice.Status.DRAFT)
        self.assertEqual(copy.invoice_number, "XX-2")
        self.assertEqual(copy.total, invoice.total)
        self.assertEqual(
            list(copy.items.values_list("session_id", flat=True)),
            list(invoice.items.values_list("session_id", flat=True)),
        )
        self.assertIn(invoice.invoice_number, copy.notes)
        self.assertRedirects(response, reverse("invoice_edit", kwargs={"pk": copy.pk}))

    def test_cancel_and_correct_only_for_sent(self):
        for status in (Invoice.Status.DRAFT, Invoice.Status.PAID, Invoice.Status.CANCELLED):
            with self.subTest(status=status):
                invoice = self.make_invoice(status)
                self.client.post(reverse("invoice_cancel_and_correct", kwargs={"pk": invoice.pk}))
                invoice.refresh_from_db()
                self.assertEqual(invoice.status, status)
        self.assertEqual(Invoice.objects.count(), 3)

    def test_cancel_and_correct_rejects_get(self):
        invoice = self.make_invoice(Invoice.Status.SENT)
        response = self.client.get(reverse("invoice_cancel_and_correct", kwargs={"pk": invoice.pk}))
        self.assertEqual(response.status_code, 405)

    def test_detail_page_hides_edit_delete_and_draft_for_issued(self):
        sent = self.make_invoice(Invoice.Status.SENT)
        html = self.client.get(reverse("invoice_detail", kwargs={"pk": sent.pk})).content.decode()
        self.assertNotIn(reverse("invoice_edit", kwargs={"pk": sent.pk}), html)
        self.assertNotIn(reverse("invoice_delete", kwargs={"pk": sent.pk}), html)
        self.assertNotIn('value="draft"', html)
        self.assertIn(reverse("invoice_cancel_and_correct", kwargs={"pk": sent.pk}), html)

        draft = self.make_invoice()
        html = self.client.get(reverse("invoice_detail", kwargs={"pk": draft.pk})).content.decode()
        self.assertIn(reverse("invoice_edit", kwargs={"pk": draft.pk}), html)
        self.assertIn(reverse("invoice_delete", kwargs={"pk": draft.pk}), html)
        self.assertNotIn(reverse("invoice_cancel_and_correct", kwargs={"pk": draft.pk}), html)


class InvoiceAdminLockTests(InvoiceLockFixtureMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.admin = InvoiceAdmin(Invoice, AdminSite())
        self.request = RequestFactory().get("/")
        self.request.user = User.objects.create_superuser("admin", "admin@example.com", "pw")

    def test_issued_invoice_is_read_only_in_admin(self):
        invoice = self.make_invoice(Invoice.Status.SENT)
        readonly = self.admin.get_readonly_fields(self.request, invoice)
        for field in ("invoice_number", "client", "invoice_date", "tax_rate"):
            self.assertIn(field, readonly)
        self.assertNotIn("status", readonly)
        self.assertFalse(self.admin.has_delete_permission(self.request, invoice))
        inline = InvoiceItemInline(Invoice, AdminSite())
        self.assertFalse(inline.has_add_permission(self.request, invoice))
        self.assertFalse(inline.has_change_permission(self.request, invoice))
        self.assertFalse(inline.has_delete_permission(self.request, invoice))

    def test_draft_stays_editable_in_admin(self):
        draft = self.make_invoice()
        self.assertNotIn("invoice_number", self.admin.get_readonly_fields(self.request, draft))
        self.assertTrue(self.admin.has_delete_permission(self.request, draft))

    def test_admin_form_refuses_back_to_draft(self):
        invoice = self.make_invoice(Invoice.Status.SENT)
        form = InvoiceAdminForm(
            instance=invoice,
            data={
                "invoice_number": invoice.invoice_number,
                "client": invoice.client_id,
                "invoice_date": invoice.invoice_date,
                "status": "draft",
                "tax_rate": "0.00",
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_saving_status_keeps_stored_totals_even_if_items_disagree(self):
        invoice = self.make_invoice(Invoice.Status.SENT)
        # Older data: a stored total that no longer matches the items.
        Invoice.objects.filter(pk=invoice.pk).update(total=Decimal("80.00"))
        invoice.refresh_from_db()
        invoice.status = Invoice.Status.PAID
        invoice.paid_date = timezone.localdate()

        self.admin.save_model(self.request, invoice, form=None, change=True)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(invoice.total, Decimal("80.00"))

    def test_bulk_delete_keeps_protected_invoices(self):
        draft = self.make_invoice()
        issued = self.make_invoice(Invoice.Status.PAID)
        with patch.object(self.admin, "message_user") as message_user:
            self.admin.delete_queryset(self.request, Invoice.objects.all())
        self.assertFalse(Invoice.objects.filter(pk=draft.pk).exists())
        self.assertTrue(Invoice.objects.filter(pk=issued.pk).exists())
        message_user.assert_called_once()


class GdprDeletionRetentionTests(InvoiceLockFixtureMixin, BaseTestCase):
    """GDPR erasure respects invoice retention and works for billed clients."""

    def setUp(self):
        super().setUp()
        self.client.login(username="testuser", password="testpass123")
        self.client_obj.active = False
        self.client_obj.save()

    def _make_old_invoice(self, invoice_date):
        # Billed sessions long ago, so only the invoice rule decides.
        old_session = Session.objects.create(
            client=self.client_obj, session_date=date(2010, 5, 1), duration=60
        )
        with allow_issued_invoice_writes():
            invoice = Invoice.objects.create(
                practice=self.practice,
                client=self.client_obj,
                invoice_number=f"XX-{invoice_date.year}",
                invoice_date=invoice_date,
                status=Invoice.Status.PAID,
            )
            InvoiceItem.objects.create(
                invoice=invoice,
                session=old_session,
                service_type=self.service_type,
                rate=Decimal("90.00"),
                quantity=Decimal("1.00"),
            )
            # Invoice.save() dates a new invoice today; put the real date back.
            Invoice.objects.filter(pk=invoice.pk).update(invoice_date=invoice_date)
        return invoice

    @patch("my_practice.views.client_views._send_gdpr_deletion_email")
    def test_billed_client_past_retention_is_erased(self, send_email):
        self._make_old_invoice(self.expired_date())

        self.client.post(reverse("client_gdpr_delete", kwargs={"pk": self.client_obj.pk}))

        self.assertFalse(Client.objects.filter(pk=self.client_obj.pk).exists())
        self.assertFalse(Invoice.objects.filter(client_id=self.client_obj.pk).exists())
        send_email.assert_called_once()

    @patch("my_practice.views.client_views._send_gdpr_deletion_email")
    def test_client_with_retained_invoice_is_refused_before_any_email(self, send_email):
        # Sessions are past the GDPR cutoff, but an invoice dated later is not
        # past its retention yet.
        self._make_old_invoice(date(timezone.localdate().year - INVOICE_RETENTION_YEARS, 1, 5))

        confirm = self.client.get(
            reverse("client_gdpr_delete_confirm", kwargs={"pk": self.client_obj.pk})
        )
        self.client.post(reverse("client_gdpr_delete", kwargs={"pk": self.client_obj.pk}))

        self.assertRedirects(confirm, reverse("client_list"))
        self.assertTrue(Client.objects.filter(pk=self.client_obj.pk).exists())
        send_email.assert_not_called()
