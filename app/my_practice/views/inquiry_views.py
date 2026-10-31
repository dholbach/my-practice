"""Views for client inquiry / lead tracking (P-031)."""

import calendar
from datetime import date, timedelta
from itertools import groupby
from typing import cast

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import (
    Case,
    Count,
    IntegerField,
    Q,
    Value,
    When,
)
from django.db.models.functions import TruncMonth
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views import View

from ..inquiry_forms import InquiryConvertForm, InquiryForm, MarketingPeriodForm
from ..models import (
    CLOSED_INQUIRY_STATUSES,
    Client,
    ClientInquiry,
    InquiryStatus,
    MarketingPeriod,
)
from ..utils import DateRangeHelper
from ..utils.inquiry_email_templates import STAGE_EMAIL_TEMPLATES
from ..utils.practice_days import berlin_public_holidays
from .crud_mixins import (
    PracticeScopedCreateView,
    PracticeScopedDeleteView,
    PracticeScopedListView,
    PracticeScopedUpdateView,
)

# Source display labels keyed by value — used in analytics
_SOURCE_LABELS = dict(ClientInquiry._meta.get_field("source").choices)


def _interpolate_inquiry_template(template: dict, inquiry: ClientInquiry, practice) -> dict:
    """Return a copy of the template dict with runtime values substituted."""
    first_name = inquiry.full_name.split()[0] if inquiry.full_name else ""
    practitioner = practice.name or ""
    booking = practice.booking_url or "[Buchungs-URL]"
    booking_en = practice.booking_url or "[booking URL]"

    def _sub(text: str) -> str:
        return (
            text.replace("<..>", first_name)
            .replace("[Buchungs-URL]", booking)
            .replace("[booking URL]", booking_en)
            .replace("[Ihr Name]", practitioner)
            .replace("[Your name]", practitioner)
        )

    result = dict(template)
    if "body" in result:
        result["body"] = _sub(result["body"])
    if "body_en" in result:
        result["body_en"] = _sub(result["body_en"])
    return result


# Months shown in the monthly inquiry chart, ending with the current month.
_CHART_MONTHS = 12

# An open inquiry with no new step for this long counts as stale — the same
# threshold the grouped list below uses to fold rows away.
_STALE_DAYS = 30


def _month_offset(first_month: date, day: date) -> float:
    """Position of `day` on a month axis starting at `first_month`, in bar slots.

    Slot i is centred on i, so its month starts at i - 0.5; the day's fraction
    of its month places it inside the slot.
    """
    months = (day.year - first_month.year) * 12 + day.month - first_month.month
    days_in_month = calendar.monthrange(day.year, day.month)[1]
    return months + (day.day - 1) / days_in_month - 0.5


def _monthly_chart(base_qs, practice, today: date) -> dict:
    """Inquiries per month for the last 12 months, plus the marketing periods as lanes.

    Every month is listed, including empty ones — a gap in the bars is itself
    the signal (e.g. volume dropping once a paid campaign ended).
    """
    first_month = DateRangeHelper.add_months(date(today.year, today.month, 1), 1 - _CHART_MONTHS)
    months = [DateRangeHelper.add_months(first_month, i) for i in range(_CHART_MONTHS)]
    counts = {
        row["month"]: row["count"]
        for row in base_qs.filter(inquiry_date__gte=first_month)
        .annotate(month=TruncMonth("inquiry_date"))
        .values("month")
        .annotate(count=Count("id"))
    }

    axis_end = _CHART_MONTHS - 0.5
    lanes = []
    periods = MarketingPeriod.objects.filter(practice=practice, start_date__lte=today).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=first_month)
    )
    for period in periods.order_by("start_date"):
        start = max(_month_offset(first_month, period.start_date), -0.5)
        if period.end_date is None:
            end = axis_end
        else:
            end = min(_month_offset(first_month, period.end_date + timedelta(days=1)), axis_end)
        lanes.append({"label": period.description, "from": round(start, 3), "to": round(end, 3)})

    return {
        "labels": [m.strftime("%m/%y") for m in months],
        "counts": [counts.get(m, 0) for m in months],
        "lanes": lanes,
    }


