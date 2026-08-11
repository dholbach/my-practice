"""
Tests for free-form (non-session) invoice items — P-122 Phase 1.

Covers: InvoiceItem model validation (session/description XOR, practice
gating), InvoiceItemForm behavior, count_sessions() exclusion, and the
create/edit view formset flow.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..invoice_forms import InvoiceItemForm
from ..models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session, UserPractice
from ..utils.calculations import count_sessions


def _make_practice(**kwargs):
    defaults = dict(
        name="Test Practice",
        title="Test Practitioner",
        email="test@practice.com",
        city="Berlin",
    )
    defaults.update(kwargs)
    return Practice.objects.create(**defaults)


class InvoiceItemFreeFormModelTests(TestCase):
    def setUp(self):
        self.practice = _make_practice(slug="p122-model", allows_free_form_items=True)
        self.strict_practice = _make_practice(
            slug="p122-model-strict", allows_free_form_items=False
        )
        self.client_obj = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        self.service_type = ServiceType.objects.create(
            code="day_rate",
            name="Consulting (day rate)",
            practice=self.practice,
        )
        self.invoice = Invoice.objects.create(
            client=self.client_obj,
            invoice_number="TC-1",
            invoice_date=date(2026, 1, 1),
            status="draft",
            practice=self.practice,
        )

    def test_free_form_item_saves_without_session(self):
        item = InvoiceItem(
            invoice=self.invoice,
            service_type=self.service_type,
            description="IT consulting, 3 days",
            rate=Decimal("800.00"),
            quantity=Decimal("3.00"),
        )
        item.save()
        self.assertIsNone(item.session_id)
        self.assertEqual(item.total, Decimal("2400.00"))

    def test_neither_session_nor_description_raises(self):
        item = InvoiceItem(
            invoice=self.invoice,
            service_type=self.service_type,
            rate=Decimal("90.00"),
        )
        with self.assertRaises(ValidationError):
            item.save()

    def test_both_session_and_description_raises(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 1, 5), duration=60
        )
        item = InvoiceItem(
            invoice=self.invoice,
            service_type=self.service_type,
            session=session,
            description="Shouldn't have both",
            rate=Decimal("90.00"),
        )
        with self.assertRaises(ValidationError):
            item.save()

    def test_description_only_rejected_when_practice_disallows(self):
        client_obj = Client.objects.create(
            client_code="SC",
            full_name="Anna Schmidt",
            hourly_rate_60=Decimal("90.00"),
            practice=self.strict_practice,
        )
        service_type = ServiceType.objects.create(
            code="therapy", name="Therapy", practice=self.strict_practice
        )
        invoice = Invoice.objects.create(
            client=client_obj,
            invoice_number="SC-1",
            invoice_date=date(2026, 1, 1),
            status="draft",
            practice=self.strict_practice,
        )
        item = InvoiceItem(
            invoice=invoice,
            service_type=service_type,
            description="Not allowed here",
            rate=Decimal("90.00"),
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_str_falls_back_to_description(self):
        item = InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            description="Workshop day",
            rate=Decimal("500.00"),
        )
        self.assertIn("Workshop day", str(item))


class CountSessionsFreeFormTests(TestCase):
    def setUp(self):
        self.practice = _make_practice(slug="p122-count", allows_free_form_items=True)
        self.client_obj = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
        )
        self.session_service = ServiceType.objects.create(
            code="therapy_60", name="60 Min", practice=self.practice
        )
        self.day_rate_service = ServiceType.objects.create(
            code="day_rate", name="Day rate", practice=self.practice
        )
        self.invoice = Invoice.objects.create(
            client=self.client_obj,
            invoice_date=date(2026, 1, 1),
            status="draft",
            practice=self.practice,
        )

    def test_free_form_item_excluded_from_session_count(self):
        session = Session.objects.create(
            client=self.client_obj, session_date=date(2026, 1, 5), duration=60
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.session_service,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.day_rate_service,
            description="3 consulting days",
            rate=Decimal("800.00"),
            quantity=Decimal("3.00"),
        )

        items = self.invoice.items.select_related("session").all()
        # Only the session-linked item (1.0) counts; the free-form item
        # (quantity=3) is excluded entirely, not counted as 3.0 sessions.
        self.assertEqual(count_sessions(items), 1.0)


class InvoiceItemFormFreeFormTests(TestCase):
    def setUp(self):
        self.allowing_practice = _make_practice(slug="p122-form-yes", allows_free_form_items=True)
        self.strict_practice = _make_practice(slug="p122-form-no", allows_free_form_items=False)

    def _request_for(self, practice):
        class FakeRequest:
            current_practice = practice

        return FakeRequest()

    def test_description_field_present_when_allowed(self):
        form = InvoiceItemForm(request=self._request_for(self.allowing_practice))
        self.assertIn("description", form.fields)

    def test_description_field_absent_when_disallowed(self):
        form = InvoiceItemForm(request=self._request_for(self.strict_practice))
        self.assertNotIn("description", form.fields)

    def test_valid_free_form_row(self):
        service_type = ServiceType.objects.create(
            code="day_rate", name="Day rate", practice=self.allowing_practice
        )
        form = InvoiceItemForm(
            data={
                "service_type": service_type.pk,
                "rate": "800.00",
                "quantity": "2.00",
                "description": "2 consulting days",
                "session_date": "",
                "duration": "",
            },
            request=self._request_for(self.allowing_practice),
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_neither_session_nor_description_is_invalid(self):
        service_type = ServiceType.objects.create(
            code="day_rate", name="Day rate", practice=self.allowing_practice
        )
        form = InvoiceItemForm(
            data={
                "service_type": service_type.pk,
                "rate": "800.00",
                "quantity": "1.00",
                "description": "",
                "session_date": "",
                "duration": "",
            },
            request=self._request_for(self.allowing_practice),
        )
        self.assertFalse(form.is_valid())

    def test_both_session_and_description_is_invalid(self):
        service_type = ServiceType.objects.create(
            code="day_rate", name="Day rate", practice=self.allowing_practice
        )
        form = InvoiceItemForm(
            data={
                "service_type": service_type.pk,
                "rate": "800.00",
                "quantity": "1.00",
                "description": "Consulting",
                "session_date": "2026-01-05",
                "duration": "60",
            },
            request=self._request_for(self.allowing_practice),
        )
        self.assertFalse(form.is_valid())


class InvoiceCreateFreeFormViewTests(TestCase):
    def setUp(self):
        self.practice = _make_practice(slug="p122-view-create", allows_free_form_items=True)
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser", password="testpass123")

        self.service_type = ServiceType.objects.create(
            code="day_rate",
            name="Consulting (day rate)",
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
            "items-0-rate": "800.00",
            "items-0-quantity": "3.00",
            "items-0-description": "IT consulting, 3 days",
            "items-0-session_date": "",
            "items-0-duration": "",
        }
        data.update(overrides)
        return data

    def test_create_free_form_invoice_item_no_session(self):
        response = self.client_instance.post(reverse("invoice_create"), self._formset_data())
        self.assertRedirects(response, reverse("invoice_list"))
        invoice = Invoice.objects.get(client=self.test_client)
        item = invoice.items.get()
        self.assertIsNone(item.session_id)
        self.assertEqual(item.description, "IT consulting, 3 days")
        self.assertEqual(item.total, Decimal("2400.00"))
        self.assertFalse(Session.objects.filter(client=self.test_client).exists())


class InvoiceCreateFreeFormDisallowedTests(TestCase):
    """A practice without allows_free_form_items can't submit a free-form row."""

    def setUp(self):
        self.practice = _make_practice(slug="p122-view-disallowed", allows_free_form_items=False)
        self.user = User.objects.create_user(username="testuser2", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser2", password="testpass123")

        self.service_type = ServiceType.objects.create(
            code="therapy_60", name="60 Min", practice=self.practice
        )
        self.test_client = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.practice,
            active=True,
        )

    def test_free_form_fields_ignored_when_not_allowed(self):
        """description isn't a form field for this practice, so posting it is a no-op
        and the row still needs a session_date to be considered filled in."""
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
            "items-0-description": "Should be ignored",
            "items-0-session_date": "",
            "items-0-duration": "",
        }
        response = self.client_instance.post(reverse("invoice_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Invoice.objects.filter(client=self.test_client).exists())
