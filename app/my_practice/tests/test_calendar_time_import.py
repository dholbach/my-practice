"""
Tests for calendar event time import functionality (P-003).
"""

from datetime import datetime, time
from unittest.mock import Mock

from django.test import TestCase

from ..models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session, UserPractice
from ..utils.google_calendar import CalendarEventParser
from ..utils.calendar_import_helpers import create_invoice_items_from_events


class CalendarTimeImportTest(TestCase):
    """Test time preservation during calendar import"""

    def setUp(self):
        """Set up test data"""
        # Create test practice
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="test",
        )

        # Create test user (admin superuser created by Django)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(username="testuser", password="testpass")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)

        # Create test client
        self.client_obj = Client.objects.create(
            client_code="TK",
            full_name="Test Klient",
            email="test@example.com",
            hourly_rate_60=90,
            hourly_rate_90=130,
            practice=self.practice,
        )

        # Create service types
        self.therapy_60 = ServiceType.objects.create(
            practice=None,  # Global
            code="therapy_60",
            name="Therapiesitzung (60 Min)",
            default_duration=60,
        )

        self.therapy_90 = ServiceType.objects.create(
            practice=None,  # Global
            code="therapy_90",
            name="Therapiesitzung (90 Min)",
            default_duration=90,
        )

    def test_parse_event_preserves_time(self):
        """Test that CalendarEventParser preserves time from datetime"""
        # Mock calendar event with time
        event = {
            "id": "test123",
            "summary": "TK Session",
            "start": {"dateTime": "2026-02-03T09:30:00+01:00"},
            "end": {"dateTime": "2026-02-03T10:30:00+01:00"},
        }

        parsed = CalendarEventParser.parse_event(event, [self.client_obj])

        # Verify datetime object includes time
        self.assertIsInstance(parsed["start"], datetime)
        self.assertEqual(parsed["start"].hour, 9)
        self.assertEqual(parsed["start"].minute, 30)
        self.assertEqual(parsed["duration_minutes"], 60)

    def test_create_invoice_item_with_time(self):
        """Test that InvoiceItem is created with session_time"""
        # Simulate parsed event with time
        event_datetime = datetime(2026, 2, 3, 14, 0, 0)  # 14:00
        parsed_event = {
            "id": "event123",
            "summary": "TK Session",
            "start": event_datetime,
            "end": datetime(2026, 2, 3, 15, 0, 0),
            "duration_minutes": 60,
            "matched_client": self.client_obj,
            "suggested_service_type_obj": self.therapy_60,
            "is_cancelled": False,
        }

        # Create mock request with current_practice
        request = Mock()
        request.current_practice = self.practice

        # Import event
        created, skipped, errors = create_invoice_items_from_events(
            approved_events=[parsed_event], user_overrides={}, request=request
        )

        # Verify creation
        self.assertEqual(created, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(errors, [])

        # Verify InvoiceItem has time via session
        session = Session.objects.get(calendar_event_id="event123")
        item = InvoiceItem.objects.select_related("session").get(session=session)
        self.assertIsNotNone(item.session.session_time)
        self.assertEqual(item.session.session_time, time(14, 0))
        self.assertEqual(item.session.session_date.day, 3)

    def test_create_invoice_item_without_time_all_day_event(self):
        """Test that all-day events (date only) have None for session_time"""
        # All-day event (no time component)
        event = {
            "id": "allday123",
            "summary": "TK Session",
            "start": {"date": "2026-02-05"},
            "end": {"date": "2026-02-05"},
        }

        parsed = CalendarEventParser.parse_event(event, [self.client_obj])

        # Create mock request
        request = Mock()
        request.current_practice = self.practice

        # Import event
        created, skipped, errors = create_invoice_items_from_events(
            approved_events=[parsed], user_overrides={}, request=request
        )

        # Verify creation
        self.assertEqual(created, 1)

        # Verify InvoiceItem has no time (all-day event)
        session = Session.objects.get(calendar_event_id="allday123")
        item = InvoiceItem.objects.select_related("session").get(session=session)
        # All-day events get time(0, 0) from parse_datetime, which is expected
        self.assertEqual(item.session.session_time, time(0, 0))
        self.assertEqual(item.session.session_date.day, 5)

    def test_multiple_sessions_same_day_different_times(self):
        """Test importing multiple sessions on same day with different times"""
        # Morning session
        morning_event = {
            "id": "morning123",
            "summary": "TK Session",
            "start": datetime(2026, 2, 10, 9, 0, 0),
            "end": datetime(2026, 2, 10, 10, 0, 0),
            "duration_minutes": 60,
            "matched_client": self.client_obj,
            "suggested_service_type_obj": self.therapy_60,
            "is_cancelled": False,
        }

        # Afternoon session
        afternoon_event = {
            "id": "afternoon123",
            "summary": "TK Session",
            "start": datetime(2026, 2, 10, 15, 0, 0),
            "end": datetime(2026, 2, 10, 16, 30, 0),
            "duration_minutes": 90,
            "matched_client": self.client_obj,
            "suggested_service_type_obj": self.therapy_90,
            "is_cancelled": False,
        }

        request = Mock()
        request.current_practice = self.practice

        # Import both events
        created, skipped, errors = create_invoice_items_from_events(
            approved_events=[morning_event, afternoon_event],
            user_overrides={},
            request=request,
        )

        # Verify both created
        self.assertEqual(created, 2)
        self.assertEqual(skipped, 0)

        # Verify times are distinct
        morning_item = InvoiceItem.objects.select_related("session").get(
            session__calendar_event_id="morning123"
        )
        afternoon_item = InvoiceItem.objects.select_related("session").get(
            session__calendar_event_id="afternoon123"
        )

        self.assertEqual(morning_item.session.session_time, time(9, 0))
        self.assertEqual(afternoon_item.session.session_time, time(15, 0))
        self.assertEqual(morning_item.session.session_date, afternoon_item.session.session_date)

    def test_agenda_query_sessions_ordered_by_time(self):
        """Test querying sessions ordered by time for agenda view"""
        # Create invoice
        invoice = Invoice.objects.create(
            client=self.client_obj,
            invoice_date="2026-02-15",
            invoice_number="RE-2026-001",
            status="draft",
            practice=self.practice,
        )

        # Create sessions at different times
        s1 = Session.objects.create(
            client=self.client_obj, session_date="2026-02-15", session_time=time(15, 0), duration=60
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.therapy_60,
            session=s1,
            rate=90,
        )

        s2 = Session.objects.create(
            client=self.client_obj, session_date="2026-02-15", session_time=time(9, 0), duration=60
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.therapy_60,
            session=s2,
            rate=90,
        )

        s3 = Session.objects.create(
            client=self.client_obj, session_date="2026-02-15", session_time=None, duration=90
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.therapy_90,
            session=s3,
            rate=130,
        )

        # Query sessions for Feb 15, sort manually for agenda view
        from datetime import time as dt_time

        sessions = list(
            InvoiceItem.objects.filter(session__session_date="2026-02-15")
            .select_related("session")
            .order_by("session__session_time")
        )

        # Sort manually to get expected order (time asc, nulls last)
        sessions_sorted = sorted(
            sessions,
            key=lambda x: (x.session.session_time is None, x.session.session_time or dt_time(0, 0)),
        )
        times_sorted = [s.session.session_time for s in sessions_sorted]
        self.assertEqual(times_sorted, [time(9, 0), time(15, 0), None])
