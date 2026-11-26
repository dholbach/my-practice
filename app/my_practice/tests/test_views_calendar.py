"""
Tests for Google Calendar integration views (P-013): OAuth flow, manual
import, the approval queue, and the client-detail quick-action endpoint.
"""

import json
from datetime import date, time
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import (
    Client,
    GoogleCalendarToken,
    Invoice,
    InvoiceItem,
    PendingCalendarEvent,
    ServiceType,
    Session,
)
from ..utils.google_calendar import CalendarUnreachable
from ..views import calendar_views
from .test_helpers import create_test_practice, create_test_user


class CalendarViewsTestBase(TestCase):
    def setUp(self):
        self.practice = create_test_practice(name="Test Practice", slug="calendar-views-test")
        self.user = create_test_user(self.practice, username="caluser", password="testpass123")
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

    def _create_calendar_token(self, calendar_id="cal-1"):
        return GoogleCalendarToken.objects.create(
            practice=self.practice,
            token="tok",
            refresh_token="refresh",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client",
            client_secret="test-secret",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            calendar_id=calendar_id,
            is_active=True,
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
            response = self.http.post(reverse("calendar_authorize"))
        self.assertRedirects(
            response, "https://accounts.google.com/auth", fetch_redirect_response=False
        )
        session = self.http.session
        self.assertEqual(session["oauth_state"], "state123")

    def test_get_is_refused_without_touching_oauth_state(self):
        response = self.http.get(reverse("calendar_authorize"))
        self.assertEqual(response.status_code, 405)
        self.assertNotIn("oauth_state", self.http.session)


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
        self.assertFalse(any("boom" in str(m) for m in messages))


class CalendarImportViewTest(CalendarViewsTestBase):
    def test_no_service_redirects_to_connect_page(self):
        with patch(
            "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service", return_value=None
        ):
            response = self.http.get(reverse("calendar_import"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/calendar_connect.html")

    def test_unreachable_google_does_not_offer_reconnecting(self):
        """#756: Google out of reach is an error message, not the connect page."""
        with patch(
            "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service",
            side_effect=CalendarUnreachable("Connection refused"),
        ):
            response = self.http.get(reverse("calendar_import"), follow=True)
        self.assertTemplateNotUsed(response, "my_practice/calendar_connect.html")
        messages = [str(m) for m in response.context["messages"]]
        self.assertTrue(any("nicht erreicht" in m for m in messages), messages)

    def test_no_calendar_selected_shows_picker(self):
        service = MagicMock()
        service.calendarList().list().execute.return_value = {
            "items": [{"id": "cal-1", "summary": "Praxis"}]
        }
        with patch(
            "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service",
            return_value=service,
        ):
            response = self.http.get(reverse("calendar_import"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/calendar_select.html")
        self.assertEqual(
            response.context["calendars"],
            [{"id": "cal-1", "name": "Praxis", "primary": False}],
        )

    def test_selecting_a_calendar_saves_it_on_the_token(self):
        token = self._create_calendar_token(calendar_id="")
        service = MagicMock()
        # follow=True re-enters calendar_import as a GET, which — now that the
        # calendar_id is set — proceeds to the real event-fetch/pagination path.
        # An unconfigured MagicMock's .get("nextPageToken") is always truthy,
        # so without this the pagination loop in
        # fetch_all_events never terminates.
        service.events.return_value.list.return_value.execute.return_value = {"items": []}
        with patch(
            "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service",
            return_value=service,
        ):
            response = self.http.post(
                reverse("calendar_import"), {"calendar_id": "cal-2"}, follow=True
            )
        self.assertRedirects(response, reverse("calendar_import"))
        token.refresh_from_db()
        self.assertEqual(token.calendar_id, "cal-2")

    def test_loads_and_categorizes_events(self):
        self._create_calendar_token(calendar_id="cal-1")
        service = MagicMock()
        raw_event = {
            "id": "evt-1",
            "summary": f"{self.test_client.client_code} Sitzung",
            "start": {"dateTime": "2026-03-01T10:00:00+01:00"},
            "end": {"dateTime": "2026-03-01T11:00:00+01:00"},
        }
        service.events.return_value.list.return_value.execute.return_value = {"items": [raw_event]}
        with patch(
            "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service",
            return_value=service,
        ):
            response = self.http.get(reverse("calendar_import"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_events"], 1)
        self.assertEqual(response.context["ready_count"], 1)
        self.assertIn("cached_events", self.http.session)

    def test_exception_during_fetch_redirects_to_dashboard(self):
        self._create_calendar_token(calendar_id="cal-1")
        service = MagicMock()
        service.events.return_value.list.return_value.execute.side_effect = RuntimeError("api down")
        with patch(
            "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service",
            return_value=service,
        ):
            response = self.http.get(reverse("calendar_import"), follow=True)
        self.assertRedirects(response, reverse("dashboard"))
        messages = list(response.context["messages"])
        self.assertTrue(any("Fehler beim Laden der Kalender-Einträge" in str(m) for m in messages))
        self.assertFalse(any("api down" in str(m) for m in messages))


class CalendarImportEventsViewTest(CalendarViewsTestBase):
    def test_unreachable_google_returns_503(self):
        with patch(
            "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service",
            side_effect=CalendarUnreachable("Connection refused"),
        ):
            response = self.http.post(
                reverse("calendar_import_events"),
                data=json.dumps({"events": [{"id": "evt-1", "action": "import"}]}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["success"])

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
        with patch(
            "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service",
            return_value=service,
        ):
            response = self.http.post(
                reverse("calendar_import_events"),
                data=json.dumps({"events": [{"id": "evt-1", "action": "import"}]}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 404)

    def test_fetch_specific_events_failure_returns_500(self):
        self._create_calendar_token(calendar_id="cal-1")
        service = MagicMock()
        with (
            patch(
                "my_practice.views.calendar_views.GoogleCalendarOAuth.get_service",
                return_value=service,
            ),
            patch(
                "my_practice.utils.calendar_event_processor.CalendarImportProcessor."
                "fetch_specific_events",
                side_effect=RuntimeError("secret-internal-detail"),
            ),
        ):
            response = self.http.post(
                reverse("calendar_import_events"),
                data=json.dumps({"events": [{"id": "evt-1", "action": "import"}]}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret-internal-detail", response.content.decode())


class CalendarApprovalQueueTest(CalendarViewsTestBase):
    def _make_event(self, event_date, **overrides):
        base = {
            "practice": self.practice,
            "google_event_id": f"evt-{event_date}",
            "summary": "Termin",
            "event_date": event_date,
            "duration_minutes": 60,
            "matched_client": self.test_client,
            "suggested_service_type": self.service_type,
            "status": PendingCalendarEvent.Status.PENDING,
        }
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

    def test_failed_events_stay_pending(self):
        """Only events that produced an invoice item are marked imported."""
        good = self._make_event()
        unmatched = PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="evt-2",
            summary="Termin ohne Zuordnung",
            event_date=date(2026, 3, 6),
            event_time="10:00:00",
            duration_minutes=60,
            matched_client=None,
            status=PendingCalendarEvent.Status.PENDING,
        )
        response = self.http.post(
            reverse("calendar_queue_import"),
            data=json.dumps({"event_ids": [good.pk, unmatched.pk]}),
            content_type="application/json",
        )
        body = response.json()
        self.assertEqual(body["created"], 1)
        self.assertEqual(body["imported_ids"], [good.pk])
        self.assertEqual(len(body["errors"]), 1)
        good.refresh_from_db()
        unmatched.refresh_from_db()
        self.assertEqual(good.status, PendingCalendarEvent.Status.IMPORTED)
        self.assertEqual(unmatched.status, PendingCalendarEvent.Status.PENDING)

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

    def test_new_invoice_is_created_once_per_batch(self):
        """ "Create new invoice" puts the whole batch on one invoice, not one per event."""
        first = self._make_event()
        second = PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="evt-2",
            summary="Termin",
            event_date=date(2026, 3, 12),
            event_time="10:00:00",
            duration_minutes=60,
            matched_client=self.test_client,
            suggested_service_type=self.service_type,
            status=PendingCalendarEvent.Status.PENDING,
        )
        response = self.http.post(
            reverse("calendar_queue_import"),
            data=json.dumps({"event_ids": [first.pk, second.pk], "invoice_id": "new"}),
            content_type="application/json",
        )
        self.assertEqual(response.json()["created"], 2)
        invoices = Invoice.objects.filter(client=self.test_client)
        self.assertEqual(invoices.count(), 1)
        self.assertEqual(invoices.get().items.count(), 2)


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
        base = {
            "practice": self.practice,
            "google_event_id": "evt-1",
            "summary": "Termin",
            "event_date": date.today(),
            "duration_minutes": 60,
            "matched_client": self.test_client,
            "suggested_service_type": self.service_type,
            "status": PendingCalendarEvent.Status.PENDING,
        }
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

    def _bill_session(self, session, service_type):
        invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            practice=self.practice,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=service_type,
            session=session,
            rate=Decimal("90.00"),
        )

    def _other_service_type(self):
        return ServiceType.objects.create(
            code="therapy_90",
            name="Therapy 90",
            name_de="Therapie 90",
            name_en="Therapy 90",
            default_duration=90,
            practice=self.practice,
        )

    def _quick_import(self, event):
        return self.http.post(
            reverse("calendar_event_quick_action", kwargs={"pk": event.pk}),
            {"action": "new_invoice"},
            follow=True,
        )

    def test_linked_session_billed_under_other_type_is_not_billed_again(self):
        """#751: the old check matched on service type only, so a session
        billed as 90 min was billed a second time as 60 min."""
        session = Session.objects.create(
            client=self.test_client, session_date=date.today(), session_time=time(10, 0)
        )
        self._bill_session(session, self._other_service_type())
        event = self._make_event(event_time=time(10, 0), session=session)

        response = self._quick_import(event)

        messages = list(response.context["messages"])
        self.assertTrue(any("bereits abgerechnet" in str(m) for m in messages))
        self.assertEqual(InvoiceItem.objects.filter(session=session).count(), 1)
        self.assertEqual(Invoice.objects.filter(client=self.test_client).count(), 1)
        event.refresh_from_db()
        self.assertEqual(event.status, PendingCalendarEvent.Status.IMPORTED)

    def test_slot_billed_under_other_type_is_not_billed_again(self):
        """Same, for an event the fetch never linked to its session."""
        session = Session.objects.create(
            client=self.test_client, session_date=date.today(), session_time=time(10, 0)
        )
        self._bill_session(session, self._other_service_type())
        event = self._make_event(event_time=time(10, 0))

        self._quick_import(event)

        self.assertEqual(InvoiceItem.objects.count(), 1)

    def test_other_slot_same_day_other_type_is_billed(self):
        """A second session that day, at another time and of another type,
        is a real session and still gets billed."""
        morning = Session.objects.create(
            client=self.test_client, session_date=date.today(), session_time=time(9, 0)
        )
        self._bill_session(morning, self._other_service_type())
        event = self._make_event(event_time=time(16, 0))

        self._quick_import(event)

        self.assertEqual(InvoiceItem.objects.count(), 2)
        event.refresh_from_db()
        self.assertEqual(event.status, PendingCalendarEvent.Status.IMPORTED)

    def test_billed_between_check_and_lock_leaves_no_new_invoice(self):
        """The check inside the transaction refuses, and the new invoice it
        would have used is never created."""
        event = self._make_event(event_time=time(10, 0))
        calls = []

        def billed_once_locked(*args, **kwargs):
            # Unbilled at the first check, billed by someone else by the time
            # the slot is locked.
            calls.append(kwargs.get("lock", False))
            return kwargs.get("lock", False)

        with patch.object(calendar_views, "_event_already_billed", billed_once_locked):
            response = self._quick_import(event)

        self.assertEqual(calls, [False, True])
        messages = list(response.context["messages"])
        self.assertTrue(any("bereits abgerechnet" in str(m) for m in messages))
        self.assertFalse(Invoice.objects.filter(client=self.test_client).exists())
        self.assertFalse(InvoiceItem.objects.exists())
        event.refresh_from_db()
        self.assertEqual(event.status, PendingCalendarEvent.Status.IMPORTED)

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
        self.assertFalse(any("db down" in str(m) for m in messages))
