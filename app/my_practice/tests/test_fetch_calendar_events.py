"""
Tests for the fetch_calendar_events management command (P-013): the
Command.handle() -> _fetch_for_practice() -> _upsert_event() pipeline that
syncs Google Calendar events into the pending approval queue.
"""

from datetime import date, timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ..management.commands.fetch_calendar_events import Command, FIRST_RUN_DAYS, OVERLAP_HOURS
from ..models import (
    Client,
    GoogleCalendarToken,
    PendingCalendarEvent,
    Practice,
    ServiceType,
    Session,
)


def _make_command() -> Command:
    cmd = Command()
    cmd.stdout = StringIO()
    style = MagicMock()
    style.SUCCESS = lambda x: x
    style.WARNING = lambda x: x
    style.ERROR = lambda x: x
    cmd.style = style
    return cmd


class UpsertEventTestBase(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="upsert-event-test",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.test_client = Client.objects.create(
            practice=self.practice,
            client_code="TC",
            full_name="Max Mustermann",
        )
        self.cmd = _make_command()

    def _event(self, **overrides):
        base = {
            "id": "evt-1",
            "start": date(2026, 3, 1),
            "summary": "TC 60min",
            "duration_minutes": 60,
            "matched_client": self.test_client,
            "suggested_service_type_obj": None,
            "is_cancelled": False,
        }
        base.update(overrides)
        return base


class UpsertEventInvalidAndDryRunTest(UpsertEventTestBase):
    def test_no_id_returns_none(self):
        result = self.cmd._upsert_event(self._event(id=None), self.practice, dry_run=False)
        self.assertIsNone(result)

    def test_no_start_returns_none(self):
        result = self.cmd._upsert_event(self._event(start=None), self.practice, dry_run=False)
        self.assertIsNone(result)

    def test_dry_run_reports_created_without_writing(self):
        result = self.cmd._upsert_event(self._event(), self.practice, dry_run=True)
        self.assertEqual(result, "created")
        self.assertFalse(PendingCalendarEvent.objects.exists())


class UpsertEventCreateTest(UpsertEventTestBase):
    def test_creates_new_event_and_session(self):
        affected: set = set()
        result = self.cmd._upsert_event(
            self._event(), self.practice, dry_run=False, affected_clients=affected
        )
        self.assertEqual(result, "created")
        pce = PendingCalendarEvent.objects.get(google_event_id="evt-1")
        self.assertEqual(pce.status, PendingCalendarEvent.Status.PENDING)
        self.assertIsNotNone(pce.session)
        self.assertIn(self.test_client, affected)

    def test_cancelled_new_event_creates_cancelled_pce_no_session(self):
        result = self.cmd._upsert_event(
            self._event(is_cancelled=True), self.practice, dry_run=False
        )
        self.assertEqual(result, "created")
        pce = PendingCalendarEvent.objects.get(google_event_id="evt-1")
        self.assertEqual(pce.status, PendingCalendarEvent.Status.CANCELLED)
        self.assertIsNone(pce.session)

    def test_therapy_free_event_creates_skipped_pce_with_session(self):
        free_type = ServiceType.objects.create(
            code="therapy_free", name="Free consult", default_duration=30
        )
        result = self.cmd._upsert_event(
            self._event(suggested_service_type_obj=free_type), self.practice, dry_run=False
        )
        self.assertEqual(result, "created")
        pce = PendingCalendarEvent.objects.get(google_event_id="evt-1")
        self.assertEqual(pce.status, PendingCalendarEvent.Status.SKIPPED)
        self.assertIsNotNone(pce.session)

    def test_unmatched_client_creates_no_session(self):
        result = self.cmd._upsert_event(
            self._event(matched_client=None), self.practice, dry_run=False
        )
        self.assertEqual(result, "created")
        pce = PendingCalendarEvent.objects.get(google_event_id="evt-1")
        self.assertIsNone(pce.session)


class UpsertEventNoChangeTest(UpsertEventTestBase):
    def test_unchanged_event_is_skipped(self):
        self.cmd._upsert_event(self._event(), self.practice, dry_run=False)
        result = self.cmd._upsert_event(self._event(), self.practice, dry_run=False)
        self.assertEqual(result, "skipped")


class UpsertEventRescheduleTest(UpsertEventTestBase):
    def setUp(self):
        super().setUp()
        self.cmd._upsert_event(self._event(), self.practice, dry_run=False)
        self.pce = PendingCalendarEvent.objects.get(google_event_id="evt-1")
        self.session = self.pce.session

    def test_date_change_reschedules_and_propagates_to_session(self):
        new_date = date(2026, 3, 5)
        affected: set = set()
        result = self.cmd._upsert_event(
            self._event(start=new_date), self.practice, dry_run=False, affected_clients=affected
        )
        self.assertEqual(result, "rescheduled")
        self.pce.refresh_from_db()
        self.session.refresh_from_db()
        self.assertEqual(self.pce.event_date, new_date)
        self.assertEqual(self.session.session_date, new_date)
        self.assertIn(self.test_client, affected)

    def test_duration_change_reschedules_and_propagates_to_session(self):
        result = self.cmd._upsert_event(
            self._event(duration_minutes=90), self.practice, dry_run=False
        )
        self.assertEqual(result, "rescheduled")
        self.pce.refresh_from_db()
        self.session.refresh_from_db()
        self.assertEqual(self.pce.duration_minutes, 90)
        self.assertEqual(self.session.duration, 90)

    def test_reschedule_of_imported_event_without_session_resets_to_pending(self):
        self.pce.status = PendingCalendarEvent.Status.IMPORTED
        self.pce.session = None
        self.pce.save()

        self.cmd._upsert_event(self._event(start=date(2026, 3, 9)), self.practice, dry_run=False)

        self.pce.refresh_from_db()
        self.assertEqual(self.pce.status, PendingCalendarEvent.Status.PENDING)

    def test_reschedule_of_imported_event_with_session_keeps_status(self):
        self.pce.status = PendingCalendarEvent.Status.IMPORTED
        self.pce.save()

        self.cmd._upsert_event(self._event(start=date(2026, 3, 9)), self.practice, dry_run=False)

        self.pce.refresh_from_db()
        self.assertEqual(self.pce.status, PendingCalendarEvent.Status.IMPORTED)


class UpsertEventReinstateTest(UpsertEventTestBase):
    def setUp(self):
        super().setUp()
        self.cmd._upsert_event(self._event(), self.practice, dry_run=False)
        self.pce = PendingCalendarEvent.objects.get(google_event_id="evt-1")
        self.session = self.pce.session
        PendingCalendarEvent.objects.filter(pk=self.pce.pk).update(
            status=PendingCalendarEvent.Status.CANCELLED,
            missing_since=timezone.now(),
        )
        Session.objects.filter(pk=self.session.pk).update(cancelled=True)

    def test_reinstate_refreshes_date_and_clears_missing_since(self):
        """A cancelled event that comes back live must pick up its current
        date/time/duration immediately — not just flip status — otherwise the
        next run sees a stale date and reports a spurious 'rescheduled'."""
        new_date = date(2026, 3, 5)
        result = self.cmd._upsert_event(self._event(start=new_date), self.practice, dry_run=False)
        self.assertEqual(result, "reinstated")
        self.pce.refresh_from_db()
        self.session.refresh_from_db()
        self.assertEqual(self.pce.status, PendingCalendarEvent.Status.PENDING)
        self.assertEqual(self.pce.event_date, new_date)
        self.assertIsNone(self.pce.missing_since)
        self.assertFalse(self.session.cancelled)
        self.assertEqual(self.session.session_date, new_date)

    def test_reinstate_then_refetch_same_event_is_skipped_not_rescheduled(self):
        """Regression test: fetching the same live event twice in a row after
        a reinstate must not report a second 'rescheduled' change."""
        new_date = date(2026, 3, 5)
        self.cmd._upsert_event(self._event(start=new_date), self.practice, dry_run=False)
        result = self.cmd._upsert_event(self._event(start=new_date), self.practice, dry_run=False)
        self.assertEqual(result, "skipped")


class ResolveEventStatusTest(TestCase):
    def test_cancelled_event(self):
        status = Command._resolve_event_status({"is_cancelled": True})
        self.assertEqual(status, PendingCalendarEvent.Status.CANCELLED)

    def test_therapy_free_event(self):
        stype = ServiceType(code="therapy_free")
        status = Command._resolve_event_status(
            {"is_cancelled": False, "suggested_service_type_obj": stype}
        )
        self.assertEqual(status, PendingCalendarEvent.Status.SKIPPED)

    def test_normal_event(self):
        status = Command._resolve_event_status({"is_cancelled": False})
        self.assertEqual(status, PendingCalendarEvent.Status.PENDING)


class AutoCreateSessionTest(UpsertEventTestBase):
    def test_no_matched_client_returns_none(self):
        result = self.cmd._auto_create_session(
            self._event(matched_client=None),
            "evt-1",
            date(2026, 3, 1),
            None,
            PendingCalendarEvent.Status.PENDING,
        )
        self.assertIsNone(result)

    def test_cancelled_status_returns_none_without_session(self):
        result = self.cmd._auto_create_session(
            self._event(),
            "evt-1",
            date(2026, 3, 1),
            None,
            PendingCalendarEvent.Status.CANCELLED,
        )
        self.assertIsNone(result)
        self.assertFalse(Session.objects.exists())

    def test_pending_status_creates_session(self):
        PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="evt-1",
            summary="TC 60min",
            event_date=date(2026, 3, 1),
            duration_minutes=60,
            status=PendingCalendarEvent.Status.PENDING,
        )
        result = self.cmd._auto_create_session(
            self._event(),
            "evt-1",
            date(2026, 3, 1),
            None,
            PendingCalendarEvent.Status.PENDING,
        )
        self.assertEqual(result, self.test_client)
        session = Session.objects.get(client=self.test_client)
        self.assertEqual(session.duration, 60)


