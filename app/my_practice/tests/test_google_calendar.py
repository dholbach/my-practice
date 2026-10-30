"""
Tests for Google Calendar utilities.
"""

from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from io import StringIO
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from my_practice.models import (
    Client,
    GoogleCalendarToken,
    PendingCalendarEvent,
    Practice,
    ServiceType,
    Session,
)
from my_practice.utils.calendar_import_helpers import _resolve_client
from my_practice.utils.google_calendar import (
    CalendarEventParser,
    GoogleCalendarOAuth,
    list_calendars,
    practice_clients,
)


class GoogleCalendarOAuthTest(TestCase):
    """Test OAuth2 authentication utilities."""

    def setUp(self):
        """Create test practice"""
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="google-calendar",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

    @patch("my_practice.utils.google_calendar.settings")
    def test_create_flow(self, mock_settings):
        """Test OAuth2 flow creation."""
        mock_settings.GOOGLE_CALENDAR_CLIENT_ID = "test-client-id"
        mock_settings.GOOGLE_CALENDAR_CLIENT_SECRET = "test-secret"

        flow = GoogleCalendarOAuth.create_flow("http://localhost/callback")

        self.assertEqual(flow.redirect_uri, "http://localhost/callback")
        # Flow stores scopes differently, check via client_config
        self.assertIsNotNone(flow)

    def test_save_token(self):
        """Test saving OAuth2 credentials to database."""
        # Create mock credentials
        mock_creds = Mock()
        mock_creds.token = "test-token"
        mock_creds.refresh_token = "test-refresh-token"
        mock_creds.token_uri = "https://oauth2.googleapis.com/token"
        mock_creds.client_id = "test-client-id"
        mock_creds.client_secret = "test-secret"
        mock_creds.scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
        mock_creds.expiry = timezone.now()

        # Save token
        token = GoogleCalendarOAuth.save_token(mock_creds)

        # Verify token saved
        self.assertIsNotNone(token)
        self.assertEqual(token.token, "test-token")
        self.assertEqual(token.refresh_token, "test-refresh-token")
        self.assertTrue(token.is_active)

    def test_save_token_deactivates_old_tokens(self):
        """Test that saving new token deactivates old ones."""
        # Create old token
        old_token = GoogleCalendarToken.objects.create(
            token="old-token",
            refresh_token="old-refresh",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="old-client",
            client_secret="old-secret",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            is_active=True,
            practice=self.practice,
        )

        # Create new credentials
        mock_creds = Mock()
        mock_creds.token = "new-token"
        mock_creds.refresh_token = "new-refresh"
        mock_creds.token_uri = "https://oauth2.googleapis.com/token"
        mock_creds.client_id = "new-client"
        mock_creds.client_secret = "new-secret"
        mock_creds.scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
        mock_creds.expiry = None

        # Save new token
        GoogleCalendarOAuth.save_token(mock_creds, practice=self.practice)

        # Verify old token deactivated
        old_token.refresh_from_db()
        self.assertFalse(old_token.is_active)

    def _practice_token(self):
        return GoogleCalendarToken.objects.create(
            token="practice-token",
            refresh_token="practice-refresh",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="practice-client",
            client_secret="practice-secret",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            is_active=True,
            practice=self.practice,
        )

    def test_no_practice_does_not_pick_up_a_practice_token(self):
        # A user without a practice passes None; that used to return any
        # practice's token and so its calendar.
        self._practice_token()
        self.assertIsNone(GoogleCalendarOAuth.get_active_token(None))

    def test_saving_a_practice_less_token_leaves_practice_tokens_active(self):
        token = self._practice_token()
        mock_creds = Mock(
            token="new-token",
            refresh_token="new-refresh",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="new-client",
            client_secret="new-secret",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            expiry=None,
        )
        GoogleCalendarOAuth.save_token(mock_creds, practice=None)
        token.refresh_from_db()
        self.assertTrue(token.is_active)

    @patch("my_practice.utils.google_calendar.build")
    def test_get_service_with_valid_token(self, mock_build):
        """Test getting calendar service with valid token."""
        # Create active token
        GoogleCalendarToken.objects.create(
            token="test-token",
            refresh_token="test-refresh",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client",
            client_secret="test-secret",
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            is_active=True,
            practice=self.practice,
        )

        service = GoogleCalendarOAuth.get_service(practice=self.practice)

        # Verify service built
        self.assertIsNotNone(service)
        # Check that build was called (credentials object will be different)
        self.assertTrue(mock_build.called)

    def test_get_service_without_token(self):
        """Test getting service when no token exists."""
        service = GoogleCalendarOAuth.get_service()
        self.assertIsNone(service)


