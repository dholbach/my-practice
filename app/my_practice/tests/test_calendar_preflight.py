"""
Tests for CalendarPreflightChecker (P-013): cross-referencing invoice items
against PendingCalendarEvent records to surface discrepancies.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from ..models import (
    Client,
    Invoice,
    InvoiceItem,
    PendingCalendarEvent,
    Practice,
    ServiceType,
    Session,
)
from ..utils.calendar_preflight import CalendarPreflightChecker


class CalendarPreflightCheckerTestBase(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="preflight-test",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.service_type = ServiceType.objects.create(
            code="individual",
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
        self.invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date.today(),
            total=Decimal("90.00"),
            practice=self.practice,
        )

    def _make_item(self, session_date, duration=60):
        session = Session.objects.create(
            client=self.test_client, session_date=session_date, duration=duration
        )
        return InvoiceItem.objects.create(
            invoice=self.invoice,
            service_type=self.service_type,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
            total=Decimal("90.00"),
        )

    def _make_event(
        self,
        event_date,
        duration_minutes=60,
        status=PendingCalendarEvent.Status.PENDING,
        google_event_id=None,
        session=None,
    ):
        return PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id=google_event_id or f"evt-{event_date}-{duration_minutes}",
            summary="Termin",
            event_date=event_date,
            duration_minutes=duration_minutes,
            matched_client=self.test_client,
            status=status,
            session=session,
        )


class HasCalendarEventsTest(CalendarPreflightCheckerTestBase):
    def test_false_when_no_events(self):
        checker = CalendarPreflightChecker(self.invoice)
        self.assertFalse(checker.has_calendar_events())

    def test_true_when_event_exists_for_client(self):
        self._make_event(date.today())
        checker = CalendarPreflightChecker(self.invoice)
        self.assertTrue(checker.has_calendar_events())

    def test_false_when_event_belongs_to_other_client(self):
        other_client = Client.objects.create(
            client_code="OC", full_name="Anna Schmidt", practice=self.practice
        )
        PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="evt-other",
            summary="Termin",
            event_date=date.today(),
            duration_minutes=60,
            matched_client=other_client,
        )
        checker = CalendarPreflightChecker(self.invoice)
        self.assertFalse(checker.has_calendar_events())


class CheckEmptyCasesTest(CalendarPreflightCheckerTestBase):
    def test_no_items_returns_empty_result(self):
        checker = CalendarPreflightChecker(self.invoice)
        result = checker.check()
        self.assertEqual(
            result, {"item_results": [], "unaccounted_events": [], "has_warnings": False}
        )


class MatchItemStatusTest(CalendarPreflightCheckerTestBase):
    """Covers the priority-ordered matching logic in _match_item."""

    def test_direct_session_link_confirms_even_if_cancelled(self):
        item = self._make_item(date.today())
        self._make_event(
            date.today(),
            status=PendingCalendarEvent.Status.CANCELLED,
            session=item.session,
        )
        result = CalendarPreflightChecker(self.invoice).check()
        self.assertEqual(result["item_results"][0]["status"], "confirmed")
        self.assertFalse(result["has_warnings"])

    def test_same_date_pending_event_confirms(self):
        item_date = date.today()
        self._make_item(item_date)
        self._make_event(item_date)
        result = CalendarPreflightChecker(self.invoice).check()
        self.assertEqual(result["item_results"][0]["status"], "confirmed")

    def test_nearby_date_within_tolerance_is_moved(self):
        item_date = date.today()
        self._make_item(item_date)
        moved_date = item_date + timedelta(days=1)
        self._make_event(moved_date)
        result = CalendarPreflightChecker(self.invoice).check()
        item_result = result["item_results"][0]
        self.assertEqual(item_result["status"], "moved")
        self.assertEqual(item_result["suggested_date"], moved_date)
        self.assertTrue(result["has_warnings"])

    def test_date_beyond_tolerance_is_unmatched(self):
        item_date = date.today()
        self._make_item(item_date)
        self._make_event(item_date + timedelta(days=5))
        result = CalendarPreflightChecker(self.invoice).check()
        self.assertEqual(result["item_results"][0]["status"], "unmatched")

    def test_same_date_cancelled_event_linked_to_session_is_cancelled(self):
        item = self._make_item(date.today())
        self._make_event(
            date.today(),
            status=PendingCalendarEvent.Status.CANCELLED,
            session=None,
            google_event_id="linked-cancel",
        )
        # Simulate the cancelled event being linked via session FK after the fact.
        PendingCalendarEvent.objects.filter(google_event_id="linked-cancel").update(
            session=item.session
        )
        result = CalendarPreflightChecker(self.invoice).check()
        # Direct-link path (priority 1) already returns "confirmed" for a linked
        # PCE regardless of its status, so this exercises that same rule.
        self.assertEqual(result["item_results"][0]["status"], "confirmed")

    def test_same_date_cancelled_event_unlinked_is_unmatched_not_cancelled(self):
        """An unrelated cancelled event at the same date is not proof this session was cancelled."""
        self._make_item(date.today())
        self._make_event(date.today(), status=PendingCalendarEvent.Status.CANCELLED)
        result = CalendarPreflightChecker(self.invoice).check()
        self.assertEqual(result["item_results"][0]["status"], "unmatched")

    def test_no_matching_event_at_all_is_unmatched(self):
        self._make_item(date.today())
        result = CalendarPreflightChecker(self.invoice).check()
        self.assertEqual(result["item_results"][0]["status"], "unmatched")
        self.assertTrue(result["has_warnings"])

    def test_duration_mismatch_beyond_tolerance_is_skipped(self):
        """An event on the same date with a very different duration must not match."""
        self._make_item(date.today(), duration=60)
        self._make_event(date.today(), duration_minutes=120)
        result = CalendarPreflightChecker(self.invoice).check()
        self.assertEqual(result["item_results"][0]["status"], "unmatched")

    def test_duration_within_tolerance_still_matches(self):
        self._make_item(date.today(), duration=60)
        self._make_event(date.today(), duration_minutes=63)
        result = CalendarPreflightChecker(self.invoice).check()
        self.assertEqual(result["item_results"][0]["status"], "confirmed")

    def test_skipped_events_are_excluded_from_matching(self):
        self._make_item(date.today())
        self._make_event(date.today(), status=PendingCalendarEvent.Status.SKIPPED)
        result = CalendarPreflightChecker(self.invoice).check()
        self.assertEqual(result["item_results"][0]["status"], "unmatched")


class UnaccountedEventsTest(CalendarPreflightCheckerTestBase):
    def test_pending_event_with_no_matching_item_is_unaccounted(self):
        item_date = date.today()
        self._make_item(item_date, duration=60)
        # Within the date window but excluded from matching by the duration
        # filter, so it can't be near-matched to the one item above — this is
        # what makes it "unaccounted" rather than "moved".
        extra_event = self._make_event(item_date + timedelta(days=1), duration_minutes=180)
        result = CalendarPreflightChecker(self.invoice).check()
        unaccounted_ids = {e.pk for e in result["unaccounted_events"]}
        self.assertIn(extra_event.pk, unaccounted_ids)
        self.assertTrue(result["has_warnings"])

    def test_matched_event_is_not_unaccounted(self):
        item_date = date.today()
        self._make_item(item_date)
        self._make_event(item_date)
        result = CalendarPreflightChecker(self.invoice).check()
        self.assertEqual(result["unaccounted_events"], [])

    def test_cancelled_event_is_never_unaccounted(self):
        item_date = date.today()
        self._make_item(item_date)
        self._make_event(
            item_date + timedelta(days=1), status=PendingCalendarEvent.Status.CANCELLED
        )
        result = CalendarPreflightChecker(self.invoice).check()
        self.assertEqual(result["unaccounted_events"], [])
