"""
Management command to fetch Google Calendar events into the pending queue (P-013).

Run every few hours via systemd timer. Idempotent: google_event_id unique constraint
prevents duplicates. On each run, also marks previously-fetched events as 'cancelled'
if they no longer appear in Google Calendar — unless the same session simply moved
to a new Google event id, which _supersede_moved_events() re-binds first.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...models import GoogleCalendarToken, PendingCalendarEvent, Session
from ...utils.google_calendar import (
    CalendarEventParser,
    GoogleCalendarOAuth,
)
from ...utils.tag_helpers import sync_no_next_session_tag

logger = logging.getLogger(__name__)

OVERLAP_HOURS = 2  # Re-fetch this many hours of overlap to catch late additions
FIRST_RUN_DAYS = 30  # How far back to go on the very first run per practice


def _format_time(value) -> str:
    """Render an event time for the console; all-day events have none."""
    return value.strftime("%H:%M") if value else "–"


class Command(BaseCommand):
    help = "Fetch calendar events into the pending approval queue (P-013)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be fetched without writing to the database",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Override the fetch window (days back from now)",
        )
        parser.add_argument(
            "--future-days",
            type=int,
            default=1,
            help="How many days into the future to fetch (default: 1)",
        )
        parser.add_argument(
            "--practice-id",
            type=int,
            default=None,
            help="Only fetch for a specific practice",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        forced_days = options["days"]
        future_days = options["future_days"]
        practice_id = options["practice_id"]

        # Find practices with active calendar tokens
        token_qs = GoogleCalendarToken.objects.filter(is_active=True).select_related("practice")
        if practice_id:
            token_qs = token_qs.filter(practice_id=practice_id)

        if not token_qs.exists():
            self.stdout.write(self.style.WARNING("No active calendar tokens found."))
            return

        for token in token_qs:
            practice = token.practice
            if not practice:
                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ Token #{token.id} has no associated practice. "
                        "Please re-authorise the calendar connection."
                    )
                )
                continue
            self.stdout.write(f"\n📅 Practice: {practice.name}")
            self._fetch_for_practice(practice, token.calendar_id, dry_run, forced_days, future_days)

    def _fetch_for_practice(self, practice, calendar_id, dry_run, forced_days, future_days=1):
        service = GoogleCalendarOAuth.get_service(practice=practice)
        if not service:
            self.stdout.write(
                self.style.ERROR(
                    f"  ✗ Calendar token for practice '{practice.name}' is expired or invalid.\n"
                    "    → Re-authorise: ./dev.py calendar-auth "
                    "(or open /calendar/authorize/ in the app).\n"
                    "    ℹ️  Note: Google caps refresh tokens at 7 days while the OAuth consent\n"
                    "       screen's publishing status is 'Testing' — being on the Test users\n"
                    "       list does NOT bypass this. Publish the app to 'In production' in\n"
                    "       the Google Cloud Console (Audience → App veröffentlichen) to remove\n"
                    "       the 7-day cap, then re-run ./dev.py calendar-auth once."
                )
            )
            return

        if not calendar_id:
            self.stdout.write(
                self.style.WARNING(
                    f"  ⚠️  No calendar selected for practice '{practice.name}'. "
                    "Open /calendar/import/ in the app to choose one."
                )
            )
            return

        start_dt, end_dt = self._determine_fetch_window(practice, forced_days, future_days)
        self.stdout.write(
            f"  Window: {start_dt.strftime('%d.%m.%Y')} – {end_dt.strftime('%d.%m.%Y')}"
        )

        try:
            raw_events = self._fetch_raw_events(service, calendar_id, start_dt, end_dt)
        except Exception as e:
            logger.error(f"Error fetching calendar events: {e}")
            self.stdout.write(self.style.ERROR(f"  ✗ API error: {e}"))
            return

        live_ids = {e.get("id") for e in raw_events if e.get("id")}
        parsed = CalendarEventParser.parse_events(raw_events)

        # Clients whose Session rows changed in this run — their
        # no-next-session tag is re-synced at the end instead of waiting
        # for the next update_client_tags timer run.
        affected_clients: set = set()

        # Must run before both passes below: it re-binds rows whose Google id
        # changed, so they are neither cancelled as stale nor re-created as new.
        moved_count = self._supersede_moved_events(
            practice, start_dt, end_dt, parsed, live_ids, dry_run
        )
        cancelled_count, flagged_count = self._cancel_stale_future_events(
            practice, start_dt, end_dt, live_ids, dry_run, affected_clients
        )
        counts = self._upsert_all_events(parsed, practice, dry_run, affected_clients)
        self._report_fetch_summary(dry_run, cancelled_count, flagged_count, moved_count, counts)

        if not dry_run:
            self._sync_no_next_session_tags(affected_clients)

    def _upsert_all_events(
        self, parsed_events: list, practice, dry_run: bool, affected_clients: set
    ) -> dict[str, int]:
        counts = {"created": 0, "skipped": 0, "rescheduled": 0, "reinstated": 0}
        for event in parsed_events:
            result = self._upsert_event(event, practice, dry_run, affected_clients)
            if result in counts:
                counts[result] += 1
        return counts

    def _report_fetch_summary(
        self,
        dry_run: bool,
        cancelled_count: int,
        flagged_count: int,
        moved_count: int,
        counts: dict,
    ) -> None:
        action = "[dry-run] Would create" if dry_run else "Created"
        parts = [
            f"{counts['created']} new",
            f"{cancelled_count} marked as cancelled",
            f"{counts['skipped']} already present",
        ]
        if moved_count:
            parts.append(f"{moved_count} moved to a new calendar entry")
        if flagged_count:
            parts.append(f"{flagged_count} newly missing (cancels next run if still absent)")
        if counts["rescheduled"]:
            parts.append(f"{counts['rescheduled']} rescheduled")
        if counts["reinstated"]:
            parts.append(f"{counts['reinstated']} reinstated")
        self.stdout.write(self.style.SUCCESS(f"  ✅ {action}: {', '.join(parts)}"))

    def _sync_no_next_session_tags(self, clients: set) -> None:
        for client in clients:
            changed = sync_no_next_session_tag(client)
            if changed is True:
                self.stdout.write(
                    self.style.WARNING(f"  🏷  +no-next-session: {client.client_code}")
                )
            elif changed is False:
                self.stdout.write(
                    self.style.SUCCESS(f"  🏷  -no-next-session: {client.client_code}")
                )

    def _determine_fetch_window(self, practice, forced_days, future_days):
        now = timezone.now()
        if forced_days:
            start_dt = now - timedelta(days=forced_days)
        else:
            last_fetch = (
                PendingCalendarEvent.objects.filter(practice=practice)
                .order_by("-fetched_at")
                .values_list("fetched_at", flat=True)
                .first()
            )
            start_dt = (
                last_fetch - timedelta(hours=OVERLAP_HOURS)
                if last_fetch
                else now - timedelta(days=FIRST_RUN_DAYS)
            )
        return start_dt, now + timedelta(days=future_days)

    def _fetch_raw_events(self, service, calendar_id, start_dt, end_dt) -> list:
        raw_events = []
        page_token = None
        while True:
            result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=start_dt.isoformat(),
                    timeMax=end_dt.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=250,
                    pageToken=page_token,
                )
                .execute()
            )
            raw_events.extend(result.get("items", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                break
        return raw_events

    @staticmethod
    def _pending_events_in_window(practice, start_dt, end_dt):
        """Future PENDING rows inside the fetch window — the set both the
        supersede and the cancel pass reason about."""
        return PendingCalendarEvent.objects.filter(
            practice=practice,
            event_date__range=(start_dt.date(), end_dt.date()),
            event_date__gt=timezone.localdate(),
            status=PendingCalendarEvent.Status.PENDING,
        )

    def _supersede_moved_events(
        self, practice, start_dt, end_dt, parsed_events: list, live_ids: set, dry_run: bool
    ) -> int:
        """Re-bind a pending event whose Google id changed but whose session is
        still on the calendar, same client and same day.

        Google mints a *new* event id when a recurring series is edited with
        "this and following events" — and when an event is cut/pasted or
        deleted and recreated. The old id then vanishes from events.list()
        while a new one appears, so without this pass a session that merely
        moved to another time gets cancelled *and* duplicated: the stale row is
        cancelled (along with its Session) and the new id creates a second row
        and Session for the same slot.

        Matching on (client, date) keeps the original row and its Session, so
        anything already linked to them survives the move. The stale row must
        have vanished from live_ids and the replacement must not be known yet,
        so two genuinely separate same-day sessions never collapse into one.

        Returns the number of rows re-bound.
        """
        replacements = self._collect_replacement_candidates(parsed_events, live_ids)
        if not replacements:
            return 0

        moved = 0
        stale = self._pending_events_in_window(practice, start_dt, end_dt).exclude(
            google_event_id__in=live_ids
        )
        for db_event in stale.select_related("matched_client"):
            candidates = replacements.get((db_event.matched_client_id, db_event.event_date))
            if not candidates:
                continue
            # One replacement can only stand in for one stale row
            candidate = candidates.pop(0)
            moved += 1
            if not dry_run:
                self._rebind_to_replacement(db_event, candidate)
            self._report_move(db_event, candidate)
        return moved

    @classmethod
    def _collect_replacement_candidates(cls, parsed_events: list, live_ids: set) -> dict:
        """Group live events that have no PendingCalendarEvent row yet by
        (client_id, date) — the pool a stale row can be re-bound to."""
        known_ids = set(
            PendingCalendarEvent.objects.filter(google_event_id__in=live_ids).values_list(
                "google_event_id", flat=True
            )
        )
        candidates: dict = {}
        for event in parsed_events:
            client = event.get("matched_client")
            if not event.get("id") or not event.get("start") or not client:
                continue
            if event["id"] in known_ids:
                continue
            if cls._resolve_event_status(event) != PendingCalendarEvent.Status.PENDING:
                continue
            event_date, _ = cls._split_event_datetime(event["start"])
            candidates.setdefault((client.pk, event_date), []).append(event)
        return candidates

    @classmethod
    def _rebind_to_replacement(cls, db_event: "PendingCalendarEvent", candidate) -> None:
        """Point an existing row (and its Session) at the replacement event's id
        and start time. The date is the match key, so it cannot have changed."""
        _, event_time = cls._split_event_datetime(candidate["start"])
        new_duration = candidate.get("duration_minutes") or db_event.duration_minutes
        PendingCalendarEvent.objects.filter(pk=db_event.pk).update(
            google_event_id=candidate["id"],
            summary=candidate.get("summary", ""),
            event_time=event_time,
            duration_minutes=new_duration,
            missing_since=None,
        )
        if db_event.session_id:
            Session.objects.filter(pk=db_event.session_id).update(
                session_time=event_time,
                duration=new_duration,
                calendar_event_id=candidate["id"],
            )

    def _report_move(self, db_event: "PendingCalendarEvent", candidate) -> None:
        _, event_time = self._split_event_datetime(candidate["start"])
        code = db_event.matched_client.client_code if db_event.matched_client else "?"
        self.stdout.write(
            self.style.WARNING(
                f"  🔀 Moved: {code} on {db_event.event_date} "
                f"{_format_time(db_event.event_time)} → {_format_time(event_time)} "
                "(new calendar entry)"
            )
        )

    def _cancel_stale_future_events(
        self,
        practice,
        start_dt,
        end_dt,
        live_ids: set,
        dry_run: bool,
        affected_clients: set | None = None,
    ) -> tuple[int, int]:
        """Cancel PENDING events missing from live_ids — but only on the second
        consecutive miss. Google's events.list() can transiently omit an event
        right after it was edited server-side; requiring two misses avoids
        cancelling a still-live session on that kind of blip.

        Returns (cancelled_count, newly_flagged_count).
        """
        cancelled = 0
        flagged = 0
        existing = self._pending_events_in_window(practice, start_dt, end_dt)
        for db_event in existing:
            if db_event.google_event_id in live_ids:
                if db_event.missing_since and not dry_run:
                    db_event.missing_since = None
                    db_event.save(update_fields=["missing_since"])
                continue

            if not db_event.missing_since:
                flagged += 1
                if not dry_run:
                    db_event.missing_since = timezone.now()
                    db_event.save(update_fields=["missing_since"])
                continue

            cancelled += 1
            if not dry_run:
                db_event.status = PendingCalendarEvent.Status.CANCELLED
                db_event.save(update_fields=["status"])
                if db_event.session_id:
                    Session.objects.filter(pk=db_event.session_id).update(cancelled=True)
                    if db_event.matched_client and affected_clients is not None:
                        affected_clients.add(db_event.matched_client)
            code = db_event.matched_client.client_code if db_event.matched_client else "?"
            self.stdout.write(f"  🚫 Cancelled: {code} on {db_event.event_date}")
        return cancelled, flagged

    def _upsert_event(
        self, event, practice, dry_run, affected_clients: set | None = None
    ) -> str | None:
        """Return 'created', 'skipped', 'rescheduled', 'reinstated', or None (invalid/no-id/no-start)."""
        event_id = event.get("id")
        start = event.get("start")
        if not event_id or not start:
            return None

        status = self._resolve_event_status(event)
        event_date, event_time = self._split_event_datetime(start)

        if dry_run:
            self._report_dry_run_event(event, event_date, status)
            return "created"

        obj, was_created = PendingCalendarEvent.objects.get_or_create(
            google_event_id=event_id,
            defaults={
                "practice": practice,
                "summary": event.get("summary", ""),
                "event_date": event_date,
                "event_time": event_time,
                "duration_minutes": event.get("duration_minutes", 0),
                "matched_client": event.get("matched_client"),
                "suggested_service_type": event.get("suggested_service_type_obj"),
                "status": status,
            },
        )
        if was_created:
            session_client = self._auto_create_session(
                event, event_id, event_date, event_time, status
            )
            if session_client and affected_clients is not None:
                affected_clients.add(session_client)
            return "created"

        if status == PendingCalendarEvent.Status.CANCELLED:
            self._transition_to_cancelled(obj, event_id, affected_clients)
            return "skipped"

        if obj.status == PendingCalendarEvent.Status.CANCELLED:
            self._transition_to_reinstated(obj, event, event_date, event_time, affected_clients)
            return "reinstated"

        if self._apply_reschedule_if_changed(obj, event, event_date, event_time, affected_clients):
            return "rescheduled"

        return "skipped"

    @staticmethod
    def _split_event_datetime(start) -> tuple:
        event_date = start.date() if hasattr(start, "date") else start
        event_time = (
            start.time() if hasattr(start, "time") and (start.hour or start.minute) else None
        )
        return event_date, event_time

    def _report_dry_run_event(self, event, event_date, status) -> None:
        code = event["matched_client"].client_code if event.get("matched_client") else "?"
        self.stdout.write(
            f"  [dry-run] {code} am {event_date} "
            f"({event.get('duration_minutes')} min) status={status}"
        )

    @staticmethod
    def _transition_to_cancelled(
        obj: "PendingCalendarEvent", event_id: str, affected_clients: set | None
    ) -> None:
        PendingCalendarEvent.objects.filter(
            google_event_id=event_id,
            status=PendingCalendarEvent.Status.PENDING,
        ).update(status=PendingCalendarEvent.Status.CANCELLED)
        if obj.session_id:
            Session.objects.filter(pk=obj.session_id).update(cancelled=True)
            if obj.matched_client and affected_clients is not None:
                affected_clients.add(obj.matched_client)

    def _transition_to_reinstated(
        self,
        obj: "PendingCalendarEvent",
        event,
        event_date,
        event_time,
        affected_clients: set | None,
    ) -> None:
        """Reinstate a previously-cancelled event (e.g. un-cancelled in Google Calendar).

        Also refreshes event_date/event_time/duration_minutes and clears
        missing_since — the cancelled row can be stale on a moved event, and a
        stale missing_since would let the two-miss cancel debounce fire on the
        very next run even though nothing actually changed.
        """
        new_duration = event.get("duration_minutes") or obj.duration_minutes
        PendingCalendarEvent.objects.filter(pk=obj.pk).update(
            status=PendingCalendarEvent.Status.PENDING,
            event_date=event_date,
            event_time=event_time,
            duration_minutes=new_duration,
            missing_since=None,
        )
        if obj.session_id:
            Session.objects.filter(pk=obj.session_id).update(
                cancelled=False,
                session_date=event_date,
                session_time=event_time,
                duration=new_duration,
            )
            if obj.matched_client and affected_clients is not None:
                affected_clients.add(obj.matched_client)
        code = event.get("matched_client")
        code = code.client_code if code else "?"
        self.stdout.write(self.style.SUCCESS(f"  ✅ Reinstated: {code} on {event_date}"))

    def _apply_reschedule_if_changed(
        self,
        obj: "PendingCalendarEvent",
        event,
        event_date,
        event_time,
        affected_clients: set | None,
    ) -> bool:
        """Detect a rescheduled or updated event (date, time or duration
        changed), apply the change, and report it. Returns True if anything
        changed.

        The time is compared separately from the date: an event dragged to a
        new time on the *same* day keeps both its Google id and its date, so
        without that comparison the move is silently dropped and the stored
        session time stays wrong forever.
        """
        new_duration = event.get("duration_minutes", 0)
        changes = {
            "date": obj.event_date != event_date,
            "time": obj.event_time != event_time,
            "duration": bool(new_duration and obj.duration_minutes != new_duration),
        }

        if not any(changes.values()):
            return False

        self._apply_reschedule_updates(obj, event_date, event_time, new_duration, changes)
        self._propagate_reschedule_to_session(
            obj, event_date, event_time, new_duration, changes, affected_clients
        )
        self._report_reschedule(obj, event, event_date, event_time, new_duration, changes)
        return True

    @staticmethod
    def _apply_reschedule_updates(
        obj: "PendingCalendarEvent",
        event_date,
        event_time,
        new_duration,
        changes: dict,
    ) -> None:
        updates: dict = {}
        if changes["date"]:
            updates["event_date"] = event_date
        if changes["time"]:
            updates["event_time"] = event_time
        if changes["duration"]:
            updates["duration_minutes"] = new_duration
        if obj.status == PendingCalendarEvent.Status.IMPORTED and obj.session is None:
            updates["status"] = PendingCalendarEvent.Status.PENDING
        PendingCalendarEvent.objects.filter(pk=obj.pk).update(**updates)

    @staticmethod
    def _propagate_reschedule_to_session(
        obj: "PendingCalendarEvent",
        event_date,
        event_time,
        new_duration,
        changes: dict,
        affected_clients: set | None,
    ) -> None:
        if not obj.session_id:
            return
        session_updates: dict = {}
        if changes["duration"]:
            session_updates["duration"] = new_duration
        if changes["time"]:
            session_updates["session_time"] = event_time
        if changes["date"]:
            session_updates["session_date"] = event_date
            # A date change can move the session across the
            # past/future boundary the tag depends on
            if obj.matched_client and affected_clients is not None:
                affected_clients.add(obj.matched_client)
        if session_updates:
            Session.objects.filter(pk=obj.session_id).update(**session_updates)

    def _report_reschedule(
        self,
        obj: "PendingCalendarEvent",
        event,
        event_date,
        event_time,
        new_duration,
        changes: dict,
    ) -> None:
        code = event.get("matched_client")
        code = code.client_code if code else "?"
        if changes["date"]:
            self.stdout.write(
                self.style.WARNING(
                    f"  📅 Rescheduled: {code} moved from {obj.event_date} → {event_date}"
                )
            )
        elif changes["time"]:
            self.stdout.write(
                self.style.WARNING(
                    f"  🕑 Time changed: {code} on {event_date} "
                    f"{_format_time(obj.event_time)} → {_format_time(event_time)}"
                )
            )
        if changes["duration"]:
            self.stdout.write(
                self.style.WARNING(
                    f"  ⏱ Duration updated: {code} on {event_date} "
                    f"{obj.duration_minutes} → {new_duration} min"
                )
            )

    @staticmethod
    def _resolve_event_status(event) -> str:
        if event.get("is_cancelled"):
            return PendingCalendarEvent.Status.CANCELLED
        stype = event.get("suggested_service_type_obj")
        if stype and stype.code == "therapy_free":
            return PendingCalendarEvent.Status.SKIPPED
        return PendingCalendarEvent.Status.PENDING

    def _auto_create_session(self, event, event_id, event_date, event_time, status):
        """Create a Session for a matched event; return its client (or None)."""
        matched_client = event.get("matched_client")
        if not matched_client:
            return None
        if status not in (
            PendingCalendarEvent.Status.PENDING,
            PendingCalendarEvent.Status.SKIPPED,
        ):
            return None
        session, _ = Session.objects.get_or_create(
            client=matched_client,
            session_date=event_date,
            session_time=event_time,
            defaults={
                "duration": event.get("duration_minutes", 60),
                "calendar_event_id": event_id,
            },
        )
        if not PendingCalendarEvent.objects.filter(session=session).exists():
            PendingCalendarEvent.objects.filter(google_event_id=event_id).update(session=session)
        return matched_client
