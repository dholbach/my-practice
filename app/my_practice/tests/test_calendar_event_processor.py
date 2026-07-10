"""
Tests for CalendarImportProcessor and its module-level helpers (P-013):
event fetching/pagination, duplicate detection, and session-cache
serialization/rehydration for the manual calendar import workflow.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils import timezone

from ..models import Client, Invoice, InvoiceItem, Practice, ServiceType, Session, UserPractice
from ..utils.calendar_event_processor import (
    CalendarImportProcessor,
    _ensure_aware,
    build_user_overrides,
    parse_date_range,
)


def _fake_request(user, practice):
    factory = RequestFactory()
    request = factory.get("/calendar/import/")
    request.user = user
    request.current_practice = practice
    request.session = {}
    return request


class CalendarImportProcessorTestBase(TestCase):
    def setUp(self):
        self.practice = Practice.objects.create(
            name="Test Practice",
            slug="calendar-import-processor",
            title="Test Practitioner",
            email="test@practice.com",
            city="Berlin",
        )
        self.user = User.objects.create_user(username="calimportuser", password="testpass123")
        UserPractice.objects.create(user=self.user, practice=self.practice, is_owner=True)
        self.request = _fake_request(self.user, self.practice)
        self.processor = CalendarImportProcessor(self.request)

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


class PaginateAndFetchTest(CalendarImportProcessorTestBase):
    def test_paginate_follows_next_page_token(self):
        page1 = {"items": [{"id": "e1"}], "nextPageToken": "tok2"}
        page2 = {"items": [{"id": "e2"}]}
        service = MagicMock()
        service.events.return_value.list.return_value.execute.side_effect = [page1, page2]

        events = self.processor._paginate(
            service, "cal-1", timezone.now(), timezone.now() + timedelta(days=1)
        )

        self.assertEqual([e["id"] for e in events], ["e1", "e2"])
        self.assertEqual(service.events.return_value.list.call_count, 2)

    def test_paginate_stops_without_next_page_token(self):
        page1 = {"items": [{"id": "e1"}]}
        service = MagicMock()
        service.events.return_value.list.return_value.execute.return_value = page1

        events = self.processor._paginate(
            service, "cal-1", timezone.now(), timezone.now() + timedelta(days=1)
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(service.events.return_value.list.call_count, 1)

    def test_fetch_and_parse_returns_parsed_events(self):
        raw_event = {
            "id": "evt-1",
            "summary": f"{self.test_client.client_code} Therapiesitzung",
            "start": {"dateTime": "2026-03-01T10:00:00+01:00"},
            "end": {"dateTime": "2026-03-01T11:00:00+01:00"},
        }
        service = MagicMock()
        service.events.return_value.list.return_value.execute.return_value = {"items": [raw_event]}

        parsed = self.processor.fetch_and_parse(
            service, "cal-1", timezone.now(), timezone.now() + timedelta(days=1)
        )

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["id"], "evt-1")
        self.assertEqual(parsed[0]["matched_client"], self.test_client)


class MarkDuplicatesTest(CalendarImportProcessorTestBase):
    def _event(self, **overrides):
        base = {
            "id": "evt-1",
            "matched_client": self.test_client,
            "start": timezone.make_aware(timezone.datetime(2026, 3, 1, 10, 0)),
            "suggested_service_type_obj": self.service_type,
            "duration_minutes": 60,
        }
        base.update(overrides)
        return base

    def test_marks_already_imported(self):
        from ..models import PendingCalendarEvent

        PendingCalendarEvent.objects.create(
            practice=self.practice,
            google_event_id="evt-1",
            summary="Termin",
            event_date=date(2026, 3, 1),
            duration_minutes=60,
            status=PendingCalendarEvent.Status.IMPORTED,
        )
        events = [self._event()]
        self.processor.mark_duplicates(events)
        self.assertTrue(events[0]["already_imported"])

    def test_not_already_imported_when_no_matching_record(self):
        events = [self._event()]
        self.processor.mark_duplicates(events)
        self.assertFalse(events[0]["already_imported"])

    def test_is_duplicate_true_when_matching_invoice_item_exists(self):
        invoice = Invoice.objects.create(
            client=self.test_client,
            invoice_number="TC-1",
            invoice_date=date(2026, 3, 1),
            total=Decimal("90.00"),
            practice=self.practice,
        )
        session = Session.objects.create(
            client=self.test_client, session_date=date(2026, 3, 1), duration=60
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_type=self.service_type,
            session=session,
            rate=Decimal("90.00"),
            quantity=Decimal("1.00"),
            total=Decimal("90.00"),
        )
        events = [self._event()]
        self.processor.mark_duplicates(events)
        self.assertTrue(events[0]["is_duplicate"])
        self.assertEqual(events[0]["duplicate_info"]["invoice_id"], invoice.pk)
        self.assertEqual(events[0]["duplicate_info"]["stored_duration"], 60)

    def test_is_duplicate_false_when_no_matching_invoice_item(self):
        events = [self._event()]
        self.processor.mark_duplicates(events)
        self.assertFalse(events[0]["is_duplicate"])

    def test_is_duplicate_false_without_matched_client(self):
        events = [self._event(matched_client=None)]
        self.processor.mark_duplicates(events)
        self.assertFalse(events[0]["is_duplicate"])

    def test_is_duplicate_false_without_service_type(self):
        events = [self._event(suggested_service_type_obj=None)]
        self.processor.mark_duplicates(events)
        self.assertFalse(events[0]["is_duplicate"])


class CacheRoundTripTest(CalendarImportProcessorTestBase):
    def _parsed_event(self):
        return {
            "id": "evt-1",
            "summary": "Termin",
            "start": timezone.make_aware(timezone.datetime(2026, 3, 1, 10, 0)),
            "end": timezone.make_aware(timezone.datetime(2026, 3, 1, 11, 0)),
            "duration_minutes": 60,
            "matched_client": self.test_client,
            "is_cancelled": False,
            "suggested_service_type_obj": self.service_type,
        }

    def test_build_cache_serializes_events(self):
        cache = self.processor.build_cache(
            [self._parsed_event()], timezone.now(), timezone.now() + timedelta(days=1)
        )
        self.assertEqual(len(cache["events"]), 1)
        cached_event = cache["events"][0]
        self.assertEqual(cached_event["matched_client_id"], self.test_client.id)
        self.assertEqual(cached_event["service_type_id"], self.service_type.id)

    def test_build_cache_handles_none_client_and_service_type(self):
        event = self._parsed_event()
        event["matched_client"] = None
        event["suggested_service_type_obj"] = None
        cache = self.processor.build_cache([event], timezone.now(), timezone.now())
        self.assertIsNone(cache["events"][0]["matched_client_id"])
        self.assertIsNone(cache["events"][0]["service_type_id"])

    def test_rehydrate_from_cache_round_trips(self):
        cache = self.processor.build_cache(
            [self._parsed_event()], timezone.now(), timezone.now() + timedelta(days=1)
        )
        rehydrated = self.processor.rehydrate_from_cache(cache, {"evt-1"})
        self.assertEqual(len(rehydrated), 1)
        self.assertEqual(rehydrated[0]["matched_client"], self.test_client)
        self.assertEqual(rehydrated[0]["suggested_service_type_obj"], self.service_type)

    def test_rehydrate_from_cache_filters_by_event_ids(self):
        cache = self.processor.build_cache([self._parsed_event()], timezone.now(), timezone.now())
        rehydrated = self.processor.rehydrate_from_cache(cache, {"some-other-id"})
        self.assertEqual(rehydrated, [])

    def test_rehydrate_from_cache_returns_none_when_stale(self):
        stale_time = timezone.now() - timedelta(minutes=31)
        cache = {
            "timestamp": stale_time.isoformat(),
            "start_date": timezone.now().isoformat(),
            "end_date": timezone.now().isoformat(),
            "events": [],
        }
        self.assertIsNone(self.processor.rehydrate_from_cache(cache, {"evt-1"}))

    def test_rehydrate_from_cache_within_window_is_not_none(self):
        fresh_time = timezone.now() - timedelta(minutes=5)
        cache = {
            "timestamp": fresh_time.isoformat(),
            "start_date": timezone.now().isoformat(),
            "end_date": timezone.now().isoformat(),
            "events": [],
        }
        self.assertEqual(self.processor.rehydrate_from_cache(cache, {"evt-1"}), [])

    def test_rehydrate_event_handles_none_start_end(self):
        event = self._parsed_event()
        event["start"] = None
        event["end"] = None
        cache = self.processor.build_cache([event], timezone.now(), timezone.now())
        rehydrated = self.processor.rehydrate_from_cache(cache, {"evt-1"})
        self.assertIsNone(rehydrated[0]["start"])
        self.assertIsNone(rehydrated[0]["end"])


class FetchSpecificEventsTest(CalendarImportProcessorTestBase):
    def test_fetches_and_parses_requested_events(self):
        raw_event = {
            "id": "evt-1",
            "summary": "Termin",
            "start": {"dateTime": "2026-03-01T10:00:00+01:00"},
            "end": {"dateTime": "2026-03-01T11:00:00+01:00"},
        }
        service = MagicMock()
        service.events.return_value.get.return_value.execute.return_value = raw_event

        result = self.processor.fetch_specific_events(service, "cal-1", ["evt-1"])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "evt-1")

    def test_skips_events_that_fail_to_fetch(self):
        service = MagicMock()
        service.events.return_value.get.return_value.execute.side_effect = Exception("404")

        result = self.processor.fetch_specific_events(service, "cal-1", ["evt-1", "evt-2"])

        self.assertEqual(result, [])


class EnsureAwareTest(TestCase):
    def test_naive_datetime_becomes_aware(self):
        naive = timezone.datetime(2026, 3, 1, 10, 0)
        result = _ensure_aware(naive)
        self.assertTrue(timezone.is_aware(result))

    def test_aware_datetime_is_unchanged(self):
        aware = timezone.make_aware(timezone.datetime(2026, 3, 1, 10, 0))
        self.assertEqual(_ensure_aware(aware), aware)

    def test_none_returns_none(self):
        self.assertIsNone(_ensure_aware(None))


class ParseDateRangeTest(TestCase):
    def test_defaults_to_last_30_days(self):
        factory = RequestFactory()
        request = factory.get("/calendar/import/")
        start, end = parse_date_range(request)
        self.assertAlmostEqual((end - start).days, 30, delta=1)

    def test_uses_explicit_start_and_end_params(self):
        factory = RequestFactory()
        request = factory.get(
            "/calendar/import/", {"start_date": "2026-01-01", "end_date": "2026-01-15"}
        )
        start, end = parse_date_range(request)
        self.assertEqual(start.date(), date(2026, 1, 1))
        self.assertEqual(end.date(), date(2026, 1, 15))


class BuildUserOverridesTest(TestCase):
    def test_builds_overrides_dict_keyed_by_event_id(self):
        events = [
            {"id": "e1", "action": "import", "client_id": "5", "service_type_id": "2"},
            {"id": "e2", "action": "skip"},
        ]
        overrides = build_user_overrides(events)
        self.assertEqual(
            overrides["e1"], {"action": "import", "client_id": "5", "service_type_id": "2"}
        )
        self.assertEqual(
            overrides["e2"], {"action": "skip", "client_id": None, "service_type_id": None}
        )

    def test_skips_events_without_id(self):
        events = [{"action": "import"}]
        overrides = build_user_overrides(events)
        self.assertEqual(overrides, {})
