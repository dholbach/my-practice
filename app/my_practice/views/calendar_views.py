"""
Google Calendar integration views for session import.
Includes OAuth2 flow and event approval/import functionality.
"""

import json
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, Exists, OuterRef
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import Client, Invoice, InvoiceItem, PendingCalendarEvent, ServiceType
from ..utils.billing_helpers import resolve_session_rate
from ..utils.calendar_event_processor import (
    CalendarImportProcessor,
    build_user_overrides,
    parse_date_range,
)
from ..utils.google_calendar import (
    GoogleCalendarOAuth,
    find_calendar_by_name,
)


def calendar_authorize(request: HttpRequest) -> HttpResponse:
    """
    Initiate OAuth2 flow to authorize Google Calendar access.
    """
    redirect_uri = request.build_absolute_uri(reverse("calendar_oauth2callback"))
    flow = GoogleCalendarOAuth.create_flow(redirect_uri)

    # Generate authorization URL with PKCE (required by Google)
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # Force consent to get refresh token
        code_challenge_method="S256",
    )

    # Store state and PKCE verifier in session
    request.session["oauth_state"] = state
    request.session["oauth_code_verifier"] = flow.code_verifier

    return redirect(authorization_url)


def calendar_oauth2callback(request: HttpRequest) -> HttpResponse:
    """
    Handle OAuth2 callback from Google.
    Store tokens in database.
    """
    # Verify state to prevent CSRF
    state = request.session.get("oauth_state")
    if not state or state != request.GET.get("state"):
        messages.error(request, "OAuth state mismatch. Please try again.")
        return redirect("dashboard")

    # Create flow and exchange code for tokens
    redirect_uri = request.build_absolute_uri(reverse("calendar_oauth2callback"))
    flow = GoogleCalendarOAuth.create_flow(redirect_uri)
    flow.state = state
    flow.code_verifier = request.session.pop("oauth_code_verifier", None)

    try:
        flow.fetch_token(code=request.GET.get("code"))
        practice = getattr(request, "current_practice", None)
        GoogleCalendarOAuth.save_token(flow.credentials, practice=practice)

        messages.success(request, _("✅ Google Calendar connected successfully!"))
        return redirect("calendar_import")

    except Exception as e:
        messages.error(request, _("Authorization error: %(error)s") % {"error": str(e)})
        return redirect("dashboard")


def calendar_import(request: HttpRequest) -> HttpResponse:
    """Show calendar import interface — list events from Google Calendar and allow import."""
    service = GoogleCalendarOAuth.get_service()
    if not service:
        messages.warning(request, _("Please connect your Google Calendar first."))
        return render(request, "my_practice/calendar_connect.html")

    start_date, end_date = parse_date_range(request)

    try:
        praxis_calendar_id = find_calendar_by_name(service, "Praxis")
        if not praxis_calendar_id:
            messages.warning(request, _("No calendar named 'Praxis' found."))
            return render(
                request,
                "my_practice/calendar_import.html",
                {"events": [], "start_date": start_date, "end_date": end_date, "total_events": 0},
            )

        processor = CalendarImportProcessor(request)
        parsed_events = processor.fetch_and_parse(service, praxis_calendar_id, start_date, end_date)
        request.session["cached_events"] = processor.build_cache(
            parsed_events, start_date, end_date
        )
        processor.mark_duplicates(parsed_events)

        already_imported_count = sum(1 for e in parsed_events if e.get("already_imported"))
        parsed_events = [e for e in parsed_events if not e.get("already_imported")]

        clients = (
            Client.objects.for_current_practice(request)
            .only("id", "client_code", "full_name")
            .order_by("full_name")
        )
        service_types = (
            ServiceType.objects.for_current_practice_with_globals(request).all().order_by("code")
        )

        context = {
            "events": parsed_events,
            "clients": clients,
            "service_types": service_types,
            "start_date": start_date,
            "end_date": end_date,
            "total_events": len(parsed_events),
            "ready_count": sum(
                1
                for e in parsed_events
                if e["matched_client"] and not e["is_cancelled"] and not e.get("is_duplicate")
            ),
            "duplicate_count": sum(1 for e in parsed_events if e.get("is_duplicate")),
            "cancelled_count": sum(1 for e in parsed_events if e["is_cancelled"]),
            "unknown_count": sum(
                1
                for e in parsed_events
                if not e["matched_client"] and not e["is_cancelled"] and not e.get("is_duplicate")
            ),
            "already_imported_count": already_imported_count,
        }
        return render(request, "my_practice/calendar_import.html", context)

    except Exception as e:
        messages.error(request, _("Error loading calendar events: %(error)s") % {"error": str(e)})
        return redirect("dashboard")


