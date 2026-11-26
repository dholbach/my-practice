"""
Tests for the views that act on one session (P-009): duration, billing, no-show, deletion.
"""

from datetime import date
from decimal import Decimal

from django.test import override_settings
from django.urls import reverse

from ..models import (
    Session,
    SessionLog,
)
from .test_clinical import TEST_FERNET_KEY, ClinicalTestBase


class SessionDurationEditViewTests(ClinicalTestBase):
    """Tests for session_duration_edit — updates Session.duration."""

    def test_updates_duration(self):
        """POST with a valid duration updates the session."""
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 15), duration=60
        )
        url = reverse(
            "session_duration_edit", kwargs={"pk": self.client_obj.pk, "session_pk": session.pk}
        )
        self.http.post(url, {"duration": "15"})
        session.refresh_from_db()
        self.assertEqual(session.duration, 15)

    def test_rejects_invalid_duration(self):
        """POST with a non-positive duration leaves the session unchanged."""
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 15), duration=60
        )
        url = reverse(
            "session_duration_edit", kwargs={"pk": self.client_obj.pk, "session_pk": session.pk}
        )
        self.http.post(url, {"duration": "0"})
        session.refresh_from_db()
        self.assertEqual(session.duration, 60)

    def test_rejects_non_numeric_duration(self):
        """POST with a non-numeric duration leaves the session unchanged."""
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 15), duration=60
        )
        url = reverse(
            "session_duration_edit", kwargs={"pk": self.client_obj.pk, "session_pk": session.pk}
        )
        self.http.post(url, {"duration": "not-a-number"})
        session.refresh_from_db()
        self.assertEqual(session.duration, 60)

    def test_rejects_duration_over_one_day(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 15), duration=60
        )
        url = reverse(
            "session_duration_edit", kwargs={"pk": self.client_obj.pk, "session_pk": session.pk}
        )
        self.http.post(url, {"duration": "99999999999"})
        session.refresh_from_db()
        self.assertEqual(session.duration, 60)

    def test_blocked_when_already_billed(self):
        """
        A session with an existing InvoiceItem cannot have its duration edited.

        The invoice item's service_type/rate/total are resolved at billing
        time and are not recalculated here, so allowing the edit would leave
        the invoice showing stale pricing for the session's new duration.
        """
        from ..models import Invoice, InvoiceItem, ServiceType

        service = ServiceType.objects.create(
            code="individual", name_en="Individual Session", name_de="Einzelsitzung"
        )
        invoice = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="TEST-1",
            invoice_date=date(2026, 3, 15),
            practice=self.practice,
        )
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 15), duration=60
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=service,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )
        url = reverse(
            "session_duration_edit", kwargs={"pk": self.client_obj.pk, "session_pk": session.pk}
        )
        self.http.post(url, {"duration": "15"})
        session.refresh_from_db()
        self.assertEqual(session.duration, 60)


@override_settings(FERNET_KEY=TEST_FERNET_KEY)
class SessionQuickActionViewTests(ClinicalTestBase):
    """Tests for session_log_delete, session_delete, session_log_mark_noshow,
    session_toggle_billable, session_bill."""

    def test_delete_session_log_keeps_unbilled_session(self):
        """Deleting the log of a session with no InvoiceItem also deletes the bare Session."""
        session = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 20))
        log = SessionLog.objects.create(session=session, content="x")
        url = reverse(
            "session_log_delete", kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk}
        )
        self.http.post(url)
        self.assertFalse(SessionLog.objects.filter(pk=log.pk).exists())
        self.assertFalse(Session.objects.filter(pk=session.pk).exists())

    def test_delete_session_log_keeps_billed_session(self):
        """Deleting the log of an already-billed session keeps the Session (only the log goes)."""
        from ..models import Invoice, InvoiceItem, ServiceType

        service = ServiceType.objects.create(
            code="individual", name_en="Individual Session", name_de="Einzelsitzung"
        )
        invoice = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="TEST-2",
            invoice_date=date(2026, 3, 20),
            practice=self.practice,
        )
        session = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 20))
        log = SessionLog.objects.create(session=session, content="x")
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=service,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )
        url = reverse(
            "session_log_delete", kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk}
        )
        self.http.post(url)
        self.assertFalse(SessionLog.objects.filter(pk=log.pk).exists())
        self.assertTrue(Session.objects.filter(pk=session.pk).exists())

    def test_delete_bare_session(self):
        session = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 20))
        url = reverse(
            "session_delete", kwargs={"client_pk": self.client_obj.pk, "session_pk": session.pk}
        )
        self.http.post(url)
        self.assertFalse(Session.objects.filter(pk=session.pk).exists())

    def test_delete_blocked_when_billed(self):
        from ..models import Invoice, InvoiceItem, ServiceType

        service = ServiceType.objects.create(
            code="individual", name_en="Individual Session", name_de="Einzelsitzung"
        )
        invoice = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="TEST-3",
            invoice_date=date(2026, 3, 20),
            practice=self.practice,
        )
        session = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 20))
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=service,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )
        url = reverse(
            "session_delete", kwargs={"client_pk": self.client_obj.pk, "session_pk": session.pk}
        )
        self.http.post(url)
        self.assertTrue(Session.objects.filter(pk=session.pk).exists())

    def test_mark_noshow(self):
        session = Session.objects.create(client=self.client_obj, session_date=date(2026, 3, 20))
        log = SessionLog.objects.create(session=session, session_type="standard")
        url = reverse(
            "session_log_mark_noshow",
            kwargs={"client_pk": self.client_obj.pk, "log_pk": log.pk},
        )
        self.http.post(url)
        log.refresh_from_db()
        self.assertEqual(log.session_type, SessionLog.SessionType.AUSFALL)

    def test_toggle_billable(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), billable=True
        )
        url = reverse(
            "session_toggle_billable",
            kwargs={"client_pk": self.client_obj.pk, "session_pk": session.pk},
        )
        self.http.post(url)
        session.refresh_from_db()
        self.assertFalse(session.billable)
        self.http.post(url)
        session.refresh_from_db()
        self.assertTrue(session.billable)

    def test_session_bill_success(self):
        from ..models import ServiceType

        ServiceType.objects.create(
            practice=self.practice,
            code="therapy_60",
            name_en="Therapy 60",
            name_de="Therapie 60",
        )
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        url = reverse("session_bill", kwargs={"pk": self.client_obj.pk, "session_pk": session.pk})
        response = self.http.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(session.invoice_items.exists())

    def test_session_bill_failure_shows_error(self):
        """No matching service type at all → error message, no InvoiceItem created."""
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 3, 20), duration=60
        )
        url = reverse("session_bill", kwargs={"pk": self.client_obj.pk, "session_pk": session.pk})
        response = self.http.post(url, follow=True)
        messages_list = list(response.context["messages"])
        self.assertTrue(any(m.tags == "error" for m in messages_list))
        self.assertFalse(session.invoice_items.exists())
