"""
Invoice-related views (CRUD operations).
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Case, Count, DecimalField, F, Q, QuerySet, Sum, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView

from ..invoice_forms import InvoiceForm
from ..models import Client, Invoice, InvoiceItem, PendingCalendarEvent, ServiceType, Session
from ..signals import recalculate_invoice_total
from ..utils import RevenueCalculator, get_next_invoice_number
from ..utils.calendar_preflight import CalendarPreflightChecker
from ..utils.invoice_filter_helper import InvoiceFilterHelper
from ..utils.view_helpers import get_year_from_request, safe_next
from .crud_mixins import (
    InvoiceFormsetMixin,
    PracticeScopedCreateView,
    PracticeScopedListView,
    PracticeScopedUpdateView,
)

logger = logging.getLogger(__name__)


class InvoiceListView(PracticeScopedListView):
    """List all invoices"""

    model = Invoice
    template_name = "my_practice/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 20
    ordering = ["-invoice_date", "-invoice_number"]  # Newest invoice date first

    def get_queryset(self) -> QuerySet[Invoice]:
        """Get filtered invoice queryset using InvoiceFilterHelper."""
        # Get practice-scoped queryset from parent
        queryset = super().get_queryset().select_related("client")

        # Use InvoiceFilterHelper to apply all filters
        filter_helper = InvoiceFilterHelper(queryset)

        return filter_helper.apply_filters(
            search_query=self.request.GET.get("search", "").strip(),
            status_filter=self.request.GET.get("status"),
            multi_status=self.request.GET.get("statuses"),
            year_filter=get_year_from_request(self.request, "year", None),
            start_date=self.request.GET.get("start_date"),
            end_date=self.request.GET.get("end_date"),
            min_amount=self.request.GET.get("min_amount"),
            max_amount=self.request.GET.get("max_amount"),
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        # Base queryset respecting year filter
        year_filter = get_year_from_request(self.request, "year", None)

        # Get status breakdown with year-aware filtering AND practice filter
        # (paid invoices filtered by paid_date, others by invoice_date)
        status_stats = RevenueCalculator.get_status_breakdown(
            year=year_filter, filters={"practice": self.request.current_practice}
        )

        # Calculate total across all statuses
        total_count = sum(status_stats[status]["count"] for status in status_stats)
        total_amount = sum(status_stats[status]["total"] for status in status_stats)

        context["stats"] = {
            "total": total_count,
            "total_amount": total_amount,
            "draft": status_stats["draft"]["count"],
            "draft_amount": status_stats["draft"]["total"],
            "sent": status_stats["sent"]["count"],
            "sent_amount": status_stats["sent"]["total"],
            "paid": status_stats["paid"]["count"],
            "paid_amount": status_stats["paid"]["total"],
        }
        context["current_status"] = self.request.GET.get("status", "all")
        context["current_year"] = year_filter or "all"

        # Advanced filter parameters for UI
        context["search_query"] = self.request.GET.get("search", "")
        context["start_date"] = self.request.GET.get("start_date", "")
        context["end_date"] = self.request.GET.get("end_date", "")
        context["min_amount"] = self.request.GET.get("min_amount", "")
        context["max_amount"] = self.request.GET.get("max_amount", "")

        # Get available years for filter dropdown (practice-scoped)
        years = Invoice.objects.for_current_practice(self.request).dates(
            "invoice_date", "year", order="DESC"
        )
        context["available_years"] = [date.year for date in years]

        context["unbilled"] = self._unbilled_summary()
        return context

    def _unbilled_summary(self) -> dict:
        """Count clients and estimate revenue for sessions not yet on any invoice."""
        practice = self.request.current_practice
        billed_ids = InvoiceItem.objects.exclude(
            invoice__status=Invoice.Status.CANCELLED
        ).values_list("session_id", flat=True)

        unbilled = (
            Session.objects.filter(client__practice=practice, cancelled=False, billable=True)
            .exclude(id__in=billed_ids)
            .exclude(duration__lte=20)
        )

        agg = unbilled.annotate(
            session_rate=Case(
                When(duration__gte=90, then=F("client__hourly_rate_90")),
                default=F("client__hourly_rate_60"),
                output_field=DecimalField(),
            )
        ).aggregate(
            client_count=Count("client", distinct=True),
            amount=Sum("session_rate"),
        )

        return {
            "client_count": agg["client_count"] or 0,
            "amount": float(agg["amount"] or 0),
        }


class InvoiceCreateView(InvoiceFormsetMixin, PracticeScopedCreateView):
    """Create new invoice"""

    model = Invoice
    form_class = InvoiceForm
    template_name = "my_practice/invoice_form.html"
    success_url = reverse_lazy("invoice_list")
    # Note: Success message handled in form_valid() due to complex transaction logic

    def get_initial(self):
        """Pre-fill client and suggest next invoice number based on URL param"""
        initial = super().get_initial()

        # Set current practice as default
        initial["practice"] = self.request.current_practice

        client_id = self.request.GET.get("client")
        if client_id:
            try:
                # Only allow clients from current practice (or accessible practices)
                client = Client.objects.for_current_practice(self.request).get(pk=client_id)
                initial["client"] = client
                suggested_number = get_next_invoice_number(client)
                initial["invoice_number"] = suggested_number
            except Client.DoesNotExist:
                # Client doesn't exist or doesn't belong to current practice
                pass
        return initial

    def get_form_kwargs(self):
        """Pass request to form for practice-scoped client filtering"""
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return self.get_formset_context(context, formset_key="items")

    def form_valid(self, form):
        context = self.get_context_data()
        items = context["items"]

        try:
            with transaction.atomic():
                # Practice assignment handled by PracticeScopedCreateView base class
                # but we need to ensure it's set before generating invoice number
                if not form.instance.practice_id:
                    form.instance.practice = self.request.current_practice

                # Generate invoice number only if not provided
                if not form.instance.invoice_number:
                    client = form.instance.client
                    form.instance.invoice_number = get_next_invoice_number(client)

                self.object = form.save()

                if items.is_valid():
                    items.instance = self.object
                    # Create/get Sessions for each item from form's session_date + duration
                    client = self.object.client
                    for form in items.forms:
                        if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                            continue
                        session_date = form.cleaned_data["session_date"]
                        duration = form.cleaned_data.get("duration", 60)
                        session, _ = Session.objects.get_or_create(
                            client=client,
                            session_date=session_date,
                            defaults={"duration": duration},
                        )
                        form.instance.session = session
                    items.save()  # signals handle total + date recalculation
                    self.object.refresh_from_db()

                    messages.success(
                        self.request,
                        f"Invoice {self.object.invoice_number} created successfully! / "
                        f"Rechnung {self.object.invoice_number} erfolgreich erstellt!",
                    )
                    return redirect(self.success_url)
                else:
                    # Formset validation failed - show errors
                    for i, form_errors in enumerate(items.errors):
                        if form_errors:
                            messages.error(self.request, f"Item {i + 1}: {form_errors}")
                    if items.non_form_errors():
                        messages.error(self.request, f"Formset errors: {items.non_form_errors()}")
                    return self.form_invalid(form)
        except Exception as e:
            logger.exception("Error creating invoice")
            messages.error(self.request, f"Error creating invoice: {str(e)}")
            return self.form_invalid(form)


class InvoiceDetailView(DetailView):
    """View invoice details"""

    model = Invoice
    template_name = "my_practice/invoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        """Ensure invoice belongs to current practice"""
        return Invoice.objects.for_current_practice(self.request).prefetch_related(
            "items__service_type", "items__session"
        )

    def get_object(self, queryset=None):
        invoice = super().get_object(queryset)
        invoice.sync_invoice_date()
        return invoice

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Add calendar pre-flight check for draft/sent invoices (P-013)."""
        context = super().get_context_data(**kwargs)
        invoice = self.object
        if invoice.status in ("draft", "sent"):
            checker = CalendarPreflightChecker(invoice)
            if checker.has_calendar_events():
                context["calendar_preflight"] = checker.check()
        return context