@require_POST
def calendar_import_events(request: HttpRequest) -> JsonResponse:
    """
    Bulk-import selected calendar events as InvoiceItems.
    Uses session-cached event data when fresh; falls back to Google API.
    """
    try:
        data = json.loads(request.body)
        events_to_process = data.get("events", [])
        if not events_to_process:
            return JsonResponse({"success": False, "error": _("No events selected")}, status=400)

        user_overrides = build_user_overrides(events_to_process)
        processor = CalendarImportProcessor(request)
        event_ids = {e.get("id") for e in events_to_process}

        parsed_events = None
        cached_data = request.session.get("cached_events")
        if cached_data:
            parsed_events = processor.rehydrate_from_cache(cached_data, event_ids)

        if not parsed_events:
            service = GoogleCalendarOAuth.get_service()
            if not service:
                return JsonResponse(
                    {"success": False, "error": _("Google Calendar not connected")}, status=401
                )
            praxis_calendar_id = find_calendar_by_name(service, "Praxis")
            if not praxis_calendar_id:
                return JsonResponse(
                    {"success": False, "error": _("Calendar 'Praxis' not found")}, status=404
                )
            try:
                parsed_events = processor.fetch_specific_events(
                    service, praxis_calendar_id, list(event_ids)
                )
            except Exception as e:
                return JsonResponse(
                    {
                        "success": False,
                        "error": _("Error loading events: %(error)s") % {"error": str(e)},
                    },
                    status=500,
                )

        from ..utils.calendar_import_helpers import create_invoice_items_from_events

        created, skipped, errors = create_invoice_items_from_events(
            approved_events=parsed_events, user_overrides=user_overrides, request=request
        )
        return JsonResponse(
            {"success": True, "created": created, "skipped": skipped, "errors": errors}
        )

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ---------------------------------------------------------------------------
# P-013: Calendar Approval Queue
# ---------------------------------------------------------------------------


def calendar_approval_queue(request: HttpRequest) -> HttpResponse:
    """
    Show all pending calendar events grouped by client and billing month.

    Events are grouped so the practitioner can review them client-by-client
    and month-by-month before turning them into invoice items.
    """
    from itertools import groupby

    practice = getattr(request, "current_practice", None)
    if not practice:
        messages.error(request, _("No active practice found."))
        return redirect("dashboard")

    # Subquery: does an InvoiceItem already exist for this client/date/duration?
    duplicate_subquery = InvoiceItem.objects.filter(
        invoice__client=OuterRef("matched_client"),
        session__session_date=OuterRef("event_date"),
        session__duration__gte=OuterRef("duration_minutes") - 5,
        session__duration__lte=OuterRef("duration_minutes") + 5,
    )

    # Stale count: already-billed events still sitting as pending (shown separately, not in list)
    stale_count = (
        PendingCalendarEvent.objects.filter(
            practice=practice,
            status=PendingCalendarEvent.Status.PENDING,
        )
        .annotate(is_duplicate=Exists(duplicate_subquery))
        .filter(is_duplicate=True)
        .count()
    )

    pending_events = (
        PendingCalendarEvent.objects.filter(
            practice=practice,
            status=PendingCalendarEvent.Status.PENDING,
        )
        .select_related("matched_client", "suggested_service_type")
        .exclude(Exists(duplicate_subquery))
        .order_by("matched_client__client_code", "event_date")
    )

    # Group by (matched_client, billing_month)
    grouped = []
    for (client, month), events_iter in groupby(
        pending_events,
        key=lambda e: (e.matched_client, e.billing_month),
    ):
        events = list(events_iter)
        grouped.append(
            {
                "client": client,
                "month": month,
                "events": events,
                "count": len(events),
            }
        )

    # Build a client → list[invoice] map for draft invoices with item count + total.
    # This avoids N+1 queries and lets the template show useful info in the dropdown.
    client_ids = [g["client"].pk for g in grouped if g["client"] is not None]
    draft_invoices = (
        Invoice.objects.filter(client_id__in=client_ids, status="draft")
        .annotate(item_count=Count("items"))
        .order_by("-invoice_date")
    )
    draft_invoice_map: dict[int, list] = {}
    for inv in draft_invoices:
        draft_invoice_map.setdefault(inv.client_id, []).append(inv)

    for group in grouped:
        group["invoices"] = draft_invoice_map.get(group["client"].pk, []) if group["client"] else []

    total_pending = pending_events.count()

    return render(
        request,
        "my_practice/calendar_approval_queue.html",
        {
            "grouped": grouped,
            "total_pending": total_pending,
            "stale_count": stale_count,
        },
    )