class CalendarEventParserTest(TestCase):
    """Test calendar event parsing utilities."""

    def setUp(self):
        """Create ServiceType objects needed for tests."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="google_calendar-1",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        ServiceType.objects.create(
            code="checkin_15",
            name="Check-in",
            name_de="Check-in Termin",
            practice=self.practice,
        )
        ServiceType.objects.create(
            code="initial_consultation",
            name="Initial Consultation",
            name_de="Vorgespräch",
            practice=self.practice,
        )
        ServiceType.objects.create(
            code="therapy_60",
            name="Session",
            name_de="Standardsitzung",
            practice=self.practice,
        )
        ServiceType.objects.create(
            code="therapy_90",
            name="Extended Session",
            name_de="Verlängerte Sitzung",
            practice=self.practice,
        )
        ServiceType.objects.create(
            code="therapy_cancelled",
            name="Cancellation",
            name_de="Ausgefallener Termin",
            practice=self.practice,
        )

    def test_parse_datetime_with_time(self):
        """Test parsing datetime string with time component."""
        # Create practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test-practice",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )

        dt_str = "2025-12-23T14:30:00Z"
        result = CalendarEventParser.parse_datetime(dt_str)

        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 12)
        self.assertEqual(result.day, 23)

    def test_parse_datetime_date_only(self):
        """Test parsing date-only string."""
        date_str = "2025-12-23"
        result = CalendarEventParser.parse_datetime(date_str)

        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 12)
        self.assertEqual(result.day, 23)

    def test_parse_datetime_invalid(self):
        """Test parsing invalid datetime string."""
        result = CalendarEventParser.parse_datetime("invalid")
        self.assertIsNone(result)

    def test_calculate_duration(self):
        """Test duration calculation between two datetimes."""
        start = datetime(2025, 12, 23, 14, 0, 0, tzinfo=dt_timezone.utc)
        end = datetime(2025, 12, 23, 15, 0, 0, tzinfo=dt_timezone.utc)

        duration = CalendarEventParser.calculate_duration(start, end)
        self.assertEqual(duration, 60)

    def test_calculate_duration_invalid(self):
        """Test duration calculation with invalid dates."""
        duration = CalendarEventParser.calculate_duration(None, None)
        self.assertEqual(duration, 0)

    def test_match_client_exact_match(self):
        """Test matching client by code in event summary."""
        client = Client.objects.create(
            full_name="John Doe",
            client_code="JD",
            email="john@example.com",
            practice=self.practice,
        )

        result = CalendarEventParser.match_client("JD 60min session", Client.objects.all())
        self.assertEqual(result, client)

    def test_match_client_case_insensitive(self):
        """Test client matching is case-insensitive."""
        client = Client.objects.create(
            full_name="Jane Smith",
            client_code="JS",
            email="jane@example.com",
            practice=self.practice,
        )

        result = CalendarEventParser.match_client("js therapy session", Client.objects.all())
        self.assertEqual(result, client)

    def test_match_client_no_match(self):
        """Test client matching with no match."""
        Client.objects.create(
            full_name="Bob Brown",
            client_code="BB",
            email="bob@example.com",
            practice=self.practice,
        )

        result = CalendarEventParser.match_client("Unknown client XX", Client.objects.all())
        self.assertIsNone(result)

    def test_match_client_empty_code(self):
        """Test client matching when client has empty code."""
        Client.objects.create(
            full_name="Alice Johnson",
            client_code="",
            email="alice@example.com",
            practice=self.practice,
        )

        result = CalendarEventParser.match_client("AJ session", Client.objects.all())
        self.assertIsNone(result)

    def _make_clients(self, *codes):
        """Create clients for the given codes, returned as a code -> Client map."""
        return {
            code: Client.objects.create(
                full_name=f"Client {code}",
                client_code=code,
                email=f"{code.lower()}@example.com",
                practice=self.practice,
            )
            for code in codes
        }

    def test_match_client_ignores_code_inside_a_word(self):
        """A code embedded in a longer word is not a match.

        Intro calls are titled with a short name abbreviation; with 2-letter codes
        a plain substring search booked them onto unrelated clients.
        """
        self._make_clients("AT", "CA", "LB")

        for summary in ("Nat", "CAR", "LBW"):
            with self.subTest(summary=summary):
                self.assertIsNone(CalendarEventParser.match_client(summary, Client.objects.all()))

    def test_match_client_ignores_code_inside_a_german_or_status_word(self):
        """Ordinary calendar words must not match a client code."""
        self._make_clients("EL", "FR", "MA", "CK")

        for summary in ("Frei", "Mail", "Blocked", "cancel"):
            with self.subTest(summary=summary):
                self.assertIsNone(CalendarEventParser.match_client(summary, Client.objects.all()))

    def test_match_client_prefers_the_longest_code(self):
        """A summary equal to a longer code matches that code, not its prefix."""
        clients = self._make_clients("TO", "TOB")

        self.assertEqual(
            CalendarEventParser.match_client("TOB", Client.objects.all()), clients["TOB"]
        )
        self.assertEqual(
            CalendarEventParser.match_client("TO", Client.objects.all()), clients["TO"]
        )

    def test_match_client_hyphen_is_part_of_the_code(self):
        """A hyphen does not delimit a code, so MM does not match inside MM-G."""
        clients = self._make_clients("MM", "MM-G")

        self.assertEqual(
            CalendarEventParser.match_client("MM-G 60min", Client.objects.all()), clients["MM-G"]
        )
        self.assertEqual(
            CalendarEventParser.match_client("MM 60min", Client.objects.all()), clients["MM"]
        )

    def test_match_client_with_cancel_suffix(self):
        """A cancelled session still matches its own code, not one inside 'cancel'."""
        clients = self._make_clients("ZK", "EL")

        self.assertEqual(
            CalendarEventParser.match_client("ZK (cancel)", Client.objects.all()), clients["ZK"]
        )

    def test_is_cancelled_with_parentheses(self):
        """Test cancelled detection with (cancel) format."""
        self.assertTrue(CalendarEventParser.is_cancelled("JD 60min (cancel)"))

    def test_is_cancelled_without_parentheses(self):
        """Test cancelled detection with cancel word."""
        self.assertTrue(CalendarEventParser.is_cancelled("JD session cancel"))

    def test_is_cancelled_false(self):
        """Test cancelled detection returns false for normal events."""
        self.assertFalse(CalendarEventParser.is_cancelled("JD 60min session"))

    def test_parse_event_complete(self):
        """Test parsing complete event with all fields."""
        client = Client.objects.create(
            full_name="Test Client",
            client_code="TC",
            email="test@example.com",
            practice=self.practice,
        )

        event = {
            "summary": "TC 60min therapy",
            "start": {"dateTime": "2025-12-23T14:00:00Z"},
            "end": {"dateTime": "2025-12-23T15:00:00Z"},
        }

        result = CalendarEventParser.parse_event(
            event, Client.objects.all(), practice=self.practice
        )

        self.assertEqual(result["summary"], "TC 60min therapy")
        self.assertIsNotNone(result["start"])
        self.assertIsNotNone(result["end"])
        self.assertEqual(result["duration_minutes"], 60)
        self.assertEqual(result["matched_client"], client)
        self.assertFalse(result["is_cancelled"])
        self.assertEqual(result["original"], event)

    def test_parse_event_cancelled(self):
        """Test parsing cancelled event."""
        event = {
            "summary": "XX 60min (cancel)",
            "start": {"dateTime": "2025-12-23T14:00:00Z"},
            "end": {"dateTime": "2025-12-23T15:00:00Z"},
        }

        result = CalendarEventParser.parse_event(
            event, Client.objects.all(), practice=self.practice
        )
        self.assertTrue(result["is_cancelled"])
        self.assertIsNone(result["matched_client"])

    def test_parse_events_multiple(self):
        """Test parsing multiple events."""
        client1 = Client.objects.create(
            full_name="Client One",
            client_code="C1",
            email="c1@example.com",
            practice=self.practice,
        )
        client2 = Client.objects.create(
            full_name="Client Two",
            client_code="C2",
            email="c2@example.com",
            practice=self.practice,
        )

        events = [
            {
                "summary": "C1 60min",
                "start": {"dateTime": "2025-12-23T10:00:00Z"},
                "end": {"dateTime": "2025-12-23T11:00:00Z"},
            },
            {
                "summary": "C2 90min",
                "start": {"dateTime": "2025-12-23T14:00:00Z"},
                "end": {"dateTime": "2025-12-23T15:30:00Z"},
            },
        ]

        results = CalendarEventParser.parse_events(
            events, Client.objects.all(), practice=self.practice
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["matched_client"], client1)
        self.assertEqual(results[0]["duration_minutes"], 60)
        self.assertEqual(results[1]["matched_client"], client2)
        self.assertEqual(results[1]["duration_minutes"], 90)

    def test_map_duration_to_service_type_checkin(self):
        """Test mapping 15-minute events to Check-in."""
        service_type, description = CalendarEventParser.map_duration_to_service_type(
            15, practice=self.practice
        )
        self.assertIsNotNone(service_type)
        self.assertEqual(service_type.code, "checkin_15")
        self.assertEqual(description, "Check-in Termin")

    def test_map_duration_to_service_type_free_consultation(self):
        """Test mapping 20-minute events to the free initial-consultation service type."""
        service_type, description = CalendarEventParser.map_duration_to_service_type(
            20, practice=self.practice
        )
        self.assertIsNotNone(service_type)
        self.assertEqual(service_type.code, "initial_consultation")
        self.assertEqual(description, "Vorgespräch")

    def test_map_duration_to_service_type_warns_on_unknown_code(self):
        """An unseeded code must be logged, not silently degrade to no suggestion.

        A code with no ServiceType row also disables every rule keyed on that code
        (free-consult rate, auto-skip), which is invisible without the warning.
        """
        with (
            patch.dict(
                "my_practice.utils.google_calendar.DURATION_TO_SERVICE_CODE",
                {(18, 22): "does_not_exist"},
                clear=True,
            ),
            self.assertLogs("my_practice.utils.google_calendar", level="WARNING") as logs,
        ):
            service_type, description = CalendarEventParser.map_duration_to_service_type(
                20, practice=self.practice
            )

        self.assertIsNone(service_type)
        self.assertIsNone(description)
        self.assertIn("does_not_exist", logs.output[0])

    def test_map_duration_to_service_type_standard_session(self):
        """Test mapping 60-minute events to Sitzung."""
        service_type, description = CalendarEventParser.map_duration_to_service_type(
            60, practice=self.practice
        )
        self.assertIsNotNone(service_type)
        self.assertEqual(service_type.code, "therapy_60")
        self.assertEqual(description, "Standardsitzung")

    def test_map_duration_to_service_type_extended_session(self):
        """Test mapping 90-minute events to Sitzung."""
        service_type, description = CalendarEventParser.map_duration_to_service_type(
            90, practice=self.practice
        )
        self.assertIsNotNone(service_type)
        self.assertEqual(service_type.code, "therapy_90")
        self.assertEqual(description, "Verlängerte Sitzung")

    def test_map_duration_to_service_type_no_match(self):
        """Test duration that doesn't match any mapping."""
        service_type, description = CalendarEventParser.map_duration_to_service_type(
            45, practice=self.practice
        )
        self.assertIsNone(service_type)
        self.assertIsNone(description)

    def test_parse_event_includes_service_type_suggestion(self):
        """Test that parse_event includes suggested service type."""
        event = {
            "summary": "ABC123 Session",
            "start": {"dateTime": "2024-01-15T14:00:00+01:00"},
            "end": {"dateTime": "2024-01-15T15:00:00+01:00"},  # 60 minutes
        }

        result = CalendarEventParser.parse_event(
            event, Client.objects.all(), practice=self.practice
        )

        self.assertIsNotNone(result["suggested_service_type_obj"])
        self.assertEqual(result["suggested_service_type_obj"].code, "therapy_60")
        self.assertEqual(result["suggested_service_type"], "Standardsitzung")

    def test_parse_event_cancelled_overrides_service_type(self):
        """Test that cancelled events get Ausfall service type."""
        event = {
            "summary": "ABC123 (cancel)",
            "start": {"dateTime": "2024-01-15T14:00:00+01:00"},
            "end": {"dateTime": "2024-01-15T15:00:00+01:00"},  # 60 minutes
        }

        result = CalendarEventParser.parse_event(
            event, Client.objects.all(), practice=self.practice
        )

        self.assertTrue(result["is_cancelled"])
        self.assertIsNotNone(result["suggested_service_type_obj"])
        self.assertEqual(result["suggested_service_type_obj"].code, "therapy_cancelled")
        self.assertEqual(result["suggested_service_type"], "Ausgefallener Termin")