class InvoiceEditView(InvoiceFormsetMixin, PracticeScopedUpdateView):
    """Edit invoice with inline items using formset"""

    model = Invoice
    form_class = InvoiceForm
    template_name = "my_practice/invoice_edit.html"
    context_object_name = "invoice"
    success_message = "Rechnung {obj.invoice_number} erfolgreich aktualisiert!"

    def get_queryset(self):
        """Optimize query with select_related/prefetch_related"""
        queryset = super().get_queryset()  # Already practice-scoped
        return queryset.select_related("client").prefetch_related("items")

    def get_success_url(self) -> str:
        return safe_next(
            self.request,
            fallback=reverse("invoice_detail", kwargs={"pk": self.object.pk}),
        )

    def get_form_kwargs(self):
        """Pass request to form for practice-scoped client filtering"""
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context: dict[str, Any] = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        return self.get_formset_context(context, formset_key="formset")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if not form.is_bound and self.object and self.object.status == Invoice.Status.DRAFT:
            self.object.sync_invoice_date()
            form.initial["invoice_date"] = self.object.invoice_date
        return form

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["formset"]

        with transaction.atomic():
            if formset.is_valid():
                # Save invoice first
                invoice = form.save()

                # Create/get Sessions for each item from form's session_date + duration
                for f in formset.forms:
                    if not f.cleaned_data or f.cleaned_data.get("DELETE"):
                        continue
                    session_date = f.cleaned_data["session_date"]
                    duration = f.cleaned_data.get("duration", 60)
                    session, _ = Session.objects.get_or_create(
                        client=invoice.client,
                        session_date=session_date,
                        defaults={"duration": duration},
                    )
                    f.instance.session = session

                # Save formset (this will trigger signals for each item)
                formset.instance = invoice
                formset.save()

                # Signals handle total/date recalculation when items change.
                # For DRAFT invoices where no items changed, ensure the date is
                # still refreshed to max(today, latest_session_date).
                if invoice.status == Invoice.Status.DRAFT:
                    recalculate_invoice_total(invoice)

                # Refresh invoice from DB to get updated values
                invoice.refresh_from_db()

                self.object = invoice
                # Success message handled by PracticeScopedUpdateView
                return redirect(self.get_success_url())
            else:
                # Show formset errors
                for i, form_errors in enumerate(formset.errors):
                    if form_errors:
                        for field, errors in form_errors.items():
                            for error in errors:
                                messages.error(self.request, f"Item {i + 1} - {field}: {error}")
                if formset.non_form_errors():
                    for error in formset.non_form_errors():
                        messages.error(self.request, f"Formset: {error}")
                return self.form_invalid(form)

    def form_invalid(self, form):
        # Show main form errors
        if form.errors:
            for field, errors in form.errors.items():
                for error in errors:
                    field_label = form.fields.get(field).label if field in form.fields else field
                    messages.error(self.request, f"{field_label}: {error}")

        # Also check formset errors (formset validation might happen even if form is invalid)
        context = self.get_context_data(form=form)
        formset = context.get("formset")
        if formset and hasattr(formset, "errors"):
            for i, form_errors in enumerate(formset.errors):
                if form_errors:
                    for field, errors in form_errors.items():
                        for error in errors:
                            messages.error(self.request, f"Item {i + 1} - {field}: {error}")
            if hasattr(formset, "non_form_errors") and formset.non_form_errors():
                for error in formset.non_form_errors():
                    messages.error(self.request, f"Formset: {error}")

        if not form.errors and (not formset or not formset.errors):
            messages.error(self.request, "Bitte korrigieren Sie die Fehler im Formular.")

        return super().form_invalid(form)


