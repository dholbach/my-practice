"""
Monthly billing views: which clients have unbilled sessions, per month and overall.
"""

from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ..models import Client, Invoice, InvoiceItem, PendingCalendarEvent, Session
from ..utils.billing_helpers import (
    build_service_type_map,
    resolve_session_rate,
)


def _parse_billing_month(month: str) -> date | None:
    """Parse a 'YYYY-MM' string into the first day of that month, or None on error."""
    try:
        year_str, month_str = month.split("-")
        year, month_num = int(year_str), int(month_str)
        if not (1 <= month_num <= 12):
            raise ValueError
        return date(year, month_num, 1)
    except ValueError, AttributeError:
        return None


def _build_client_rows(
    clients,
    invoices_by_client: dict,
    billed_session_count_by_client: dict,
    unbilled_sessions_by_client: dict,
    pending_by_client: dict,
    cancelled_billed_by_client: dict,
    *,
    skip_ok: bool = False,
) -> list[dict]:
    """Build the per-client row dicts for billing overview templates."""
    rows = []
    for client in clients:
        client_invoices = invoices_by_client.get(client.pk, [])
        unbilled_sessions = unbilled_sessions_by_client.get(client.pk, [])
        unbilled_count = len(unbilled_sessions)
        pending_count = pending_by_client.get(client.pk, 0)
        cancelled_billed_count = cancelled_billed_by_client.get(client.pk, 0)
        billed_session_count = billed_session_count_by_client.get(client.pk, 0)

        status, status_label, status_icon = _determine_client_billing_status(
            client_invoices, unbilled_count, pending_count, cancelled_billed_count
        )
        if skip_ok and status == "ok":
            continue

        primary_invoice = _pick_primary_invoice(client_invoices)

        rows.append(
            {
                "client": client,
                "billed_session_count": billed_session_count,
                "unbilled_sessions": unbilled_sessions,
                "unbilled_count": unbilled_count,
                "pending_count": pending_count,
                "cancelled_billed_count": cancelled_billed_count,
                "invoices": client_invoices,
                "primary_invoice": primary_invoice,
                "status": status,
                "status_label": status_label,
                "status_icon": status_icon,
            }
        )
    return rows


def _pick_primary_invoice(client_invoices: list) -> "Invoice | None":
    """Prefer a draft invoice, then a sent one, then whatever's first."""
    for status in (Invoice.Status.DRAFT, Invoice.Status.SENT):
        for invoice in client_invoices:
            if invoice.status == status:
                return invoice
    return client_invoices[0] if client_invoices else None


def _build_billing_summary(rows: list[dict]) -> dict:
    """Summarise a list of billing rows by status."""
    return {
        "total": len(rows),
        "warning": sum(1 for r in rows if r["status"] == "warning"),
        "draft": sum(1 for r in rows if r["status"] == "draft"),
        "sent": sum(1 for r in rows if r["status"] == "sent"),
        "ok": sum(1 for r in rows if r["status"] == "ok"),
    }