def _open_inquiry_ageing(base_qs, today: date) -> list[dict]:
    """Open inquiries, longest-waiting first, with the days since their latest step.

    The latest step is ClientInquiry.last_step(). A milestone in the future —
    an intro meeting already booked — counts as zero days: nothing is overdue yet.
    """
    step_labels = {
        "inquiry_date": _("Received"),
        "contacted_date": _("Responded"),
        "intro_date": _("Intro meeting"),
        "decision_date": _("Decision"),
    }
    rows = []
    for inquiry in base_qs.open():
        step_date, step_field = inquiry.last_step()
        days = max((today - step_date).days, 0)
        rows.append(
            {
                "inquiry": inquiry,
                "days": days,
                "step": step_labels[step_field],
                "step_date": step_date,
                "stale": days > _STALE_DAYS,
            }
        )
    rows.sort(key=lambda row: row["days"], reverse=True)
    longest = rows[0]["days"] if rows else 0
    for row in rows:
        row["pct"] = round(100 * row["days"] / longest) if longest else 0
    return rows


def _build_inquiry_analytics(request) -> dict:
    """Compute funnel counts, time-in-stage averages, source breakdown, and monthly trend."""
    base_qs = ClientInquiry.objects.for_current_practice(request)
    today = timezone.localdate()

    # --- Funnel counts by status ---
    status_counts: dict[str, int] = {
        row["status"]: row["count"] for row in base_qs.values("status").annotate(count=Count("id"))
    }

    open_pipeline = [
        (InquiryStatus.NEW, _("New")),
        (InquiryStatus.CONTACTED, _("Contacted")),
        (InquiryStatus.INTRO_MEETING, _("Intro meeting")),
        (InquiryStatus.WAITLIST, _("Waitlist")),
        (InquiryStatus.IN_INTAKE, _("Intake")),
        (InquiryStatus.CONVERTED, _("Onboarded")),
    ]
    funnel_stages = [(s, label, status_counts.get(s, 0)) for s, label in open_pipeline]

    closed_count = sum(
        status_counts.get(s, 0) for s in CLOSED_INQUIRY_STATUSES - {InquiryStatus.CONVERTED}
    )

    # --- Time-in-stage averages (working days, Mon–Fri excl. Berlin public holidays) ---
    # Pre-build a holiday set covering all inquiry years (plus the next, for year-spanning cases).
    _inquiry_years = {d.year for d in base_qs.dates("inquiry_date", "year")}
    _holidays: set[date] = set()
    for yr in _inquiry_years:
        _holidays |= berlin_public_holidays(yr)
        _holidays |= berlin_public_holidays(yr + 1)

    def _avg_days(from_field: str, to_field: str) -> tuple[float | None, int]:
        pairs = list(
            base_qs.filter(
                **{f"{from_field}__isnull": False, f"{to_field}__isnull": False}
            ).values_list(from_field, to_field)
        )
        if not pairs:
            return None, 0
        # count_working_days is inclusive; use d2 - 1 day so only days *elapsed before* the
        # milestone are counted (same-day response = 0 working days).
        total = sum(
            DateRangeHelper.count_working_days(d1, d2 - timedelta(days=1), _holidays)
            for d1, d2 in pairs
            if d2 > d1
        )
        return round(total / len(pairs), 1), len(pairs)

    avg_to_contact, n_contact = _avg_days("inquiry_date", "contacted_date")
    avg_to_intro, n_intro = _avg_days("contacted_date", "intro_date")
    avg_to_decision, n_decision = _avg_days("intro_date", "decision_date")
    avg_to_converted, n_converted = _avg_days("decision_date", "converted_date")

    time_in_stage = [
        (_("Received → response"), avg_to_contact, n_contact),
        (_("Response → intro meeting"), avg_to_intro, n_intro),
        (_("Intro meeting → decision"), avg_to_decision, n_decision),
        (_("Decision → onboarded"), avg_to_converted, n_converted),
    ]

    # --- Source breakdown ---
    source_rows = list(base_qs.values("source").annotate(count=Count("id")).order_by("-count"))
    total = sum(r["count"] for r in source_rows) or 1
    source_breakdown = [
        {
            "source": r["source"],
            "label": _SOURCE_LABELS.get(r["source"], r["source"]),
            "count": r["count"],
            "pct": round(100 * r["count"] / total),
        }
        for r in source_rows
    ]

    # --- Language breakdown ---
    lang_rows = list(base_qs.values("language").annotate(count=Count("id")).order_by("-count"))
    lang_total = sum(r["count"] for r in lang_rows) or 1
    _lang_labels = {"de": _("German"), "en": _("English")}
    language_breakdown = [
        {
            "language": r["language"],
            "label": _lang_labels.get(r["language"], r["language"]),
            "count": r["count"],
            "pct": round(100 * r["count"] / lang_total),
        }
        for r in lang_rows
    ]

    return {
        "funnel_stages": funnel_stages,
        "closed_count": closed_count,
        "time_in_stage": time_in_stage,
        "source_breakdown": source_breakdown,
        "language_breakdown": language_breakdown,
        "monthly_chart": _monthly_chart(base_qs, request.current_practice, today),
        "open_ageing": _open_inquiry_ageing(base_qs, today),
        "total_inquiries": sum(status_counts.values()),
    }