class ListCalendarsTest(TestCase):
    """Test the calendar-listing utility behind the calendar-selection picker."""

    def test_list_calendars(self):
        """Returns id/name/primary for every calendar the account can see."""
        mock_service = Mock()
        mock_service.calendarList().list().execute.return_value = {
            "items": [
                {"id": "cal1", "summary": "Personal"},
                {"id": "cal2", "summary": "Praxis", "primary": True},
                {"id": "cal3", "summary": "Work"},
            ]
        }

        result = list_calendars(mock_service)
        self.assertEqual(
            result,
            [
                {"id": "cal1", "name": "Personal", "primary": False},
                {"id": "cal2", "name": "Praxis", "primary": True},
                {"id": "cal3", "name": "Work", "primary": False},
            ],
        )

    def test_list_calendars_empty(self):
        """No calendars on the account returns an empty list, not an error."""
        mock_service = Mock()
        mock_service.calendarList().list().execute.return_value = {"items": []}

        self.assertEqual(list_calendars(mock_service), [])

    def test_list_calendars_falls_back_to_id_when_summary_missing(self):
        mock_service = Mock()
        mock_service.calendarList().list().execute.return_value = {"items": [{"id": "cal1"}]}

        result = list_calendars(mock_service)
        self.assertEqual(result, [{"id": "cal1", "name": "cal1", "primary": False}])