class DetermineFetchWindowTest(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="fetch-window-test",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.cmd = _make_command()

    def test_forced_days_overrides_everything(self):
        start, end = self.cmd._determine_fetch_window(self.practice, forced_days=7, future_days=1)
        now = timezone.now()
        self.assertAlmostEqual((now - start).total_seconds(), 7 * 86400, delta=60)

    def test_first_run_uses_first_run_days(self):
        start, _end = self.cmd._determine_fetch_window(
            self.practice, forced_days=None, future_days=1
        )
        now = timezone.now()
        self.assertAlmostEqual((now - start).total_seconds(), FIRST_RUN_DAYS * 86400, delta=60)

    def test_subsequent_run_uses_overlap_from_last_fetch(self):
        PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="evt-1",
            summary="Termin",
            event_date=date.today(),
            duration_minutes=60,
        )
        start, _end = self.cmd._determine_fetch_window(
            self.practice, forced_days=None, future_days=1
        )
        last_fetch = PendingCalendarEvent.objects.first().fetched_at
        expected_start = last_fetch - timedelta(hours=OVERLAP_HOURS)
        self.assertAlmostEqual((start - expected_start).total_seconds(), 0, delta=2)


class FetchRawEventsTest(TestCase):
    def test_paginates_until_no_next_page_token(self):
        cmd = _make_command()
        service = MagicMock()
        service.events.return_value.list.return_value.execute.side_effect = [
            {"items": [{"id": "e1"}], "nextPageToken": "tok"},
            {"items": [{"id": "e2"}]},
        ]
        events = cmd._fetch_raw_events(
            service, "cal-1", timezone.now(), timezone.now() + timedelta(days=1)
        )
        self.assertEqual([e["id"] for e in events], ["e1", "e2"])