@login_required
def invoice_delete(request, pk):
    """Delete an invoice (with confirmation page)"""
    invoice = get_object_or_404(Invoice.objects.for_current_practice(request), pk=pk)

    if request.method == "POST":
        # Store data for success message
        invoice_number = invoice.invoice_number
        client_code = invoice.client.client_code

        # Delete the invoice (cascade will delete items)
        invoice.delete()

        messages.success(
            request,
            f"Rechnung {invoice_number} für {client_code} wurde erfolgreich gelöscht.",
        )
        return redirect(safe_next(request, fallback=reverse("invoice_list")))

    # GET request - show confirmation page
    next_url = request.GET.get("next", "")
    return render(
        request,
        "my_practice/invoice_confirm_delete.html",
        {"invoice": invoice, "next": next_url},
    )


@login_required
def add_sessions_to_invoice(request, pk):
    """Add one or more unbilled sessions to an existing draft invoice as line items."""
    if request.method != "POST":
        return redirect("invoice_detail", pk=pk)

    practice = getattr(request, "current_practice", None)
    invoice = get_object_or_404(Invoice, pk=pk, practice=practice, status=Invoice.Status.DRAFT)

    session_ids = request.POST.getlist("session_ids")
    if not session_ids:
        messages.warning(request, "Keine Sitzungen angegeben.")
        return redirect("invoice_detail", pk=pk)

    sessions = Session.objects.filter(
        pk__in=session_ids,
        client=invoice.client,
        cancelled=False,
    )

    # Pick service type by duration: prefer exact match on default_duration, fall back
    # to the first available type for the practice.
    service_types = {
        st.default_duration: st
        for st in ServiceType.objects.filter(Q(practice=practice) | Q(practice__isnull=True))
    }
    fallback_service_type = next(iter(service_types.values())) if service_types else None

    added = 0
    for session in sessions:
        # Skip if already on a non-cancelled invoice (race condition guard).
        already_billed = (
            InvoiceItem.objects.filter(
                session=session,
            )
            .exclude(invoice__status=Invoice.Status.CANCELLED)
            .exists()
        )
        if already_billed:
            continue

        service_type = service_types.get(session.duration, fallback_service_type)
        if service_type is None:
            continue

        rate = (
            invoice.client.hourly_rate_90
            if session.duration >= 90
            else invoice.client.hourly_rate_60
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            session=session,
            service_type=service_type,
            rate=rate,
            quantity=Decimal("1.00"),
            total=rate,
        )
        added += 1

    if added:
        recalculate_invoice_total(invoice)
        messages.success(
            request,
            f"{added} Sitzung{'en' if added != 1 else ''} zu {invoice.invoice_number} hinzugefügt.",
        )
    else:
        messages.warning(request, "Keine neuen Sitzungen hinzugefügt (bereits abgerechnet?).")

    next_url = request.POST.get("next")
    return redirect(next_url or "invoice_detail", pk=pk)


