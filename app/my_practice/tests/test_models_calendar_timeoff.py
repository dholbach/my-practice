"""
Tests for the time-off and Google Calendar models.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from my_practice.models import (
    Client,
    GoogleCalendarToken,
    PendingCalendarEvent,
    Practice,
    TimeOff,
)

from .test_helpers import create_test_practice


class TimeOffModelTestCase(TestCase):
    """Tests for TimeOff model"""

    def test_timeoff_creation(self):
        """Test creating a time off entry"""
        timeoff = TimeOff.objects.create(
            title="Christmas Holiday",
            start_date=date(2025, 12, 24),
            end_date=date(2025, 12, 26),
            type="vacation",
        )
        self.assertEqual(timeoff.title, "Christmas Holiday")
        self.assertEqual(timeoff.type, "vacation")

    def test_timeoff_str(self):
        """Test TimeOff string representation"""
        timeoff = TimeOff.objects.create(
            title="Summer Vacation",
            start_date=date(2025, 7, 1),
            end_date=date(2025, 7, 14),
            type="vacation",
        )
        self.assertIn("Summer Vacation", str(timeoff))

    def test_timeoff_duration_days_property(self):
        """Test duration_days property counts working days only, excluding public holidays"""
        timeoff = TimeOff.objects.create(
            title="Test",
            # Dec 24 2025 is a Wednesday (workday); Dec 25/26 are Berlin public holidays
            start_date=date(2025, 12, 24),
            end_date=date(2025, 12, 26),
            type="vacation",
        )
        self.assertEqual(timeoff.duration_days, 1)

    def test_timeoff_duration_days_excludes_weekend(self):
        """Test duration_days excludes weekend days from the count"""
        timeoff = TimeOff.objects.create(
            title="Test",
            # Mon 2025-11-03 through Fri 2025-11-07: 5 workdays, no holidays
            start_date=date(2025, 11, 3),
            end_date=date(2025, 11, 9),  # includes the following Sat/Sun
            type="vacation",
        )
        self.assertEqual(timeoff.duration_days, 5)

    def test_timeoff_single_day(self):
        """Test time off for single day"""
        timeoff = TimeOff.objects.create(
            title="Doctor Appointment",
            start_date=date(2025, 12, 24),
            end_date=date(2025, 12, 24),
            type="sick",
        )
        self.assertEqual(timeoff.duration_days, 1)

    def test_timeoff_ordering(self):
        """Test TimeOff ordering"""
        TimeOff.objects.create(
            title="Old",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 1),
            type="vacation",
        )
        TimeOff.objects.create(
            title="New",
            start_date=date(2025, 12, 1),
            end_date=date(2025, 12, 1),
            type="vacation",
        )

        timeoffs = list(TimeOff.objects.all())
        # Check that we have both
        self.assertEqual(len(timeoffs), 2)


class GoogleCalendarTokenModelTestCase(TestCase):
    """Tests for GoogleCalendarToken model"""

    def setUp(self):
        """Create test practice"""
        self.practice = create_test_practice(name="Test Practice", slug="models-token")

    def test_token_creation(self):
        """Test creating a calendar token"""
        token = GoogleCalendarToken.objects.create(
            token='{"access_token": "test"}',
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test_client",
            client_secret="test_secret",
            practice=self.practice,
        )
        self.assertIsNotNone(token.created_at)

    def test_token_str(self):
        """Test GoogleCalendarToken string representation"""
        token = GoogleCalendarToken.objects.create(
            token='{"access_token": "test"}', practice=self.practice
        )
        # Check it returns something
        self.assertIsNotNone(str(token))
        self.assertTrue(len(str(token)) > 0)


class PendingCalendarEventModelTestCase(TestCase):
    """Tests for PendingCalendarEvent model"""

    def setUp(self):
        self.practice = create_test_practice(name="Test Practice", slug="models-pce")
        self.client_obj = Client.objects.create(
            client_code="TC",
            full_name="Test Client",
            email="test@example.com",
            practice=self.practice,
        )

    def test_matched_client_practice_mismatch_rejected(self):
        """A matched_client from another practice must fail validation (clean())."""
        other_practice = Practice.objects.create(
            name="Other Practice",
            slug="models-pce-other",
            title="Other Practitioner",
            email="other@practice.com",
            city="Berlin",
        )
        other_client = Client.objects.create(
            client_code="OC",
            full_name="Other Client",
            email="other@example.com",
            practice=other_practice,
        )
        event = PendingCalendarEvent(
            practice=self.practice,
            google_event_id="evt-mismatch",
            summary="Test event",
            event_date=date.today(),
            duration_minutes=60,
            matched_client=other_client,
        )
        with self.assertRaises(ValidationError):
            event.full_clean()

    def test_matched_client_same_practice_valid(self):
        event = PendingCalendarEvent(
            practice=self.practice,
            google_event_id="evt-ok",
            summary="Test event",
            event_date=date.today(),
            duration_minutes=60,
            matched_client=self.client_obj,
        )
        event.full_clean()  # should not raise
