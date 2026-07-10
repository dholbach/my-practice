"""
Tests for Google Calendar integration views (P-013): OAuth flow, manual
import, the approval queue, and the client-detail quick-action endpoint.
"""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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


class CalendarViewsTestBase(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="calendar-views-test",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="caluser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.http = TestClient()
        self.http.login(username="caluser", password="testpass123")

        self.service_type = ServiceType.objects.create(
            code="therapy_60",
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


class CalendarAuthorizeTest(CalendarViewsTestBase):
    def test_redirects_to_google_authorization_url(self):
        fake_flow = MagicMock()
        fake_flow.authorization_url.return_value = ("https://accounts.google.com/auth", "state123")
        fake_flow.code_verifier = "verifier"
        with patch(
            "my_practice.views.calendar_views.GoogleCalendarOAuth.create_flow",
            return_value=fake_flow,
        ):
            response = self.http.get(reverse("calendar_authorize"))
        self.assertRedirects(
            response, "https://accounts.google.com/auth", fetch_redirect_response=False
        )
        session = self.http.session
        self.assertEqual(session["oauth_state"], "state123")


class CalendarOAuth2CallbackTest(CalendarViewsTestBase):
    def _set_session_state(self, state="state123"):
        session = self.http.session
        session["oauth_state"] = state
        session["oauth_code_verifier"] = "verifier"
        session.save()

    def test_state_mismatch_shows_error(self):
        self._set_session_state("state123")
        response = self.http.get(
            reverse("calendar_oauth2callback") + "?state=wrong&code=abc", follow=True
        )
        self.assertRedirects(response, reverse("dashboard"))
        messages = list(response.context["messages"])
        self.assertTrue(any("OAuth-Statusfehler" in str(m) for m in messages))

    def test_successful_callback_saves_token_and_redirects(self):
        self._set_session_state("state123")
        fake_flow = MagicMock()
        fake_flow.credentials = MagicMock()
        with (
            patch(
                "my_practice.views.calendar_views.GoogleCalendarOAuth.create_flow",
                return_value=fake_flow,
            ),
            patch("my_practice.views.calendar_views.GoogleCalendarOAuth.save_token") as mock_save,
        ):
            response = self.http.get(
                reverse("calendar_oauth2callback") + "?state=state123&code=abc"
            )
        self.assertRedirects(response, reverse("calendar_import"))
        mock_save.assert_called_once()

    def test_token_exchange_failure_shows_error(self):
        self._set_session_state("state123")
        fake_flow = MagicMock()
        fake_flow.fetch_token.side_effect = RuntimeError("boom")
        with patch(
            "my_practice.views.calendar_views.GoogleCalendarOAuth.create_flow",
            return_value=fake_flow,
        ):
            response = self.http.get(
                reverse("calendar_oauth2callback") + "?state=state123&code=abc", follow=True
            )
        self.assertRedirects(response, reverse("dashboard"))
        messages = list(response.context["messages"])
        self.assertTrue(any("Fehler bei der Autorisierung" in str(m) for m in messages))


class CalendarImportViewTest(CalendarViewsTestBase):
    def test_no_service_redirects_to_connect_page(self):
        with patch(
            "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service", return_value=None
        ):
            response = self.http.get(reverse("calendar_import"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/calendar_connect.html")

    def test_no_praxis_calendar_found(self):
        service = MagicMock()
        with (
            patch(
                "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service",
                return_value=service,
            ),
            patch("my_practice.views.calendar_views.find_calendar_by_name", return_value=None),
        ):
            response = self.http.get(reverse("calendar_import"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_events"], 0)

    def test_loads_and_categorizes_events(self):
        service = MagicMock()
        raw_event = {
            "id": "evt-1",
            "summary": f"{self.test_client.client_code} Sitzung",
            "start": {"dateTime": "2026-03-01T10:00:00+01:00"},
            "end": {"dateTime": "2026-03-01T11:00:00+01:00"},
        }
        service.events.return_value.list.return_value.execute.return_value = {"items": [raw_event]}
        with (
            patch(
                "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service",
                return_value=service,
            ),
            patch(
                "my_practice.views.calendar_views.find_calendar_by_name",
                return_value="cal-1",
            ),
        ):
            response = self.http.get(reverse("calendar_import"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_events"], 1)
        self.assertEqual(response.context["ready_count"], 1)
        self.assertIn("cached_events", self.http.session)

    def test_exception_during_fetch_redirects_to_dashboard(self):
        service = MagicMock()
        with (
            patch(
                "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service",
                return_value=service,
            ),
            patch(
                "my_practice.views.calendar_views.find_calendar_by_name",
                side_effect=RuntimeError("api down"),
            ),
        ):
            response = self.http.get(reverse("calendar_import"), follow=True)
        self.assertRedirects(response, reverse("dashboard"))
        messages = list(response.context["messages"])
        self.assertTrue(any("Fehler beim Laden der Kalender-Einträge" in str(m) for m in messages))


class CalendarImportEventsViewTest(CalendarViewsTestBase):
    def test_no_events_selected_returns_400(self):
        response = self.http.post(
            reverse("calendar_import_events"),
            data=json.dumps({"events": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_invalid_json_returns_400(self):
        response = self.http.post(
            reverse("calendar_import_events"), data="not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_uses_fresh_session_cache(self):
        session = self.http.session
        session["cached_events"] = {
            "timestamp": timezone.now().isoformat(),
            "start_date": date.today().isoformat(),
            "end_date": date.today().isoformat(),
            "events": [
                {
                    "id": "evt-1",
                    "summary": "Termin",
                    "start": None,
                    "end": None,
                    "duration_minutes": 60,
                    "matched_client_id": self.test_client.id,
                    "is_cancelled": False,
                    "service_type_id": self.service_type.id,
                }
            ],
        }
        session.save()

        with patch(
            "my_practice.utils.calendar_import_helpers.create_invoice_items_from_events",
            return_value=(1, 0, []),
        ) as mock_create:
            response = self.http.post(
                reverse("calendar_import_events"),
                data=json.dumps({"events": [{"id": "evt-1", "action": "import"}]}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["created"], 1)
        mock_create.assert_called_once()

    def test_stale_cache_falls_back_to_google_service_not_connected(self):
        response = self.http.post(
            reverse("calendar_import_events"),
            data=json.dumps({"events": [{"id": "evt-1", "action": "import"}]}),
            content_type="application/json",
        )
        # No cache at all, and GoogleCalendarOAuth.get_service() will be None
        # in the test environment (no real credentials configured).
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()["success"])

    def test_calendar_not_found_returns_404(self):
        service = MagicMock()
        with (
            patch(
                "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service",
                return_value=service,
            ),
            patch("my_practice.views.calendar_views.find_calendar_by_name", return_value=None),
        ):
            response = self.http.post(
                reverse("calendar_import_events"),
                data=json.dumps({"events": [{"id": "evt-1", "action": "import"}]}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 404)

    def test_fetch_specific_events_failure_returns_500(self):
        service = MagicMock()
        with (
            patch(
                "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service",
                return_value=service,
            ),
            patch(
                "my_practice.views.calendar_views.find_calendar_by_name",
                return_value="cal-1",
            ),
            patch(
                "my_practice.utils.calendar_event_processor.CalendarImportProcessor."
                "fetch_specific_events",
                side_effect=RuntimeError("boom"),
            ),
        ):
            response = self.http.post(
                reverse("calendar_import_events"),
                data=json.dumps({"events": [{"id": "evt-1", "action": "import"}]}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 500)


class CalendarApprovalQueueTest(CalendarViewsTestBase):
    def _make_event(self, event_date, **overrides):
        base = dict(
            practice=self.practice,
            google_event_id=f"evt-{event_date}",
            summary="Termin",
            event_date=event_date,
            duration_minutes=60,
            matched_client=self.test_client,
            suggested_service_type=self.service_type,
            status=PendingCalendarEvent.Status.PENDING,
        )
        base.update(overrides)
        return PendingCalendarEvent.objects.create(**base)

    def test_groups_events_by_client_and_month(self):
        self._make_event(date(2026, 3, 5))
        self._make_event(date(2026, 3, 10))
        response = self.http.get(reverse("calendar_approval_queue"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_pending"], 2)
        self.assertEqual(len(response.context["grouped"]), 1)
        self.assertEqual(response.context["grouped"][0]["count"], 2)

    def test_stale_duplicate_events_are_counted_but_excluded_from_list(self):
        event = self._make_event(date(2026, 3, 5))
        invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date(2026, 3, 5),
            total=Decimal("90.00"),
            practice=self.practice,
        )
        session = Session.objects.create(
            client=self.test_client, session_date=date(2026, 3, 5), duration=60
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
            total=Decimal("90.00"),
        )
        response = self.http.get(reverse("calendar_approval_queue"))
        self.assertEqual(response.context["stale_count"], 1)
        self.assertEqual(response.context["grouped"], [])
        self.assertTrue(PendingCalendarEvent.objects.filter(pk=event.pk, status="pending").exists())


class CalendarQueueImportTest(CalendarViewsTestBase):
    def _make_event(self):
        # event_time is required: create_invoice_items_from_events skips events
        # with no combined start datetime ("start" ends up None otherwise).
        return PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="evt-1",
            summary="Termin",
            event_date=date(2026, 3, 5),
            event_time="10:00:00",
            duration_minutes=60,
            matched_client=self.test_client,
            suggested_service_type=self.service_type,
            status=PendingCalendarEvent.Status.PENDING,
        )

    def test_no_events_selected_returns_400(self):
        response = self.http.post(
            reverse("calendar_queue_import"),
            data=json.dumps({"event_ids": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_json_returns_400(self):
        response = self.http.post(
            reverse("calendar_queue_import"), data="not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_imports_events_and_marks_imported(self):
        event = self._make_event()
        response = self.http.post(
            reverse("calendar_queue_import"),
            data=json.dumps({"event_ids": [event.pk]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["created"], 1)
        event.refresh_from_db()
        self.assertEqual(event.status, PendingCalendarEvent.Status.IMPORTED)

    def test_imports_onto_specific_invoice_when_given(self):
        event = self._make_event()
        invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date(2026, 3, 1),
            status="draft",
            total=Decimal("0.00"),
            practice=self.practice,
        )
        response = self.http.post(
            reverse("calendar_queue_import"),
            data=json.dumps({"event_ids": [event.pk], "invoice_id": invoice.pk}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(invoice.items.count(), 1)


class CalendarQueueSkipDuplicatesTest(CalendarViewsTestBase):
    def test_skips_duplicate_pending_events(self):
        invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date(2026, 3, 5),
            total=Decimal("90.00"),
            practice=self.practice,
        )
        session = Session.objects.create(
            client=self.test_client, session_date=date(2026, 3, 5), duration=60
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
            total=Decimal("90.00"),
        )
        event = PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="evt-1",
            summary="Termin",
            event_date=date(2026, 3, 5),
            duration_minutes=60,
            matched_client=self.test_client,
            status=PendingCalendarEvent.Status.PENDING,
        )
        response = self.http.post(reverse("calendar_queue_skip_duplicates"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["skipped"], 1)
        event.refresh_from_db()
        self.assertEqual(event.status, PendingCalendarEvent.Status.SKIPPED)


class CalendarQueueSkipTest(CalendarViewsTestBase):
    def test_skips_single_event(self):
        event = PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="evt-1",
            summary="Termin",
            event_date=date.today(),
            duration_minutes=60,
            status=PendingCalendarEvent.Status.PENDING,
        )
        response = self.http.post(reverse("calendar_queue_skip", kwargs={"pk": event.pk}))
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.status, PendingCalendarEvent.Status.SKIPPED)

    def test_not_found_returns_404(self):
        response = self.http.post(reverse("calendar_queue_skip", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)


class CalendarEventQuickActionTest(CalendarViewsTestBase):
    def _make_event(self, **overrides):
        base = dict(
            practice=self.practice,
            google_event_id="evt-1",
            summary="Termin",
            event_date=date.today(),
            duration_minutes=60,
            matched_client=self.test_client,
            suggested_service_type=self.service_type,
            status=PendingCalendarEvent.Status.PENDING,
        )
        base.update(overrides)
        return PendingCalendarEvent.objects.create(**base)

    def test_event_not_found_redirects_to_client_list(self):
        response = self.http.post(
            reverse("calendar_event_quick_action", kwargs={"pk": 99999}),
            {"action": "ignore"},
        )
        self.assertRedirects(response, reverse("client_list"))

    def test_ignore_action_marks_skipped(self):
        event = self._make_event()
        response = self.http.post(
            reverse("calendar_event_quick_action", kwargs={"pk": event.pk}),
            {"action": "ignore"},
        )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": self.test_client.pk}))
        event.refresh_from_db()
        self.assertEqual(event.status, PendingCalendarEvent.Status.SKIPPED)

    def test_ignore_without_client_redirects_to_approval_queue(self):
        event = self._make_event(matched_client=None)
        response = self.http.post(
            reverse("calendar_event_quick_action", kwargs={"pk": event.pk}),
            {"action": "ignore"},
        )
        self.assertRedirects(response, reverse("calendar_approval_queue"))

    def test_unknown_action_shows_error(self):
        event = self._make_event()
        response = self.http.post(
            reverse("calendar_event_quick_action", kwargs={"pk": event.pk}),
            {"action": "not-a-real-action"},
            follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("Unbekannte Aktion" in str(m) for m in messages))

    def test_no_client_assigned_redirects_to_approval_queue(self):
        event = self._make_event(matched_client=None)
        response = self.http.post(
            reverse("calendar_event_quick_action", kwargs={"pk": event.pk}),
            {"action": "new_invoice"},
        )
        self.assertRedirects(response, reverse("calendar_approval_queue"))

    def test_no_service_type_shows_error(self):
        ServiceType.objects.filter(code="therapy_60").delete()
        event = self._make_event(suggested_service_type=None)
        response = self.http.post(
            reverse("calendar_event_quick_action", kwargs={"pk": event.pk}),
            {"action": "new_invoice"},
            follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("Kein passender Leistungstyp" in str(m) for m in messages))

    def test_falls_back_to_default_60min_service_type(self):
        event = self._make_event(suggested_service_type=None)
        response = self.http.post(
            reverse("calendar_event_quick_action", kwargs={"pk": event.pk}),
            {"action": "new_invoice"},
        )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": self.test_client.pk}))
        event.refresh_from_db()
        self.assertEqual(event.status, PendingCalendarEvent.Status.IMPORTED)

    def test_zero_rate_shows_error(self):
        self.test_client.hourly_rate_60 = Decimal("0.00")
        self.test_client.save()
        event = self._make_event()
        response = self.http.post(
            reverse("calendar_event_quick_action", kwargs={"pk": event.pk}),
            {"action": "new_invoice"},
            follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("Kein Stundensatz" in str(m) for m in messages))

    def test_already_billed_session_shows_warning(self):
        invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            total=Decimal("90.00"),
            practice=self.practice,
        )
        session = Session.objects.create(
            client=self.test_client, session_date=date.today(), duration=60
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
            total=Decimal("90.00"),
        )
        event = self._make_event()
        response = self.http.post(
            reverse("calendar_event_quick_action", kwargs={"pk": event.pk}),
            {"action": "new_invoice"},
            follow=True,
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("bereits abgerechnet" in str(m) for m in messages))

    def test_new_invoice_action_creates_invoice_and_item(self):
        event = self._make_event()
        response = self.http.post(
            reverse("calendar_event_quick_action", kwargs={"pk": event.pk}),
            {"action": "new_invoice"},
        )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": self.test_client.pk}))
        invoice = Invoice.objects.get(client=self.test_client)
        self.assertEqual(invoice.items.count(), 1)
        event.refresh_from_db()
        self.assertEqual(event.status, PendingCalendarEvent.Status.IMPORTED)
        self.assertIsNotNone(event.session)

    def test_current_invoice_action_reuses_existing_draft(self):
        existing = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today().replace(day=1),
            status="draft",
            total=Decimal("0.00"),
            practice=self.practice,
        )
        event = self._make_event()
        response = self.http.post(
            reverse("calendar_event_quick_action", kwargs={"pk": event.pk}),
            {"action": "current_invoice"},
        )
        self.assertRedirects(response, reverse("client_detail", kwargs={"pk": self.test_client.pk}))
        existing.refresh_from_db()
        self.assertEqual(existing.items.count(), 1)

    def test_creation_exception_shows_import_error(self):
        event = self._make_event()
        with patch(
            "my_practice.utils.calendar_import_helpers.get_or_create_invoice_for_month",
            side_effect=RuntimeError("db down"),
        ):
            response = self.http.post(
                reverse("calendar_event_quick_action", kwargs={"pk": event.pk}),
                {"action": "current_invoice"},
                follow=True,
            )
        messages = list(response.context["messages"])
        self.assertTrue(any("Fehler beim Import" in str(m) for m in messages))