@login_required
def create_invoice_with_sessions(request):
    """Create a new draft invoice for a client and immediately attach unbilled sessions."""
    if request.method != "POST":
        return redirect("invoice_list")

    practice = getattr(request, "current_practice", None)
    if not practice:
        messages.error(request, "Keine aktive Praxis gefunden.")
        return redirect("dashboard")

    client_id = request.POST.get("client_id")
    client = get_object_or_404(Client, pk=client_id, practice=practice)

    session_ids = request.POST.getlist("session_ids")
    sessions = list(
        Session.objects.filter(
            pk__in=session_ids,
            client=client,
            cancelled=False,
        ).order_by("session_date")
    )
    if not sessions:
        messages.warning(request, "Keine Sitzungen angegeben.")
        next_url = request.POST.get("next")
        return redirect(next_url or "invoice_list")

    service_types = {
        st.default_duration: st
        for st in ServiceType.objects.filter(Q(practice=practice) | Q(practice__isnull=True))
    }
    fallback_service_type = next(iter(service_types.values())) if service_types else None

    with transaction.atomic():
        invoice = Invoice.objects.create(
            practice=practice,
            client=client,
            invoice_number=get_next_invoice_number(client),
            status=Invoice.Status.DRAFT,
            invoice_date=date.today(),
        )
        for session in sessions:
            service_type = service_types.get(session.duration, fallback_service_type)
            rate = client.hourly_rate_90 if session.duration >= 90 else client.hourly_rate_60
            InvoiceItem.objects.create(
                invoice=invoice,
                session=session,
                service_type=service_type,
                rate=rate,
                quantity=Decimal("1.00"),
                total=rate,
            )
        recalculate_invoice_total(invoice)

    messages.success(
        request,
        f"Rechnung {invoice.invoice_number} mit {len(sessions)} Sitzung{'en' if len(sessions) != 1 else ''} erstellt.",
    )
    next_url = request.POST.get("next")
    return redirect(next_url or "invoice_detail", pk=invoice.pk)


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

        drafts = [i for i in client_invoices if i.status == Invoice.Status.DRAFT]
        sent = [i for i in client_invoices if i.status == Invoice.Status.SENT]
        primary_invoice = (
            drafts[0]
            if drafts
            else (sent[0] if sent else (client_invoices[0] if client_invoices else None))
        )

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
    - Billed work    → invoice_date month (so GM-20 dated Feb shows in Feb, not Jan)
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

    pending_by_client: dict[int, int] = {}
    for row in PendingCalendarEvent.objects.filter(
        practice=practice,
        event_date__year=year,
        event_date__month=month_num,
        status=PendingCalendarEvent.Status.PENDING,
        matched_client__isnull=False,
    ).values("matched_client_id"):
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
        return "warning", "Stornierte Sitzung abgerechnet", "🚫"
    if pending_count > 0:
        return "warning", "Termine ausstehend", "⚠️"
    if unbilled_count > 0:
        return "warning", "Nicht abgerechnet", "📝"
    if client_invoices and all(i.status == Invoice.Status.DRAFT for i in client_invoices):
        return "draft", "Entwurf", "📄"
    if client_invoices and any(i.status == Invoice.Status.SENT for i in client_invoices):
        return "sent", "Versendet", "📤"
    if client_invoices and all(i.status == Invoice.Status.PAID for i in client_invoices):
        return "ok", "Bezahlt", "✅"
    return "ok", "OK", "✅"


@login_required
def monthly_billing_redirect(request):
    """Redirect to the current month's billing overview."""
    today = date.today()
    return redirect("monthly_billing_overview", month=f"{today.year}-{today.month:02d}")


@login_required
def billing_open_overview(request):
    """Cross-month view of all unresolved billing items (warning, draft, sent)."""
    practice = getattr(request, "current_practice", None)
    if not practice:
        messages.error(request, "Keine aktive Praxis gefunden.")
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

    return render(
        request,
        "my_practice/billing_open_overview.html",
        {
            "months": months,
            "total_unresolved": total_unresolved,
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
        messages.error(request, "Keine aktive Praxis gefunden.")
        return redirect("dashboard")

    today = date.today()
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