def _gather_billing_data(practice, year, month_num):
    """Run all DB queries needed for the monthly billing overview.

    Grouping strategy:
    - Billed work    → invoice_date month (so XX-20 dated Feb shows in Feb, not Jan)
    - Unbilled work  → session_date month (genuinely outstanding work)
    - Pending events → event_date month

    Returns a 5-tuple of client-id-keyed dicts:
        (invoices_by_client, billed_session_count_by_client,
         unbilled_sessions_by_client, pending_by_client, cancelled_billed_by_client)
    """
    invoices_this_month = list(
        Invoice.objects.filter(
            practice=practice,
            invoice_date__year=year,
            invoice_date__month=month_num,
        )
        .exclude(status=Invoice.Status.CANCELLED)
        .prefetch_related("items")
        .order_by("-invoice_date")
    )
    invoices_by_client: dict[int, list] = {}
    for inv in invoices_this_month:
        invoices_by_client.setdefault(inv.client_id, []).append(inv)

    # Sessions this month: billed = session_date in M on a non-cancelled invoice;
    # unbilled = session_date in M with no invoice. Both sides share the same universe.
    billed_sessions_qs = InvoiceItem.objects.filter(
        invoice__practice=practice,
        session__session_date__year=year,
        session__session_date__month=month_num,
    ).exclude(invoice__status=Invoice.Status.CANCELLED)
    billed_session_ids = set(billed_sessions_qs.values_list("session_id", flat=True))
    billed_session_count_by_client: dict[int, int] = {}
    for row in billed_sessions_qs.values("session__client_id"):
        cid = row["session__client_id"]
        billed_session_count_by_client[cid] = billed_session_count_by_client.get(cid, 0) + 1

    unbilled_sessions_by_client: dict[int, list] = {}
    for session in (
        Session.objects.filter(
            client__practice=practice,
            session_date__year=year,
            session_date__month=month_num,
            cancelled=False,
            duration__gt=20,
            billable=True,
        )
        .exclude(pk__in=billed_session_ids)
        .order_by("session_date")
    ):
        unbilled_sessions_by_client.setdefault(session.client_id, []).append(session)

    already_billed_subquery = InvoiceItem.objects.filter(
        invoice__client=OuterRef("matched_client"),
        session__session_date=OuterRef("event_date"),
        session__duration__gte=OuterRef("duration_minutes") - 5,
        session__duration__lte=OuterRef("duration_minutes") + 5,
    ).exclude(invoice__status=Invoice.Status.CANCELLED)

    pending_by_client: dict[int, int] = {}
    for row in (
        PendingCalendarEvent.objects.filter(
            practice=practice,
            event_date__year=year,
            event_date__month=month_num,
            status=PendingCalendarEvent.Status.PENDING,
            matched_client__isnull=False,
        )
        .exclude(Exists(already_billed_subquery))
        .values("matched_client_id")
    ):
        cid = row["matched_client_id"]
        pending_by_client[cid] = pending_by_client.get(cid, 0) + 1

    # Invoice items on unpaid invoices this month that reference a cancelled session —
    # need manual cleanup before the invoice can be sent. Paid invoices are excluded
    # because they can no longer be edited and the warning would not be actionable.
    cancelled_billed_by_client: dict[int, int] = {}
    for row in (
        InvoiceItem.objects.filter(
            invoice__in=invoices_this_month,
            session__cancelled=True,
        )
        .exclude(invoice__status=Invoice.Status.PAID)
        .values("invoice__client_id")
    ):
        cid = row["invoice__client_id"]
        cancelled_billed_by_client[cid] = cancelled_billed_by_client.get(cid, 0) + 1

    return (
        invoices_by_client,
        billed_session_count_by_client,
        unbilled_sessions_by_client,
        pending_by_client,
        cancelled_billed_by_client,
    )


def _determine_client_billing_status(
    client_invoices: list,
    unbilled_count: int,
    pending_count: int,
    cancelled_billed_count: int,
) -> tuple[str, str, str]:
    """Return (status, label, icon) for a client row in the billing overview."""
    if cancelled_billed_count > 0:
        return "warning", _("Cancelled session billed"), "🚫"
    if pending_count > 0:
        return "warning", _("Appointments pending"), "⚠️"
    if unbilled_count > 0:
        return "warning", _("Not billed"), "📝"
    if not client_invoices:
        return "ok", _("OK"), "✅"

    statuses = {i.status for i in client_invoices}
    if statuses == {Invoice.Status.DRAFT}:
        return "draft", _("Draft"), "📄"
    if Invoice.Status.SENT in statuses:
        return "sent", _("Sent"), "📤"
    if statuses == {Invoice.Status.PAID}:
        return "ok", _("Paid"), "✅"
    return "ok", _("OK"), "✅"


@login_required
def monthly_billing_redirect(request):
    """Redirect to the current month's billing overview."""
    today = timezone.localdate()
    return redirect("monthly_billing_overview", month=f"{today.year}-{today.month:02d}")