class CancelStaleFutureEventsTest(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="cancel-stale-test",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.test_client = Client.objects.create(
            practice=self.practice, client_code="TC", full_name="Max Mustermann"
        )
        self.cmd = _make_command()
        self.future_date = date.today() + timedelta(days=5)

    def test_first_miss_flags_but_does_not_cancel(self):
        """A single missing fetch only starts the debounce clock — Google's API
        can transiently omit a just-edited event, so we don't cancel yet."""
        session = Session.objects.create(
            client=self.test_client, session_date=self.future_date, duration=60
        )
        pce = PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="gone-event",
            summary="Termin",
            event_date=self.future_date,
            duration_minutes=60,
            matched_client=self.test_client,
            status=PendingCalendarEvent.Status.PENDING,
            session=session,
        )
        cancelled, flagged = self.cmd._cancel_stale_future_events(
            self.practice,
            timezone.now(),
            timezone.now() + timedelta(days=10),
            live_ids=set(),
            dry_run=False,
        )
        self.assertEqual(cancelled, 0)
        self.assertEqual(flagged, 1)
        pce.refresh_from_db()
        self.assertIsNotNone(pce.missing_since)
        self.assertEqual(pce.status, PendingCalendarEvent.Status.PENDING)
        session.refresh_from_db()
        self.assertFalse(session.cancelled)

    def test_second_consecutive_miss_cancels(self):
        session = Session.objects.create(
            client=self.test_client, session_date=self.future_date, duration=60
        )
        PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="gone-event",
            summary="Termin",
            event_date=self.future_date,
            duration_minutes=60,
            matched_client=self.test_client,
            status=PendingCalendarEvent.Status.PENDING,
            session=session,
            missing_since=timezone.now() - timedelta(hours=6),
        )
        cancelled, flagged = self.cmd._cancel_stale_future_events(
            self.practice,
            timezone.now(),
            timezone.now() + timedelta(days=10),
            live_ids=set(),
            dry_run=False,
        )
        self.assertEqual(cancelled, 1)
        self.assertEqual(flagged, 0)
        session.refresh_from_db()
        self.assertTrue(session.cancelled)

    def test_reappearing_event_clears_missing_since(self):
        pce = PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="still-here",
            summary="Termin",
            event_date=self.future_date,
            duration_minutes=60,
            status=PendingCalendarEvent.Status.PENDING,
            missing_since=timezone.now() - timedelta(hours=6),
        )
        cancelled, flagged = self.cmd._cancel_stale_future_events(
            self.practice,
            timezone.now(),
            timezone.now() + timedelta(days=10),
            live_ids={"still-here"},
            dry_run=False,
        )
        self.assertEqual(cancelled, 0)
        self.assertEqual(flagged, 0)
        pce.refresh_from_db()
        self.assertIsNone(pce.missing_since)

    def test_event_present_in_live_ids_is_not_cancelled(self):
        PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="still-here",
            summary="Termin",
            event_date=self.future_date,
            duration_minutes=60,
            status=PendingCalendarEvent.Status.PENDING,
        )
        cancelled, flagged = self.cmd._cancel_stale_future_events(
            self.practice,
            timezone.now(),
            timezone.now() + timedelta(days=10),
            live_ids={"still-here"},
            dry_run=False,
        )
        self.assertEqual(cancelled, 0)
        self.assertEqual(flagged, 0)

    def test_dry_run_first_miss_flags_without_writing(self):
        PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="gone-event",
            summary="Termin",
            event_date=self.future_date,
            duration_minutes=60,
            status=PendingCalendarEvent.Status.PENDING,
        )
        cancelled, flagged = self.cmd._cancel_stale_future_events(
            self.practice,
            timezone.now(),
            timezone.now() + timedelta(days=10),
            live_ids=set(),
            dry_run=True,
        )
        self.assertEqual(cancelled, 0)
        self.assertEqual(flagged, 1)
        pce = PendingCalendarEvent.objects.get(google_event_id="gone-event")
        self.assertEqual(pce.status, PendingCalendarEvent.Status.PENDING)
        self.assertIsNone(pce.missing_since)

    def test_dry_run_second_miss_counts_cancel_without_writing(self):
        PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="gone-event",
            summary="Termin",
            event_date=self.future_date,
            duration_minutes=60,
            status=PendingCalendarEvent.Status.PENDING,
            missing_since=timezone.now() - timedelta(hours=6),
        )
        cancelled, flagged = self.cmd._cancel_stale_future_events(
            self.practice,
            timezone.now(),
            timezone.now() + timedelta(days=10),
            live_ids=set(),
            dry_run=True,
        )
        self.assertEqual(cancelled, 1)
        self.assertEqual(flagged, 0)
        pce = PendingCalendarEvent.objects.get(google_event_id="gone-event")
        self.assertEqual(pce.status, PendingCalendarEvent.Status.PENDING)


