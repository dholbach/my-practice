"""
Helper functions for calendar event import to InvoiceItems.
"""

from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from ..models import Client, Invoice, InvoiceItem, ServiceType
from ..models import Session
from ..utils import get_next_invoice_number, sync_no_next_session_tag
from .billing_helpers import resolve_session_rate


# ── Private resolution helpers ────────────────────────────────────────────────


def _resolve_client(event: dict, overrides: dict) -> tuple[Client | None, str | None]:
    """Return (client, None) or (None, error_message)."""
    client_id = overrides.get("client_id")
    if client_id:
        try:
            return Client.objects.get(id=client_id), None
        except Client.DoesNotExist:
            return None, _("Client ID %(id)s not found for event %(summary)s") % {
                "id": client_id,
                "summary": event.get("summary"),
            }
    if event.get("matched_client"):
        return event["matched_client"], None
    return None, _("No client for event: %(summary)s") % {"summary": event.get("summary")}


def _resolve_service_type(
    event: dict, overrides: dict, practice
) -> tuple[ServiceType | None, str | None]:
    """Return (service_type, None) or (None, error_message)."""
    service_type_id = overrides.get("service_type_id")
    if service_type_id:
        try:
            return ServiceType.objects.get(id=service_type_id), None
        except ServiceType.DoesNotExist:
            return None, _("Service type ID %(id)s not found") % {"id": service_type_id}
    if event.get("suggested_service_type_obj"):
        return event["suggested_service_type_obj"], None
    default = ServiceType.objects.filter(
        Q(practice=practice) | Q(practice__isnull=True), code="therapy_60"
    ).first()
    if not default:
        return None, _("No default service type found for event: %(summary)s") % {
            "summary": event.get("summary")
        }
    return default, None


def _resolve_rate(client: Client, service_type: ServiceType) -> tuple[Decimal | None, str | None]:
    """Return (rate, None) or (None, error_message).

    Delegates to billing_helpers.resolve_session_rate — the single source of
    truth for rate resolution shared with the manual invoice-creation and
    calendar-approval flows — and only adds the "no hourly rate configured"
    error this import flow surfaces to the user.
    """
    rate = resolve_session_rate(client, service_type)
    if rate == Decimal("0") and service_type.code != "therapy_free":
        return None, _("Client %(code)s has no hourly rate — set it in client settings") % {
            "code": client.client_code
        }
    return rate, None


# ── Public API ────────────────────────────────────────────────────────────────


def create_invoice_items_from_events(
    approved_events: list[dict], user_overrides: dict[str, dict], request
) -> tuple[int, int, list[str]]:
    """
    Create InvoiceItems from approved calendar events.

    Args:
        approved_events: List of event dicts from CalendarEventParser
        user_overrides: Dict mapping event IDs to override data
            {
                'event_id': {
                    'client_id': int,
                    'service_type_id': int,
                    'action': 'import' | 'skip'
                }
            }
        request: HttpRequest with current_practice

    Returns:
        Tuple of (created_count, skipped_count, errors)
    """
    created = 0
    skipped = 0
    errors = []

    for event in approved_events:
        event_id = event.get("id") or ""
        overrides = user_overrides.get(event_id, {})

        if overrides.get("action") == "skip":
            skipped += 1
            continue

        client, err = _resolve_client(event, overrides)
        if err:
            errors.append(err)
            if not client:
                skipped += 1
            continue

        service_type, err = _resolve_service_type(event, overrides, request.current_practice)
        if err:
            errors.append(err)
            continue

        event_date = event.get("start")
        if not event_date:
            errors.append(_("No date for event: %(summary)s") % {"summary": event.get("summary")})
            continue

        invoice = get_or_create_invoice_for_month(client, event_date)

        if InvoiceItem.objects.filter(
            invoice=invoice,
            session__session_date=event_date.date(),
            service_type=service_type,
        ).exists():
            errors.append(
                _("Duplicate: %(summary)s on %(date)s")
                % {"summary": event.get("summary"), "date": event_date.date()}
            )
            skipped += 1
            continue

        rate, err = _resolve_rate(client, service_type)
        if err:
            errors.append(err)
            skipped += 1
            continue

        try:
            with transaction.atomic():
                if service_type.code == "therapy_free" and not client.first_seen_date:
                    client.first_seen_date = event_date.date()
                    client.save(update_fields=["first_seen_date"])

                session_time = event_date.time() if isinstance(event_date, datetime) else None
                session, _created = Session.objects.get_or_create(
                    client=client,
                    session_date=event_date.date(),
                    session_time=session_time,
                    defaults={
                        "duration": service_type.default_duration,
                        "calendar_event_id": event_id or "",
                    },
                )
                InvoiceItem.objects.create(
                    invoice=invoice,
                    service_type=service_type,
                    quantity=1,
                    rate=rate,
                    session=session,
                )
                sync_no_next_session_tag(client)
                created += 1
        except Exception as e:
            errors.append(
                _("Error creating %(summary)s: %(error)s")
                % {"summary": event.get("summary"), "error": str(e)}
            )

    return created, skipped, errors


def get_or_create_invoice_for_month(client: Client, date: datetime) -> Invoice:
    """
    Get or create a draft invoice for the given client.
    Uses a single running draft invoice per client instead of monthly invoices.

    Args:
        client: Client object
        date: Date within the target period (used for invoice_date if creating new)

    Returns:
        Invoice object (existing draft or newly created)
    """
    # Check if draft invoice exists for this client
    existing = Invoice.objects.filter(client=client, status="draft").first()

    if existing:
        return existing

    # Create new draft invoice with first day of month as invoice_date
    first_day = date.replace(day=1)
    invoice_number = get_next_invoice_number(client)
    invoice = Invoice.objects.create(
        client=client,
        invoice_date=first_day,
        invoice_number=invoice_number,
        status="draft",
        practice=client.practice,
    )

    return invoice


def bill_session(session: "Session", practice) -> tuple[bool, str]:
    """
    Create an InvoiceItem for an unbilled Session (P-036 Phase 2).

    Determines service type and rate from the linked PendingCalendarEvent
    (if available) or falls back to the default 60-min service type.

    Returns:
        (success: bool, message: str)
    """
    client = session.client

    # Determine service type — prefer what was auto-matched on the calendar event
    service_type = None
    try:
        pce = session.pending_calendar_event
        if pce and pce.suggested_service_type:
            service_type = pce.suggested_service_type
    except Exception:
        pass

    if service_type is None:
        service_type = ServiceType.objects.filter(
            Q(practice=practice) | Q(practice__isnull=True),
            code="therapy_60",
        ).first()

    if service_type is None:
        return False, _("No matching service type found.")

    rate, err = _resolve_rate(client, service_type)
    if err:
        return False, _("No hourly rate set for %(code)s.") % {"code": client.client_code}

    # Guard: already billed
    if InvoiceItem.objects.filter(session=session).exists():
        return False, _("Session is already billed.")

    from datetime import datetime as dt

    session_dt = dt.combine(session.session_date, session.session_time or dt.min.time())

    try:
        with transaction.atomic():
            invoice = get_or_create_invoice_for_month(client, session_dt)
            try:
                pce = session.pending_calendar_event
                if pce:
                    pass
            except Exception:
                pass

            InvoiceItem.objects.create(
                invoice=invoice,
                service_type=service_type,
                quantity=1,
                rate=rate,
                session=session,
            )
            sync_no_next_session_tag(client)
    except Exception as e:
        return False, _("Error: %(error)s") % {"error": e}

    return True, _("Session on %(date)s was billed.") % {
        "date": session.session_date.strftime("%d.%m.%Y")
    }