class InquiryListView(PracticeScopedListView):
    """List all inquiries for the current practice, with optional status/source filter."""

    model = ClientInquiry
    template_name = "my_practice/inquiry_list.html"
    context_object_name = "inquiries"

    def get_queryset(self):
        qs = super().get_queryset().select_related("converted_client")
        status = self.request.GET.get("status")
        source = self.request.GET.get("source")
        # Default: hide closed inquiries unless explicitly requested
        if not self.request.GET.get("show_closed") and not status:
            qs = qs.open()
        if status:
            qs = qs.filter(status=status)
        if source:
            qs = qs.filter(source=source)
        # Sort by pipeline stage, then newest first within each stage
        status_priority = Case(
            When(status=InquiryStatus.NEW, then=Value(0)),
            When(status=InquiryStatus.CONTACTED, then=Value(1)),
            When(status=InquiryStatus.INTRO_MEETING, then=Value(2)),
            When(status=InquiryStatus.WAITLIST, then=Value(3)),
            When(status=InquiryStatus.IN_INTAKE, then=Value(3)),
            When(status=InquiryStatus.CONVERTED, then=Value(4)),
            When(status=InquiryStatus.DECLINED, then=Value(5)),
            When(status=InquiryStatus.UNREACHABLE, then=Value(5)),
            When(status=InquiryStatus.NOT_SUITABLE, then=Value(5)),
            When(status=InquiryStatus.LAPSED, then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )
        return qs.annotate(status_priority=status_priority).order_by(
            "status_priority", "-created_at"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_filter"] = self.request.GET.get("status", "")
        context["source_filter"] = self.request.GET.get("source", "")
        context["show_closed"] = bool(self.request.GET.get("show_closed"))
        context["status_choices"] = ClientInquiry._meta.get_field("status").choices
        context["source_choices"] = ClientInquiry._meta.get_field("source").choices
        context["marketing_periods"] = MarketingPeriod.objects.filter(
            practice=self.request.current_practice
        ).order_by("-start_date")
        analytics = _build_inquiry_analytics(self.request)
        context["analytics"] = analytics
        context["closed_count"] = analytics["closed_count"]

        # Group inquiries by pipeline stage for the section-header layout.
        # Items are already ordered by status_priority then -created_at.
        thirty_days_ago = timezone.localdate() - timedelta(days=30)
        _group_labels = {
            0: _("New"),
            1: _("Contacted"),
            2: _("Intro meeting"),
            3: _("Waitlist / intake"),
            4: _("Onboarded"),
            5: _("Closed"),
        }
        inquiry_groups = []
        for priority, group_iter in groupby(
            list(context["inquiries"]), key=lambda x: x.status_priority
        ):
            items = list(group_iter)
            fresh = [i for i in items if i.updated_at.date() >= thirty_days_ago]
            stale = [i for i in items if i.updated_at.date() < thirty_days_ago]
            inquiry_groups.append(
                {
                    "label": _group_labels.get(priority, _("Other")),
                    "priority": priority,
                    "status": items[0].status if items else "",
                    "fresh": fresh,
                    "stale": stale,
                    "total": len(items),
                }
            )
        context["inquiry_groups"] = inquiry_groups
        return context


class InquiryCreateView(PracticeScopedCreateView):
    """Create a new inquiry."""

    model = ClientInquiry
    form_class = InquiryForm
    template_name = "my_practice/inquiry_form.html"
    success_url = reverse_lazy("inquiry_list")
    success_message = gettext_lazy("Inquiry from {obj.full_name} recorded.")


class InquiryUpdateView(PracticeScopedUpdateView):
    """Edit an existing inquiry."""

    model = ClientInquiry
    form_class = InquiryForm
    template_name = "my_practice/inquiry_form.html"
    success_url = reverse_lazy("inquiry_list")
    success_message = gettext_lazy("Inquiry from {obj.full_name} saved.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_convert_button"] = self.object.can_convert()
        context["current_status"] = self.object.status
        context["booking_url_missing"] = not bool(self.request.current_practice.booking_url)
        context["all_email_templates"] = [
            {
                "status": status,
                "label": t["label"],
                "subject": t.get("subject", ""),
                "body": t.get("body", ""),
                "subject_en": t.get("subject_en", ""),
                "body_en": t.get("body_en", ""),
            }
            for status, t in (
                (s, _interpolate_inquiry_template(tmpl, self.object, self.request.current_practice))
                for s, tmpl in STAGE_EMAIL_TEMPLATES.items()
            )
        ]
        return context


class InquiryDeleteView(PracticeScopedDeleteView):
    """Delete an inquiry."""

    model = ClientInquiry
    template_name = "my_practice/inquiry_confirm_delete.html"
    success_url = reverse_lazy("inquiry_list")
    context_object_name = "inquiry"
    success_message = gettext_lazy("Inquiry from {obj.full_name} deleted.")


class MarketingPeriodCreateView(PracticeScopedCreateView):
    """Create a new marketing period."""

    model = MarketingPeriod
    form_class = MarketingPeriodForm
    template_name = "my_practice/marketing_period_form.html"
    success_url = reverse_lazy("inquiry_list")
    success_message = gettext_lazy("Marketing period recorded.")


class MarketingPeriodUpdateView(PracticeScopedUpdateView):
    """Edit an existing marketing period."""

    model = MarketingPeriod
    form_class = MarketingPeriodForm
    template_name = "my_practice/marketing_period_form.html"
    success_url = reverse_lazy("inquiry_list")
    success_message = gettext_lazy("Marketing period saved.")


class MarketingPeriodDeleteView(PracticeScopedDeleteView):
    """Delete a marketing period."""

    model = MarketingPeriod
    template_name = "my_practice/marketing_period_confirm_delete.html"
    success_url = reverse_lazy("inquiry_list")
    context_object_name = "period"
    success_message = gettext_lazy("Marketing period deleted.")


class InquiryConvertView(LoginRequiredMixin, View):
    """
    Convert an inquiry to a Client.

    GET: Show confirmation form pre-filled with inquiry data.
    POST: Create the Client, link it to the inquiry, set status=CONVERTED.
    """

    def _get_inquiry(self, request: HttpRequest, pk: int) -> ClientInquiry:
        return cast(
            ClientInquiry,
            get_object_or_404(
                ClientInquiry.objects.for_current_practice(request),
                pk=pk,
            ),
        )

    def _refuse(self, request: HttpRequest, inquiry: ClientInquiry) -> HttpResponse:
        """Redirect away from an inquiry that can no longer be converted."""
        if inquiry.converted_client_id:
            messages.info(request, _("This inquiry has already been added as a client."))
            return redirect(reverse("client_detail", kwargs={"pk": inquiry.converted_client_id}))
        messages.error(request, _("This inquiry can no longer be added as a client."))
        return redirect(reverse("inquiry_list"))

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        inquiry = self._get_inquiry(request, pk)
        if not inquiry.can_convert():
            return self._refuse(request, inquiry)
        form = InquiryConvertForm()
        return render(
            request,
            "my_practice/inquiry_convert_confirm.html",
            {"inquiry": inquiry, "form": form},
        )

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        form = InquiryConvertForm(request.POST)
        with transaction.atomic():
            # The row lock serialises a double submit, so the second one sees the first's
            # client and is refused instead of creating a duplicate.
            inquiry = cast(
                ClientInquiry,
                get_object_or_404(
                    ClientInquiry.objects.for_current_practice(request).select_for_update(),
                    pk=pk,
                ),
            )
            if not inquiry.can_convert():
                return self._refuse(request, inquiry)

            if not form.is_valid():
                return render(
                    request,
                    "my_practice/inquiry_convert_confirm.html",
                    {"inquiry": inquiry, "form": form},
                )

            client = self._create_client(request, inquiry, form)

        messages.success(
            request,
            _("Client %(name)s (%(code)s) created successfully.")
            % {"name": client.full_name, "code": client.client_code},
        )
        return redirect(reverse("client_detail", kwargs={"pk": client.pk}))

    def _create_client(
        self, request: HttpRequest, inquiry: ClientInquiry, form: InquiryConvertForm
    ) -> Client:
        """Create the Client from the inquiry and mark the inquiry converted."""
        client = Client.objects.create(
            practice=request.current_practice,
            full_name=inquiry.full_name,
            email=inquiry.email,
            phone=inquiry.phone,
            client_code=form.cleaned_data["client_code"],
            first_seen_date=form.cleaned_data.get("first_seen_date"),
            hourly_rate_60=form.cleaned_data["default_hourly_rate"],
            hourly_rate_90=form.cleaned_data["default_hourly_rate"],
            language=inquiry.language,
        )

        inquiry.converted_client = client
        inquiry.status = InquiryStatus.CONVERTED
        if not inquiry.converted_date:
            inquiry.converted_date = timezone.localdate()
        inquiry.save(update_fields=["converted_client", "status", "converted_date", "updated_at"])
        return client
