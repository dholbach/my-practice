"""Inquiry analytics for the lead list (P-031): funnel, time in stage, sources, trend."""

import calendar
from datetime import date, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.utils.translation import gettext as _

from ..models import CLOSED_INQUIRY_STATUSES, ClientInquiry, InquiryStatus, MarketingPeriod
from ..models.base import scope_to_practice
from .date_helpers import DateRangeHelper
from .practice_days import berlin_public_holidays

# Source display labels keyed by value — used in analytics
_SOURCE_LABELS = dict(ClientInquiry._meta.get_field("source").choices)

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


def monthly_chart(base_qs, *, practice, today: date) -> dict:
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
    periods = (
        scope_to_practice(MarketingPeriod.objects.all(), practice)
        .filter(start_date__lte=today)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=first_month))
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


def open_inquiry_ageing(base_qs, today: date) -> list[dict]:
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


def build_inquiry_analytics(base_qs, *, practice, today: date | None = None) -> dict:
    """Funnel counts, time-in-stage averages, source and language breakdown, monthly trend.

    ``base_qs`` is the practice's inquiries (already scoped by the caller); ``practice``
    scopes the marketing periods drawn into the chart.
    """
    today = today or timezone.localdate()

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
        "monthly_chart": monthly_chart(base_qs, practice=practice, today=today),
        "open_ageing": open_inquiry_ageing(base_qs, today),
        "total_inquiries": sum(status_counts.values()),
    }