class UpsertEventReinstatementTest(TestCase):
    """Test that _upsert_event reinstates previously-cancelled events."""

    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="reinstatement-test",
            title="Test Practitioner",
            email="test@example.com",
            city="Berlin",
        )
        self.client = Client.objects.create(
            practice=self.practice,
            client_code="XX",
            full_name="Max Mustermann",
            email="max@example.com",
        )
        self.session_date = date(2026, 6, 10)
        self.session = Session.objects.create(
            client=self.client,
            session_date=self.session_date,
            session_time=None,
            duration=60,
            cancelled=True,
        )
        self.pce = PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="test-event-id-123",
            summary="XX 60min",
            event_date=self.session_date,
            event_time=None,
            duration_minutes=60,
            matched_client=self.client,
            status=PendingCalendarEvent.Status.CANCELLED,
            session=self.session,
        )

    def _make_event(self, is_cancelled=False):
        return {
            "id": "test-event-id-123",
            "start": self.session_date,
            "summary": "XX 60min",
            "duration_minutes": 60,
            "matched_client": self.client,
            "suggested_service_type_obj": None,
            "is_cancelled": is_cancelled,
        }

    def _get_command(self):
        from my_practice.management.commands.fetch_calendar_events import Command

        cmd = Command()
        cmd.stdout = StringIO()
        cmd.style = type("S", (), {"SUCCESS": lambda s, x: x, "WARNING": lambda s, x: x})()
        return cmd

    def test_reinstates_cancelled_event(self):
        """An event returning as active in Google Calendar un-cancels the local Session."""
        cmd = self._get_command()
        result = cmd._upsert_event(
            self._make_event(is_cancelled=False), self.practice, dry_run=False
        )

        self.assertEqual(result, "reinstated")
        self.pce.refresh_from_db()
        self.session.refresh_from_db()
        self.assertEqual(self.pce.status, PendingCalendarEvent.Status.PENDING)
        self.assertFalse(self.session.cancelled)

    def test_cancellation_still_works(self):
        """A PENDING event returned as cancelled is still cancelled correctly."""
        self.pce.status = PendingCalendarEvent.Status.PENDING
        self.pce.save()
        self.session.cancelled = False
        self.session.save()

        cmd = self._get_command()
        result = cmd._upsert_event(
            self._make_event(is_cancelled=True), self.practice, dry_run=False
        )

        self.assertEqual(result, "skipped")
        self.pce.refresh_from_db()
        self.session.refresh_from_db()
        self.assertEqual(self.pce.status, PendingCalendarEvent.Status.CANCELLED)
        self.assertTrue(self.session.cancelled)