@login_required
def billing_open_overview(request):
    """Cross-month view of all unresolved billing items (warning, draft, sent)."""
    practice = getattr(request, "current_practice", None)
    if not practice:
        messages.error(request, _("No active practice found."))
        return redirect("dashboard")

    # Find which months have open invoices (draft or sent)
    open_invoice_months = set(
        Invoice.objects.filter(practice=practice)
        .exclude(
            status__in=[
                Invoice.Status.PAID,
                Invoice.Status.CANCELLED,
                Invoice.Status.WRITTEN_OFF,
            ]
        )
        .values_list("invoice_date__year", "invoice_date__month")
    )

    # Find which months have unbilled sessions
    billed_session_ids = set(
        InvoiceItem.objects.filter(invoice__practice=practice)
        .exclude(invoice__status=Invoice.Status.CANCELLED)
        .values_list("session_id", flat=True)
    )
    unbilled_session_months = set(
        Session.objects.filter(
            client__practice=practice,
            cancelled=False,
            duration__gt=20,
            billable=True,
        )
        .exclude(pk__in=billed_session_ids)
        .values_list("session_date__year", "session_date__month")
    )

    # Find which months have pending calendar events
    pending_event_months = set(
        PendingCalendarEvent.objects.filter(
            practice=practice,
            status=PendingCalendarEvent.Status.PENDING,
            matched_client__isnull=False,
        ).values_list("event_date__year", "event_date__month")
    )

    all_months = sorted(
        open_invoice_months | unbilled_session_months | pending_event_months,
        reverse=True,
    )

    _status_order = {"warning": 0, "draft": 1, "sent": 2}
    months = []
    for year, month_num in all_months:
        (
            invoices_by_client,
            billed_session_count_by_client,
            unbilled_sessions_by_client,
            pending_by_client,
            cancelled_billed_by_client,
        ) = _gather_billing_data(practice, year, month_num)

        all_client_ids = (
            set(invoices_by_client)
            | set(unbilled_sessions_by_client)
            | set(pending_by_client)
            | set(cancelled_billed_by_client)
        )
        clients = Client.objects.filter(pk__in=all_client_ids).order_by("client_code")
        rows = _build_client_rows(
            clients,
            invoices_by_client,
            billed_session_count_by_client,
            unbilled_sessions_by_client,
            pending_by_client,
            cancelled_billed_by_client,
            skip_ok=True,
        )
        rows.sort(key=lambda r: (_status_order.get(r["status"], 5), r["client"].client_code))

        if rows:
            summary = _build_billing_summary(rows)
            months.append(
                {
                    "month_date": date(year, month_num, 1),
                    "month_str": f"{year}-{month_num:02d}",
                    "rows": rows,
                    "summary": summary,
                }
            )

    total_unresolved = sum(len(m["rows"]) for m in months)

    service_type_map = build_service_type_map(practice)
    fallback_service_type = next(iter(service_type_map.values()), None)

    total_unbilled_sessions = 0
    total_unbilled_fees = Decimal("0")
    for m in months:
        for row in m["rows"]:
            total_unbilled_sessions += row["unbilled_count"]
            for session in row["unbilled_sessions"]:
                service_type = service_type_map.get(session.duration, fallback_service_type)
                if service_type is not None:
                    total_unbilled_fees += resolve_session_rate(row["client"], service_type)

    return render(
        request,
        "my_practice/billing_open_overview.html",
        {
            "months": months,
            "total_unresolved": total_unresolved,
            "total_unbilled_sessions": total_unbilled_sessions,
            "total_unbilled_fees": total_unbilled_fees,
        },
    )


@login_required
def monthly_billing_overview(request, month):
    """
    Single-page billing status for all clients in a given month.

    Replaces the multi-step clients list → client detail → protocol → invoice
    navigation chain with one table showing pending events, session counts,
    and invoice state per client, with contextual quick actions.
    """
    billing_month_start = _parse_billing_month(month)
    if billing_month_start is None:
        return redirect("monthly_billing")

    practice = getattr(request, "current_practice", None)
    if not practice:
        messages.error(request, _("No active practice found."))
        return redirect("dashboard")

    today = timezone.localdate()
    year, month_num = billing_month_start.year, billing_month_start.month
    (
        invoices_by_client,
        billed_session_count_by_client,
        unbilled_sessions_by_client,
        pending_by_client,
        cancelled_billed_by_client,
    ) = _gather_billing_data(practice, year, month_num)

    all_client_ids = (
        set(invoices_by_client)
        | set(unbilled_sessions_by_client)
        | set(pending_by_client)
        | set(cancelled_billed_by_client)
    )
    clients = Client.objects.filter(pk__in=all_client_ids).order_by("client_code")
    rows = _build_client_rows(
        clients,
        invoices_by_client,
        billed_session_count_by_client,
        unbilled_sessions_by_client,
        pending_by_client,
        cancelled_billed_by_client,
    )

    _status_order = {"warning": 0, "draft": 1, "sent": 2, "ok": 3}
    rows.sort(key=lambda r: (_status_order.get(r["status"], 5), r["client"].client_code))

    prev_month = billing_month_start - relativedelta(months=1)
    next_month = billing_month_start + relativedelta(months=1)
    next_month_str = (
        f"{next_month.year}-{next_month.month:02d}"
        if next_month.replace(day=1) <= today.replace(day=1)
        else None
    )

    return render(
        request,
        "my_practice/monthly_billing_overview.html",
        {
            "billing_month": billing_month_start,
            "month_str": month,
            "prev_month_str": f"{prev_month.year}-{prev_month.month:02d}",
            "next_month_str": next_month_str,
            "rows": rows,
            "summary": _build_billing_summary(rows),
        },
    )
