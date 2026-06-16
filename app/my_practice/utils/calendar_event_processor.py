"""
Business logic for the manual calendar import workflow.

Handles event fetching, pagination, duplicate detection, session-cache
serialization and rehydration — so calendar_views can focus on HTTP.
"""

from datetime import datetime, timedelta

from django.utils import timezone

from ..models import Client, InvoiceItem, PendingCalendarEvent, ServiceType
from .google_calendar import CalendarEventParser


class CalendarImportProcessor:
    """
    Encapsulates the non-HTTP logic for calendar_import and calendar_import_events.

    Usage (fetch path):
        processor = CalendarImportProcessor(request)
        calendar_id = find_calendar_by_name(service, "Praxis")
        events = processor.fetch_and_parse(service, calendar_id, start, end)
        request.session["cached_events"] = processor.build_cache(events, start, end)
        processor.mark_duplicates(events)

    Usage (import path):
        cached = processor.rehydrate_from_cache(cached_data, set(event_ids))
        # or fall back to processor.fetch_specific_events(service, calendar_id, ids)
    """

    def __init__(self, request) -> None:
        self.request = request
        self.practice = request.current_practice

    # ── Fetch path ────────────────────────────────────────────────────────────

    def fetch_and_parse(self, service, calendar_id: str, start_date, end_date) -> list[dict]:
        """Fetch all events from a calendar (paginated) and parse them."""
        raw = self._paginate(service, calendar_id, start_date, end_date)
        return CalendarEventParser.parse_events(raw)

    def _paginate(self, service, calendar_id: str, start_date, end_date) -> list:
        events = []
        page_token = None
        while True:
            result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=start_date.isoformat(),
                    timeMax=end_date.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=250,
                    pageToken=page_token,
                )
                .execute()
            )
            events.extend(result.get("items", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                break
        return events

    # ── Duplicate detection ───────────────────────────────────────────────────

    def mark_duplicates(self, parsed_events: list[dict]) -> None:
        """Set is_duplicate / already_imported flags in-place on each event."""
        imported_ids = set(
            PendingCalendarEvent.objects.filter(
                practice=self.practice,
                status=PendingCalendarEvent.Status.IMPORTED,
            ).values_list("google_event_id", flat=True)
        )
        for event in parsed_events:
            event["already_imported"] = event.get("id") in imported_ids
            event["is_duplicate"] = self._check_duplicate(event)

    def _check_duplicate(self, event: dict) -> bool:
        if not (event.get("matched_client") and event.get("start")):
            return False
        service_type = event.get("suggested_service_type_obj")
        duration = event.get("duration_minutes")
        if not (service_type and duration):
            return False
        qs = InvoiceItem.objects.filter(
            invoice__client=event["matched_client"],
            session__session_date=event["start"].date(),
            service_type=service_type,
            session__duration__gte=duration - 5,
            session__duration__lte=duration + 5,
        )
        if not qs.exists():
            return False
        matched = qs.first()
        if matched:
            event["duplicate_info"] = {
                "invoice_id": matched.invoice_id,
                "stored_duration": matched.session.duration,
                "calendar_duration": duration,
            }
        return True

    # ── Session cache ─────────────────────────────────────────────────────────

    def build_cache(self, parsed_events: list[dict], start_date, end_date) -> dict:
        """Serialize parsed events into a JSON-safe dict for session storage."""
        return {
            "timestamp": timezone.now().isoformat(),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "events": [
                {
                    "id": e.get("id"),
                    "summary": e["summary"],
                    "start": e["start"].isoformat() if e["start"] else None,
                    "end": e["end"].isoformat() if e["end"] else None,
                    "duration_minutes": e["duration_minutes"],
                    "matched_client_id": (
                        e["matched_client"].id if e.get("matched_client") else None
                    ),
                    "is_cancelled": e["is_cancelled"],
                    "service_type_id": (
                        e["suggested_service_type_obj"].id
                        if e.get("suggested_service_type_obj")
                        else None
                    ),
                }
                for e in parsed_events
            ],
        }

    def rehydrate_from_cache(self, cached_data: dict, event_ids: set[str]) -> list[dict] | None:
        """
        Reconstruct full event dicts from session cache.
        Returns None if the cache is older than 30 minutes.
        """
        cache_time = _ensure_aware(datetime.fromisoformat(cached_data["timestamp"]))
        if (timezone.now() - cache_time).total_seconds() >= 1800:
            return None

        return [self._rehydrate_event(e) for e in cached_data["events"] if e["id"] in event_ids]

    def _rehydrate_event(self, cached: dict) -> dict:
        return {
            "id": cached["id"],
            "summary": cached["summary"],
            "start": (
                _ensure_aware(datetime.fromisoformat(cached["start"])) if cached["start"] else None
            ),
            "end": (
                _ensure_aware(datetime.fromisoformat(cached["end"])) if cached["end"] else None
            ),
            "duration_minutes": cached["duration_minutes"],
            "matched_client": (
                Client.objects.for_current_practice(self.request)
                .filter(id=cached["matched_client_id"])
                .first()
                if cached["matched_client_id"]
                else None
            ),
            "is_cancelled": cached["is_cancelled"],
            "suggested_service_type_obj": (
                ServiceType.objects.for_current_practice_with_globals(self.request)
                .filter(id=cached["service_type_id"])
                .first()
                if cached["service_type_id"]
                else None
            ),
        }

    # ── API fallback (import path) ────────────────────────────────────────────

    def fetch_specific_events(self, service, calendar_id: str, event_ids: list[str]) -> list[dict]:
        """Fetch individual events by ID and parse them (used when cache is stale)."""
        fetched = []
        for event_id in event_ids:
            try:
                event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
                fetched.append(event)
            except Exception:
                pass  # Skip events that can't be fetched
        return CalendarEventParser.parse_events(fetched)


def _ensure_aware(dt):
    """Return a timezone-aware datetime, converting naive datetimes if needed."""
    if dt and timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


def parse_date_range(request) -> tuple:
    """Extract start/end dates from request GET params, defaulting to last 30 days."""
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)

    start_param = request.GET.get("start_date")
    if start_param:
        start_date = _ensure_aware(datetime.fromisoformat(start_param))
    end_param = request.GET.get("end_date")
    if end_param:
        end_date = _ensure_aware(datetime.fromisoformat(end_param))

    return start_date, end_date


def build_user_overrides(events_to_process: list[dict]) -> dict:
    """Convert the POST events list to the {event_id: overrides} dict."""
    return {
        e["id"]: {
            "action": e.get("action", "import"),
            "client_id": e.get("client_id"),
            "service_type_id": e.get("service_type_id"),
        }
        for e in events_to_process
        if e.get("id")
    }