class FetchTagSyncTest(TestCase):
    """The fetch command re-syncs the no-next-session tag for clients whose
    sessions it created or cancelled, instead of waiting for the next
    update_client_tags run."""

    def setUp(self):
        from my_practice.models import ClientTag

        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="fetch-tag-sync-test",
            title="Test Practitioner",
            email="test@example.com",
            city="Berlin",
        )
        self.client_obj = Client.objects.create(
            practice=self.practice,
            client_code="XX-1",
            full_name="Max Mustermann",
            email="max@example.com",
        )
        self.tag = ClientTag.objects.create(
            slug="no-next-session",
            name="no-next-session",
            color="orange",
            category="attention",
            is_system=True,
        )
        self.today = timezone.localdate()
        # Recent past session so the client counts as "recently active"
        Session.objects.create(
            client=self.client_obj,
            session_date=self.today - timedelta(days=5),
            duration=60,
            cancelled=False,
        )
        self.future_date = self.today + timedelta(days=7)

    def _get_command(self):
        from my_practice.management.commands.fetch_calendar_events import Command

        cmd = Command()
        cmd.stdout = StringIO()
        cmd.style = type("S", (), {"SUCCESS": lambda s, x: x, "WARNING": lambda s, x: x})()
        return cmd

    def _make_event(self, event_id, is_cancelled=False):
        return {
            "id": event_id,
            "start": self.future_date,
            "summary": "XX-1 60min",
            "duration_minutes": 60,
            "matched_client": self.client_obj,
            "suggested_service_type_obj": None,
            "is_cancelled": is_cancelled,
        }

    def test_auto_created_future_session_removes_tag(self):
        """A new future event auto-creates a Session → tag is removed."""
        self.client_obj.tags.add(self.tag)
        cmd = self._get_command()
        affected: set = set()

        result = cmd._upsert_event(
            self._make_event("new-event-1"), self.practice, dry_run=False, affected_clients=affected
        )

        self.assertEqual(result, "created")
        self.assertIn(self.client_obj, affected)
        cmd._sync_no_next_session_tags(affected)
        self.assertFalse(self.client_obj.tags.filter(slug="no-next-session").exists())

    def test_cancelling_only_future_session_adds_tag(self):
        """Cancelling the client's only future session → tag is added."""
        session = Session.objects.create(
            client=self.client_obj,
            session_date=self.future_date,
            duration=60,
            cancelled=False,
        )
        PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="event-to-cancel",
            summary="XX-1 60min",
            event_date=self.future_date,
            duration_minutes=60,
            matched_client=self.client_obj,
            status=PendingCalendarEvent.Status.PENDING,
            session=session,
        )
        cmd = self._get_command()
        affected: set = set()

        result = cmd._upsert_event(
            self._make_event("event-to-cancel", is_cancelled=True),
            self.practice,
            dry_run=False,
            affected_clients=affected,
        )

        self.assertEqual(result, "skipped")
        self.assertIn(self.client_obj, affected)
        cmd._sync_no_next_session_tags(affected)
        self.assertTrue(self.client_obj.tags.filter(slug="no-next-session").exists())

    def test_stale_event_cancellation_collects_client(self):
        """_cancel_stale_future_events collects the client when its session is
        cancelled — which only happens on the second consecutive miss (the
        first miss just starts the debounce clock, see missing_since)."""
        session = Session.objects.create(
            client=self.client_obj,
            session_date=self.future_date,
            duration=60,
            cancelled=False,
        )
        PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="vanished-event",
            summary="XX-1 60min",
            event_date=self.future_date,
            duration_minutes=60,
            matched_client=self.client_obj,
            status=PendingCalendarEvent.Status.PENDING,
            session=session,
            missing_since=timezone.now() - timedelta(hours=6),
        )
        cmd = self._get_command()
        affected: set = set()

        start_dt = timezone.now()
        end_dt = start_dt + timedelta(days=14)
        cancelled, flagged = cmd._cancel_stale_future_events(
            self.practice,
            start_dt,
            end_dt,
            live_ids=set(),
            dry_run=False,
            affected_clients=affected,
        )

        self.assertEqual(cancelled, 1)
        self.assertEqual(flagged, 0)
        self.assertIn(self.client_obj, affected)
        session.refresh_from_db()
        self.assertTrue(session.cancelled)


