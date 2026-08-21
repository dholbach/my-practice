"""
Tests for free-form (non-session) invoice items — P-122 Phase 1.

Covers: InvoiceItem model validation (session/description XOR, practice
gating), InvoiceItemForm behavior, count_sessions() exclusion, the
create/edit view formset flow, and the P-122 follow-up fixes for billing
a non-individual counterparty (ClientIntakeForm field visibility,
client-dashboard activity grouping).
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from ..forms import ClientIntakeForm
from ..invoice_forms import InvoiceItemForm
from ..models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session, UserPractice
from ..utils.calculations import count_sessions
from ..utils.client_helpers import annotate_activity_status, group_clients_by_activity


def _make_practice(**kwargs):
    defaults = {
        "name": "Test Practice",
        "title": "Test Practitioner",
        "email": "test@practice.com",
        "city": "Berlin",
    }
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

    def test_free_form_items_sort_deterministically(self):
        """Multiple free-form items all have session=None, so ordering by
        session__session_date alone leaves them tied with no tiebreaker —
        Meta.ordering must include a secondary key (pk)."""
        first = InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            description="Day 1",
            rate=Decimal("800.00"),
        )
        second = InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            description="Day 2",
            rate=Decimal("800.00"),
        )
        third = InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            description="Day 3",
            rate=Decimal("800.00"),
        )
        self.assertEqual(
            list(self.invoice.items.all()),
            [first, second, third],
        )

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

    def test_description_only_rejected_on_create_path(self):
        """Mirrors what InvoiceFormsetMixin/save_new() actually do on create:
        the item's invoice FK isn't attached until immediately before save(),
        so clean() alone (invoice_id still None) can't catch this — save()
        must be the backstop that fires."""
        client_obj = Client.objects.create(
            client_code="SC",
            full_name="Anna Schmidt",
            hourly_rate_60=Decimal("90.00"),
            practice=self.strict_practice,
        )
        service_type = ServiceType.objects.create(
            code="therapy2", name="Therapy", practice=self.strict_practice
        )
        invoice = Invoice.objects.create(
            client=client_obj,
            invoice_number="SC-2",
            invoice_date=date(2026, 1, 1),
            status="draft",
            practice=self.strict_practice,
        )
        item = InvoiceItem(
            service_type=service_type,
            description="Not allowed here",
            rate=Decimal("90.00"),
        )
        # No invoice attached yet — same as during formset validation on
        # create. clean() alone can't see the practice, so it must NOT raise.
        item.clean()

        # Attach the invoice the way save_new() does, right before save().
        item.invoice = invoice
        with self.assertRaises(ValidationError):
            item.save()

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

    def test_quantity_field_present_when_allowed(self):
        form = InvoiceItemForm(request=self._request_for(self.allowing_practice))
        self.assertIn("quantity", form.fields)

    def test_quantity_field_absent_when_disallowed(self):
        """quantity > 1 only makes sense for free-form/day-rate billing — a
        session-linked item always bills at quantity 1, so the field is
        removed entirely for practices that haven't opted in, same as
        description."""
        form = InvoiceItemForm(request=self._request_for(self.strict_practice))
        self.assertNotIn("quantity", form.fields)

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

    def test_zero_quantity_is_rejected_server_side(self):
        """The widget's min="0.01" is a client-side hint only — a crafted POST
        must still be rejected server-side (MinValueValidator on the model
        field), not silently saved as a zero-total line item."""
        service_type = ServiceType.objects.create(
            code="day_rate2", name="Day rate", practice=self.allowing_practice
        )
        form = InvoiceItemForm(
            data={
                "service_type": service_type.pk,
                "rate": "800.00",
                "quantity": "0",
                "description": "2 consulting days",
                "session_date": "",
                "duration": "",
            },
            request=self._request_for(self.allowing_practice),
        )
        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

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

    def test_converting_session_item_to_free_form_is_rejected(self):
        """Blanking session_date on a row that already has a linked Session
        would orphan that Session (no InvoiceItem left pointing to it, so it
        starts showing up as unbilled) — must be rejected, not silently
        allowed."""
        client_obj = Client.objects.create(
            client_code="TC",
            full_name="Max Mustermann",
            hourly_rate_60=Decimal("90.00"),
            practice=self.allowing_practice,
        )
        service_type = ServiceType.objects.create(
            code="therapy_60", name="60 Min", practice=self.allowing_practice
        )
        invoice = Invoice.objects.create(
            client=client_obj,
            invoice_number="TC-1",
            invoice_date=date(2026, 1, 1),
            status="draft",
            practice=self.allowing_practice,
        )
        session_obj = Session.objects.create(
            client=client_obj, session_date=date(2026, 1, 5), duration=60
        )
        item = InvoiceItem.objects.create(
            invoice=invoice,
            service_type=service_type,
            session=session_obj,
            rate=Decimal("90.00"),
            total=Decimal("90.00"),
        )
        form = InvoiceItemForm(
            data={
                "service_type": service_type.pk,
                "rate": "800.00",
                "quantity": "1.00",
                "description": "Switched to free-form",
                "session_date": "",
                "duration": "",
            },
            instance=item,
            request=self._request_for(self.allowing_practice),
        )
        self.assertFalse(form.is_valid())
        session_obj.refresh_from_db()
        self.assertTrue(Session.objects.filter(pk=session_obj.pk).exists())


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


class InvoiceEditFreeFormViewTests(TestCase):
    """invoice_edit.html must round-trip quantity for free-form items —
    a missing field here silently resets quantity/total on every edit."""

    def setUp(self):
        self.practice = _make_practice(slug="p122-view-edit", allows_free_form_items=True)
        self.user = User.objects.create_user(username="testuser3", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.client_instance = TestClient()
        self.client_instance.login(username="testuser3", password="testpass123")

        self.service_type = ServiceType.objects.create(
            code="day_rate", name="Consulting (day rate)", practice=self.practice
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
            total=Decimal("2400.00"),
            practice=self.practice,
        )
        self.item = InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            description="IT consulting, 3 days",
            rate=Decimal("800.00"),
            quantity=Decimal("3.00"),
            total=Decimal("2400.00"),
        )

    def test_edit_form_renders_quantity_input(self):
        response = self.client_instance.get(reverse("invoice_edit", kwargs={"pk": self.invoice.pk}))
        self.assertContains(response, 'name="items-0-quantity"')
        self.assertContains(response, 'value="3.00"')

    def test_edit_preserves_quantity_on_unrelated_change(self):
        """Editing an unrelated field (rate) must not reset quantity to 1.00."""
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
            "items-0-rate": "850.00",
            "items-0-quantity": "3.00",
            "items-0-description": "IT consulting, 3 days",
            "items-0-session_date": "",
            "items-0-duration": "",
        }
        response = self.client_instance.post(
            reverse("invoice_edit", kwargs={"pk": self.invoice.pk}), data
        )
        self.assertRedirects(response, reverse("invoice_detail", kwargs={"pk": self.invoice.pk}))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("3.00"))
        self.assertEqual(self.item.total, Decimal("2550.00"))


class ClientIntakeFormFreeFormPracticeTests(TestCase):
    """A company counterparty billed via free-form items shouldn't be asked
    for therapy-only details (date of birth, hourly rate, insurance, ...)."""

    def setUp(self):
        self.allowing_practice = _make_practice(
            slug="p122-client-form-yes", allows_free_form_items=True
        )
        self.strict_practice = _make_practice(
            slug="p122-client-form-no", allows_free_form_items=False
        )

    def test_therapy_only_fields_hidden_for_free_form_practice(self):
        request = SimpleNamespace(current_practice=self.allowing_practice)
        form = ClientIntakeForm(request=request)
        for field_name in ClientIntakeForm.THERAPY_ONLY_FIELDS:
            self.assertNotIn(field_name, form.fields)
        self.assertIn("full_name", form.fields)
        self.assertIn("client_code", form.fields)

    def test_therapy_only_fields_shown_for_strict_practice(self):
        request = SimpleNamespace(current_practice=self.strict_practice)
        form = ClientIntakeForm(request=request)
        for field_name in ClientIntakeForm.THERAPY_ONLY_FIELDS:
            self.assertIn(field_name, form.fields)

    def test_therapy_only_fields_shown_without_request(self):
        """No request (e.g. shell/script usage) keeps the full field set."""
        form = ClientIntakeForm()
        for field_name in ClientIntakeForm.THERAPY_ONLY_FIELDS:
            self.assertIn(field_name, form.fields)


class GroupClientsByActivityFreeFormTests(TestCase):
    """A session-less client (free-form-items practice) shouldn't be stuck
    in "needs attention" forever just for never having a session."""

    def test_track_session_inactivity_false_skips_the_inactivity_flag(self):
        practice = _make_practice(slug="p122-group-activity", allows_free_form_items=True)
        client_obj = Client.objects.create(
            client_code="CO",
            full_name="Training Institute GmbH",
            practice=practice,
        )
        annotate_activity_status([client_obj])
        self.assertEqual(client_obj.days_since_session, 9999)  # never had a session

        grouped_default = group_clients_by_activity([client_obj], track_session_inactivity=True)
        self.assertIn(client_obj, grouped_default["needs_attention"])

        grouped_free_form = group_clients_by_activity([client_obj], track_session_inactivity=False)
        self.assertIn(client_obj, grouped_free_form["active_ok"])
        self.assertNotIn(client_obj, grouped_free_form["needs_attention"])

    def test_tag_based_attention_still_applies_when_ignoring_inactivity(self):
        """Skipping the inactivity check must not swallow real attention tags."""
        from ..models import ClientTag

        practice = _make_practice(slug="p122-group-activity-tag", allows_free_form_items=True)
        client_obj = Client.objects.create(
            client_code="CO2",
            full_name="Another Corp",
            practice=practice,
        )
        tag = ClientTag.objects.create(name="Urgent", slug="urgent-p122", category="attention")
        client_obj.tags.add(tag)
        annotate_activity_status([client_obj])

        grouped = group_clients_by_activity([client_obj], track_session_inactivity=False)
        self.assertIn(client_obj, grouped["needs_attention"])