@require_POST
def calendar_queue_import(request: HttpRequest) -> JsonResponse:
    """
    Import selected pending calendar events as invoice items (P-013).

    Expects JSON: {"event_ids": [1, 2, 3], "invoice_id": 42}
    If invoice_id is omitted, events are marked as pending for manual assignment.

    Returns JSON with counts of created/skipped/errors.
    """
    try:
        data = json.loads(request.body)
        event_ids = data.get("event_ids", [])
        invoice_id = data.get("invoice_id")

        if not event_ids:
            return JsonResponse({"success": False, "error": _("No events selected.")}, status=400)

        practice = getattr(request, "current_practice", None)
        events = PendingCalendarEvent.objects.filter(
            pk__in=event_ids,
            practice=practice,
            status=PendingCalendarEvent.Status.PENDING,
        ).select_related("matched_client", "suggested_service_type")

        from ..utils.calendar_import_helpers import create_invoice_items_from_events

        # Convert PendingCalendarEvent objects to the format expected by the importer
        parsed_events = [
            {
                "id": ev.google_event_id,
                "summary": ev.summary,
                "start": (
                    datetime.combine(ev.event_date, ev.event_time) if ev.event_time else None
                ),
                "duration_minutes": ev.duration_minutes,
                "matched_client": ev.matched_client,
                "suggested_service_type_obj": ev.suggested_service_type,
            }
            for ev in events
        ]

        user_overrides = {}
        if invoice_id:
            # All events go onto the same invoice
            for ev in events:
                user_overrides[ev.google_event_id] = {"invoice_id": invoice_id}

        created, skipped, errors = create_invoice_items_from_events(
            approved_events=parsed_events,
            user_overrides=user_overrides,
            request=request,
        )

        # Mark imported events
        events.update(status=PendingCalendarEvent.Status.IMPORTED)

        return JsonResponse(
            {"success": True, "created": created, "skipped": skipped, "errors": errors}
        )

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_POST
def calendar_queue_skip_duplicates(request: HttpRequest) -> JsonResponse:
    """
    Mark all pending events that already have a matching InvoiceItem as skipped.

    A match is: same client, same date, duration within ±5 min.
    """
    practice = getattr(request, "current_practice", None)

    duplicate_subquery = InvoiceItem.objects.filter(
        invoice__client=OuterRef("matched_client"),
        session__session_date=OuterRef("event_date"),
        session__duration__gte=OuterRef("duration_minutes") - 5,
        session__duration__lte=OuterRef("duration_minutes") + 5,
    )

    duplicates = (
        PendingCalendarEvent.objects.filter(
            practice=practice,
            status=PendingCalendarEvent.Status.PENDING,
        )
        .annotate(is_duplicate=Exists(duplicate_subquery))
        .filter(is_duplicate=True)
    )

    count = duplicates.count()
    duplicates.update(status=PendingCalendarEvent.Status.SKIPPED)

    return JsonResponse({"success": True, "skipped": count})


@require_POST
def calendar_queue_skip(request: HttpRequest, pk: int) -> JsonResponse:
    """Mark a single pending calendar event as skipped (P-013)."""
    practice = getattr(request, "current_practice", None)
    try:
        event = PendingCalendarEvent.objects.get(
            pk=pk,
            practice=practice,
            status=PendingCalendarEvent.Status.PENDING,
        )
        event.status = PendingCalendarEvent.Status.SKIPPED
        event.save(update_fields=["status"])
        return JsonResponse({"success": True, "event_id": pk})
    except PendingCalendarEvent.DoesNotExist:
        return JsonResponse({"success": False, "error": _("Event not found.")}, status=404)