class PracticeScopedMatchingTests(TestCase):
    """A practice's calendar only ever matches that practice's clients."""

    def setUp(self):
        self.own = Practice.objects.create(name="Own Practice", slug="own-calendar", title="T")
        other = Practice.objects.create(name="Test GmbH", slug="other-calendar", title="T")
        self.foreign = Client.objects.create(
            client_code="YY", full_name="Anna Schmidt", practice=other
        )

    def test_other_practices_client_code_does_not_match(self):
        event = {
            "id": "evt-1",
            "summary": "YY 60min",
            "start": {"dateTime": "2026-10-01T10:00:00+02:00"},
            "end": {"dateTime": "2026-10-01T11:00:00+02:00"},
        }
        parsed = CalendarEventParser.parse_events(
            [event], practice_clients(self.own), practice=self.own
        )
        self.assertIsNone(parsed[0]["matched_client"])

    def test_stored_foreign_match_is_not_imported(self):
        client, error = _resolve_client(
            {"matched_client": self.foreign, "summary": "YY"}, {}, self.own
        )
        self.assertIsNone(client)
        self.assertIsNotNone(error)


class ServiceTypeSuggestionScopeTest(TestCase):
    """Event suggestions only use the importing practice's own or global service types."""

    def setUp(self):
        self.own = Practice.objects.create(name="A", slug="st-own", title="T")
        self.other = Practice.objects.create(name="B", slug="st-other", title="T")
        self.event = {
            "id": "evt-1",
            "summary": "XX (cancel)",
            "start": {"dateTime": "2026-02-03T09:00:00+01:00"},
            "end": {"dateTime": "2026-02-03T10:00:00+01:00"},
        }

    def test_other_practices_cancel_type_is_not_suggested(self):
        ServiceType.objects.create(code="a_late_cancel", name="Late cancel B", practice=self.other)
        result = CalendarEventParser.parse_event(self.event, [], practice=self.own)
        self.assertIsNone(result["suggested_service_type_obj"])

    def test_own_cancel_type_wins_over_global(self):
        ServiceType.objects.create(code="a_cancel", name="Global cancel")
        own = ServiceType.objects.create(code="z_cancel", name="Own cancel", practice=self.own)
        result = CalendarEventParser.parse_event(self.event, [], practice=self.own)
        self.assertEqual(result["suggested_service_type_obj"], own)
