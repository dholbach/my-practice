"""
Calendar pre-flight checker for invoice detail view (P-013).

Compares invoice items against PendingCalendarEvent records for the same
client and billing period, using fuzzy matching to detect moved or cancelled sessions.
"""

from datetime import timedelta

from ..models import PendingCalendarEvent


class CalendarPreflightChecker:
    """
    Cross-reference invoice items against calendar events to surface discrepancies.

    For each InvoiceItem the result status can be:
    - 'confirmed'  : matching calendar event found on the same date
    - 'moved'      : calendar event found within TOLERANCE_DAYS but on a different date
    - 'cancelled'  : calendar event exists but was cancelled in Google Calendar
    - 'unmatched'  : no calendar event found at all (session may not have been imported yet)

    'unaccounted_events' are calendar events that fall within the invoice period
    but have no corresponding invoice item, i.e., potentially billable sessions
    that were missed.
    """

    TOLERANCE_DAYS = 2
    TOLERANCE_MINUTES = 5

    def __init__(self, invoice):
        self.invoice = invoice

    def has_calendar_events(self) -> bool:
        """Return True if any calendar events exist for the invoice's client/practice."""
        return PendingCalendarEvent.objects.filter(
            practice=self.invoice.practice,
            matched_client=self.invoice.client,
        ).exists()

    def check(self) -> dict:
        """
        Run the pre-flight check.

        Returns:
            dict with keys:
                - item_results: list of per-item result dicts
                - unaccounted_events: calendar events in the billing period not on the invoice
                - has_warnings: True if any anomaly was found
        """
        items = list(self.invoice.items.select_related("service_type", "session").all())
        if not items:
            return {
                "item_results": [],
                "unaccounted_events": [],
                "has_warnings": False,
            }

        # Expand the date window by tolerance on both sides
        session_dates = [i.session.session_date for i in items if i.session_id]
        if not session_dates:
            return {
                "item_results": [],
                "unaccounted_events": [],
                "has_warnings": False,
            }

        window_start = min(session_dates) - timedelta(days=self.TOLERANCE_DAYS)
        window_end = max(session_dates) + timedelta(days=self.TOLERANCE_DAYS)

        calendar_events = list(
            PendingCalendarEvent.objects.filter(
                practice=self.invoice.practice,
                matched_client=self.invoice.client,
                event_date__range=(window_start, window_end),
            )
            .exclude(status=PendingCalendarEvent.Status.SKIPPED)
            .order_by("event_date")
        )

        # Build session → linked PCE mapping to avoid N+1 queries in _match_item.
        # The direct link (PendingCalendarEvent.session) is the authoritative source
        # for sessions that were auto-created from a calendar event.
        session_ids = [i.session_id for i in items if i.session_id]
        linked_pce_map: dict[int, PendingCalendarEvent] = {
            pce.session_id: pce
            for pce in PendingCalendarEvent.objects.filter(session_id__in=session_ids)
        }

        item_results = []
        matched_event_ids = set()

        for item in items:
            result = self._match_item(item, calendar_events, linked_pce_map)
            item_results.append(result)
            if result.get("calendar_event"):
                matched_event_ids.add(result["calendar_event"].pk)

        # Unaccounted: pending events in the window that didn't match any item
        unaccounted = [
            e
            for e in calendar_events
            if e.pk not in matched_event_ids
            and e.status == PendingCalendarEvent.Status.PENDING
            and window_start <= e.event_date <= window_end
        ]

        has_warnings = any(
            r["status"] in ("cancelled", "moved", "unmatched") for r in item_results
        ) or bool(unaccounted)

        return {
            "item_results": item_results,
            "unaccounted_events": unaccounted,
            "has_warnings": has_warnings,
        }

    def _match_item(self, item, calendar_events: list, linked_pce_map: dict) -> dict:
        """
        Find the best-matching calendar event for a single invoice item.

        Matching logic (in priority order):
        1. Direct link (session.pending_calendar_event) → confirmed, regardless of
           the PCE's own status.  A directly-linked PCE that is CANCELLED usually
           means Google cancelled the original recurring-event slot and issued a new
           event ID for the replacement — the session itself still happened.
        2. Same date, not cancelled → confirmed
        3. Within TOLERANCE_DAYS, not cancelled → moved (suggest new date)
        4. Same date, cancelled, AND the cancelled event is linked to this session
           → cancelled (the event that auto-created this session was later cancelled)
        5. No useful match → unmatched
        """
        if not item.session_id:
            return {
                "item": item,
                "status": "unmatched",
                "calendar_event": None,
                "suggested_date": None,
            }

        # Priority 1: trust the explicit session → PCE link over date-based heuristics.
        linked_pce = linked_pce_map.get(item.session_id)
        if linked_pce is not None:
            return {
                "item": item,
                "status": "confirmed",
                "calendar_event": linked_pce,
                "suggested_date": None,
            }

        item_session_date = item.session.session_date
        item_duration = item.session.duration

        exact_match = None
        exact_cancelled = None
        near_match = None

        for event in calendar_events:
            # Duration filter: skip if event duration differs too much
            if item_duration and event.duration_minutes:
                if abs(event.duration_minutes - item_duration) > self.TOLERANCE_MINUTES:
                    continue

            delta = abs((event.event_date - item_session_date).days)

            if delta == 0:
                if event.status == PendingCalendarEvent.Status.CANCELLED:
                    if exact_cancelled is None:
                        exact_cancelled = event
                else:
                    exact_match = event
                    break  # Best possible match
            elif delta <= self.TOLERANCE_DAYS and near_match is None:
                if event.status != PendingCalendarEvent.Status.CANCELLED:
                    near_match = event

        if exact_match:
            return {
                "item": item,
                "status": "confirmed",
                "calendar_event": exact_match,
                "suggested_date": None,
            }
        elif near_match:
            return {
                "item": item,
                "status": "moved",
                "calendar_event": near_match,
                "suggested_date": near_match.event_date,
            }
        elif exact_cancelled:
            # Only report cancelled when the cancelled event is explicitly linked to
            # this session.  An unrelated cancelled event at the same date (session_id
            # is None or belongs to a different session) is not reliable evidence that
            # *this* appointment was cancelled.
            if exact_cancelled.session_id == item.session_id:
                return {
                    "item": item,
                    "status": "cancelled",
                    "calendar_event": exact_cancelled,
                    "suggested_date": None,
                }

        return {
            "item": item,
            "status": "unmatched",
            "calendar_event": None,
            "suggested_date": None,
        }
