"""
Shared helpers for session → InvoiceItem creation.

Four call sites need consistent service-type resolution, rate computation, and
already-billed detection:
  1. invoice_views.add_sessions_to_invoice
  2. invoice_views.create_invoice_with_sessions
  3. calendar_views (approval flow)
  4. calendar_import_helpers (manual calendar import flow, via resolve_session_rate)

Keeping this logic in one place means bugs fixed here fix all four.
"""

from decimal import Decimal

from django.db.models import Q

from ..models import Invoice, InvoiceItem, ServiceType


def build_service_type_map(practice) -> dict[int, ServiceType]:
    """
    Return a {default_duration: ServiceType} dict for a practice.

    Includes global service types (practice=None). When two types share the
    same default_duration the one with the higher code (alphabetically) wins —
    the dict is built in ascending code order so later entries overwrite earlier
    ones, and iteration order is stable.
    """
    return {
        st.default_duration: st
        for st in ServiceType.objects.filter(
            Q(practice=practice) | Q(practice__isnull=True)
        ).order_by("code")
    }


def resolve_session_rate(client, service_type) -> Decimal:
    """
    Return the billing rate for a session of this service type for the client.

    Returns Decimal("0") for free consultations (service_type.code == "therapy_free").
    Types with default_duration >= 90 use the client's separately-negotiated 90-min
    rate — not prorated, since practices often discount double sessions rather than
    charging a strict 1.5x multiple of the 60-min rate. Shorter types are prorated
    off the 60-min rate (default_duration / 60 * hourly_rate_60), so e.g. a 15-min
    check-in bills at a quarter of a full session instead of the full rate.
    """
    if service_type.code == "therapy_free":
        return Decimal("0")
    if service_type.default_duration >= 90:
        return Decimal(str(client.hourly_rate_90 or client.hourly_rate_60 or 0))
    hourly_rate_60 = Decimal(str(client.hourly_rate_60 or 0))
    proration = Decimal(service_type.default_duration) / Decimal("60")
    return (hourly_rate_60 * proration).quantize(Decimal("0.01"))


def is_session_already_billed(session) -> bool:
    """
    Return True if the session is attached to any non-cancelled InvoiceItem.

    Cancelled invoices are excluded so that a re-billed session (after
    cancellation) is not refused.
    """
    return (
        InvoiceItem.objects.filter(session=session)
        .exclude(invoice__status=Invoice.Status.CANCELLED)
        .exists()
    )


def create_invoice_item_for_session(
    invoice,
    session,
    service_type_map: dict[int, ServiceType],
    fallback_service_type: ServiceType | None = None,
) -> InvoiceItem | None:
    """
    Create an InvoiceItem for a session on a draft invoice.

    Returns the created InvoiceItem, or None when:
    - the session is already billed on a non-cancelled invoice, or
    - no service type could be resolved.

    Does NOT call recalculate_invoice_total — the caller is responsible for
    that after all items have been created.
    """
    if is_session_already_billed(session):
        return None

    service_type = service_type_map.get(session.duration, fallback_service_type)
    if service_type is None:
        return None

    rate = resolve_session_rate(invoice.client, service_type)
    return InvoiceItem.objects.create(
        invoice=invoice,
        session=session,
        service_type=service_type,
        rate=rate,
        quantity=Decimal("1.00"),
        total=rate,
    )