@require_POST
def calendar_event_quick_action(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Handle inline import/ignore of a single pending calendar event from the client detail page.

    POST fields:
    - action: "current_invoice" | "new_invoice" | "ignore"

    For import actions, creates a Session + InvoiceItem and marks the event as IMPORTED.
    For "ignore", marks the event as SKIPPED.
    Redirects back to the client detail page.
    """
    from datetime import datetime as dt

    from django.contrib import messages
    from django.db import transaction
    from django.shortcuts import redirect

    from ..models import InvoiceItem, Session
    from ..utils import get_next_invoice_number, sync_no_next_session_tag
    from ..utils.calendar_import_helpers import get_or_create_invoice_for_month

    practice = getattr(request, "current_practice", None)
    action = request.POST.get("action")

    try:
        event = PendingCalendarEvent.objects.select_related(
            "matched_client", "suggested_service_type"
        ).get(pk=pk, practice=practice, status=PendingCalendarEvent.Status.PENDING)
    except PendingCalendarEvent.DoesNotExist:
        messages.error(request, _("Event not found."))
        return redirect("client_list")

    client = event.matched_client
    redirect_target = (
        redirect("client_detail", pk=client.pk) if client else redirect("calendar_approval_queue")
    )

    if action == "ignore":
        event.status = PendingCalendarEvent.Status.SKIPPED
        event.save(update_fields=["status"])
        messages.success(
            request,
            _("Event on %(date)s skipped.") % {"date": event.event_date.strftime("%d.%m.%Y")},
        )
        return redirect_target

    if action not in ("current_invoice", "new_invoice"):
        messages.error(request, _("Unknown action."))
        return redirect_target

    if not client:
        messages.error(request, _("No client assigned to this event."))
        return redirect("calendar_approval_queue")

    # Resolve service type — prefer calendar match, fall back to default 60min
    service_type = event.suggested_service_type
    if service_type is None:
        from django.db.models import Q

        service_type = ServiceType.objects.filter(
            Q(practice=practice) | Q(practice__isnull=True),
            code="therapy_60",
        ).first()

    if service_type is None:
        messages.error(request, _("No matching service type found."))
        return redirect_target

    rate = resolve_session_rate(client, service_type)

    if rate == Decimal("0") and service_type.code != "therapy_free":
        messages.error(
            request,
            _("No hourly rate set for %(code)s.") % {"code": client.client_code},
        )
        return redirect_target

    # Guard against duplicates — exclude cancelled invoices so re-import after
    # cancellation works correctly.
    if (
        InvoiceItem.objects.filter(
            invoice__client=client,
            session__session_date=event.event_date,
            service_type=service_type,
        )
        .exclude(invoice__status=Invoice.Status.CANCELLED)
        .exists()
    ):
        messages.warning(
            request,
            _("Session on %(date)s is already billed.")
            % {"date": event.event_date.strftime("%d.%m.%Y")},
        )
        return redirect_target

    # Get or create target invoice
    event_dt = dt.combine(event.event_date, event.event_time or dt.min.time())
    if action == "new_invoice":
        invoice = Invoice.objects.create(
            client=client,
            invoice_date=event.event_date.replace(day=1),
            invoice_number=get_next_invoice_number(client),
            status="draft",
            practice=client.practice,
        )
    else:
        invoice = get_or_create_invoice_for_month(client, event_dt)

    try:
        with transaction.atomic():
            session, _created = Session.objects.get_or_create(
                client=client,
                session_date=event.event_date,
                session_time=event.event_time,
                defaults={
                    "duration": service_type.default_duration,
                    "calendar_event_id": event.google_event_id,
                },
            )
            InvoiceItem.objects.create(
                invoice=invoice,
                service_type=service_type,
                quantity=Decimal("1.00"),
                rate=rate,
                total=rate,
                session=session,
            )
            event.status = PendingCalendarEvent.Status.IMPORTED
            event.session = session
            event.save(update_fields=["status", "session"])
            sync_no_next_session_tag(client)

        messages.success(
            request,
            _("Event on %(date)s added to invoice %(number)s.")
            % {"date": event.event_date.strftime("%d.%m.%Y"), "number": invoice.invoice_number},
        )
    except Exception as e:
        messages.error(request, _("Import error: %(error)s") % {"error": e})

    return redirect_target