class HandleAndFetchForPracticeTest(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="handle-test",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

    def test_no_active_tokens_warns(self):
        out = StringIO()
        call_command("fetch_calendar_events", stdout=out)
        self.assertIn("No active calendar tokens found", out.getvalue())

    def test_token_without_practice_shows_error(self):
        GoogleCalendarToken.objects.create(
            practice=None,
            token="tok",
            refresh_token="refresh",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client",
            client_secret="test-secret",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            is_active=True,
        )
        out = StringIO()
        call_command("fetch_calendar_events", stdout=out)
        self.assertIn("no associated practice", out.getvalue())

    def test_practice_id_filters_tokens(self):
        other_practice = Practice.objects.create(
            name="Other",
            slug="handle-test-other",
            title="Other",
            email="other@practice.com",
            city="Hamburg",
        )
        GoogleCalendarToken.objects.create(
            practice=other_practice,
            token="tok",
            refresh_token="refresh",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client",
            client_secret="test-secret",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            is_active=True,
        )
        out = StringIO()
        call_command("fetch_calendar_events", "--practice-id", self.practice.pk, stdout=out)
        self.assertIn("No active calendar tokens found", out.getvalue())

    def test_fetch_for_practice_no_service_shows_error(self):
        GoogleCalendarToken.objects.create(
            practice=self.practice,
            token="tok",
            refresh_token="refresh",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client",
            client_secret="test-secret",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            is_active=True,
        )
        with patch(
            "my_practice.management.commands.fetch_calendar_events.GoogleCalendarOAuth.get_service",
            return_value=None,
        ):
            out = StringIO()
            call_command("fetch_calendar_events", stdout=out)
        self.assertIn("expired or invalid", out.getvalue())

    def test_fetch_for_practice_no_praxis_calendar_warns(self):
        GoogleCalendarToken.objects.create(
            practice=self.practice,
            token="tok",
            refresh_token="refresh",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client",
            client_secret="test-secret",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            is_active=True,
        )
        service = MagicMock()
        with (
            patch(
                "my_practice.management.commands.fetch_calendar_events.GoogleCalendarOAuth.get_service",
                return_value=service,
            ),
            patch(
                "my_practice.management.commands.fetch_calendar_events.find_calendar_by_name",
                return_value=None,
            ),
        ):
            out = StringIO()
            call_command("fetch_calendar_events", stdout=out)
        self.assertIn("not found", out.getvalue())

    def test_fetch_for_practice_api_error_is_reported(self):
        GoogleCalendarToken.objects.create(
            practice=self.practice,
            token="tok",
            refresh_token="refresh",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client",
            client_secret="test-secret",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            is_active=True,
        )
        service = MagicMock()
        with (
            patch(
                "my_practice.management.commands.fetch_calendar_events.GoogleCalendarOAuth.get_service",
                return_value=service,
            ),
            patch(
                "my_practice.management.commands.fetch_calendar_events.find_calendar_by_name",
                return_value="cal-1",
            ),
            patch(
                "my_practice.management.commands.fetch_calendar_events.Command._fetch_raw_events",
                side_effect=RuntimeError("api down"),
            ),
        ):
            out = StringIO()
            call_command("fetch_calendar_events", stdout=out)
        self.assertIn("API-Fehler", out.getvalue())

    def test_fetch_for_practice_creates_events_end_to_end(self):
        test_client = Client.objects.create(
            practice=self.practice, client_code="TC", full_name="Max Mustermann"
        )
        GoogleCalendarToken.objects.create(
            practice=self.practice,
            token="tok",
            refresh_token="refresh",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client",
            client_secret="test-secret",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            is_active=True,
        )
        service = MagicMock()
        raw_event = {
            "id": "evt-1",
            "summary": f"{test_client.client_code} Sitzung",
            "start": {"dateTime": "2026-03-01T10:00:00+01:00"},
            "end": {"dateTime": "2026-03-01T11:00:00+01:00"},
        }
        service.events.return_value.list.return_value.execute.return_value = {"items": [raw_event]}
        with (
            patch(
                "my_practice.management.commands.fetch_calendar_events.GoogleCalendarOAuth.get_service",
                return_value=service,
            ),
            patch(
                "my_practice.management.commands.fetch_calendar_events.find_calendar_by_name",
                return_value="cal-1",
            ),
        ):
            out = StringIO()
            call_command("fetch_calendar_events", stdout=out)
        self.assertIn("1 new", out.getvalue())
        self.assertTrue(PendingCalendarEvent.objects.filter(google_event_id="evt-1").exists())

    def test_dry_run_reports_would_create(self):
        test_client = Client.objects.create(
            practice=self.practice, client_code="TC", full_name="Max Mustermann"
        )
        GoogleCalendarToken.objects.create(
            practice=self.practice,
            token="tok",
            refresh_token="refresh",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client",
            client_secret="test-secret",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            is_active=True,
        )
        service = MagicMock()
        raw_event = {
            "id": "evt-1",
            "summary": f"{test_client.client_code} Sitzung",
            "start": {"dateTime": "2026-03-01T10:00:00+01:00"},
            "end": {"dateTime": "2026-03-01T11:00:00+01:00"},
        }
        service.events.return_value.list.return_value.execute.return_value = {"items": [raw_event]}
        with (
            patch(
                "my_practice.management.commands.fetch_calendar_events.GoogleCalendarOAuth.get_service",
                return_value=service,
            ),
            patch(
                "my_practice.management.commands.fetch_calendar_events.find_calendar_by_name",
                return_value="cal-1",
            ),
        ):
            out = StringIO()
            call_command("fetch_calendar_events", "--dry-run", stdout=out)
        self.assertIn("[dry-run] Would create", out.getvalue())
        self.assertFalse(PendingCalendarEvent.objects.exists())
