"""
Tests for Google Calendar utilities.
"""

from datetime import date, datetime
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
from my_practice.utils.google_calendar import (
    CalendarEventParser,
    GoogleCalendarOAuth,
    find_calendar_by_name,
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
        GoogleCalendarOAuth.save_token(mock_creds)

        # Verify old token deactivated
        old_token.refresh_from_db()
        self.assertFalse(old_token.is_active)

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

        service = GoogleCalendarOAuth.get_service()

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
            code="therapy_15",
            name="Check-in",
            name_de="Check-in Termin",
            practice=self.practice,
        )
        ServiceType.objects.create(
            code="therapy_free",
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

        result = CalendarEventParser.match_client("JD 60min session")
        self.assertEqual(result, client)

    def test_match_client_case_insensitive(self):
        """Test client matching is case-insensitive."""
        client = Client.objects.create(
            full_name="Jane Smith",
            client_code="JS",
            email="jane@example.com",
            practice=self.practice,
        )

        result = CalendarEventParser.match_client("js therapy session")
        self.assertEqual(result, client)

    def test_match_client_no_match(self):
        """Test client matching with no match."""
        Client.objects.create(
            full_name="Bob Brown",
            client_code="BB",
            email="bob@example.com",
            practice=self.practice,
        )

        result = CalendarEventParser.match_client("Unknown client XX")
        self.assertIsNone(result)

    def test_match_client_empty_code(self):
        """Test client matching when client has empty code."""
        Client.objects.create(
            full_name="Alice Johnson",
            client_code="",
            email="alice@example.com",
            practice=self.practice,
        )

        result = CalendarEventParser.match_client("AJ session")
        self.assertIsNone(result)

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

        result = CalendarEventParser.parse_event(event)

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

        result = CalendarEventParser.parse_event(event)
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

        results = CalendarEventParser.parse_events(events)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["matched_client"], client1)
        self.assertEqual(results[0]["duration_minutes"], 60)
        self.assertEqual(results[1]["matched_client"], client2)
        self.assertEqual(results[1]["duration_minutes"], 90)

    def test_map_duration_to_service_type_checkin(self):
        """Test mapping 15-minute events to Check-in."""
        service_type, description = CalendarEventParser.map_duration_to_service_type(15)
        self.assertIsNotNone(service_type)
        self.assertEqual(service_type.code, "therapy_15")
        self.assertEqual(description, "Check-in Termin")

    def test_map_duration_to_service_type_free_consultation(self):
        """Test mapping 20-minute events to the free initial-consultation service type."""
        service_type, description = CalendarEventParser.map_duration_to_service_type(20)
        self.assertIsNotNone(service_type)
        self.assertEqual(service_type.code, "therapy_free")
        self.assertEqual(description, "Vorgespräch")

    def test_map_duration_to_service_type_standard_session(self):
        """Test mapping 60-minute events to Sitzung."""
        service_type, description = CalendarEventParser.map_duration_to_service_type(60)
        self.assertIsNotNone(service_type)
        self.assertEqual(service_type.code, "therapy_60")
        self.assertEqual(description, "Standardsitzung")

    def test_map_duration_to_service_type_extended_session(self):
        """Test mapping 90-minute events to Sitzung."""
        service_type, description = CalendarEventParser.map_duration_to_service_type(90)
        self.assertIsNotNone(service_type)
        self.assertEqual(service_type.code, "therapy_90")
        self.assertEqual(description, "Verlängerte Sitzung")

    def test_map_duration_to_service_type_no_match(self):
        """Test duration that doesn't match any mapping."""
        service_type, description = CalendarEventParser.map_duration_to_service_type(45)
        self.assertIsNone(service_type)
        self.assertIsNone(description)

    def test_parse_event_includes_service_type_suggestion(self):
        """Test that parse_event includes suggested service type."""
        event = {
            "summary": "ABC123 Session",
            "start": {"dateTime": "2024-01-15T14:00:00+01:00"},
            "end": {"dateTime": "2024-01-15T15:00:00+01:00"},  # 60 minutes
        }

        result = CalendarEventParser.parse_event(event)

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

        result = CalendarEventParser.parse_event(event)

        self.assertTrue(result["is_cancelled"])
        self.assertIsNotNone(result["suggested_service_type_obj"])
        self.assertEqual(result["suggested_service_type_obj"].code, "therapy_cancelled")
        self.assertEqual(result["suggested_service_type"], "Ausgefallener Termin")


class FindCalendarByNameTest(TestCase):
    """Test calendar lookup utility."""

    def test_find_calendar_by_name(self):
        """Test finding calendar by name."""
        mock_service = Mock()
        mock_service.calendarList().list().execute.return_value = {
            "items": [
                {"id": "cal1", "summary": "Personal"},
                {"id": "cal2", "summary": "Praxis"},
                {"id": "cal3", "summary": "Work"},
            ]
        }

        result = find_calendar_by_name(mock_service, "Praxis")
        self.assertEqual(result, "cal2")

    def test_find_calendar_case_insensitive(self):
        """Test calendar lookup is case-insensitive."""
        mock_service = Mock()
        mock_service.calendarList().list().execute.return_value = {
            "items": [
                {"id": "cal1", "summary": "PRAXIS"},
            ]
        }

        result = find_calendar_by_name(mock_service, "praxis")
        self.assertEqual(result, "cal1")

    def test_find_calendar_not_found(self):
        """Test calendar lookup when calendar doesn't exist."""
        mock_service = Mock()
        mock_service.calendarList().list().execute.return_value = {
            "items": [
                {"id": "cal1", "summary": "Personal"},
            ]
        }

        result = find_calendar_by_name(mock_service, "NonExistent")
        self.assertIsNone(result)

    def test_find_calendar_api_error(self):
        """Test calendar lookup handles API errors gracefully."""
        mock_service = Mock()
        mock_service.calendarList().list().execute.side_effect = Exception("API Error")

        result = find_calendar_by_name(mock_service, "Praxis")
        self.assertIsNone(result)


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
