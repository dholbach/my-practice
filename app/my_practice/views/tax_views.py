"""
Tax year summary view - provides comprehensive financial overview for tax purposes.
"""

import calendar
from datetime import date
from decimal import Decimal
from typing import cast

from django.db.models import Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..models import CompanyExpense, CompanyWithdrawal, Invoice, TaxYearNote
from ..utils import TaxYearContextBuilder
from ..utils.practice_days import WorkdayAuditCalculator
from ..utils.view_helpers import get_year_from_request


def _quarter_date_range(year: int, quarter: int) -> tuple[date, date]:
    """Return (start, end) dates for the given year and quarter (1–4)."""
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    start = date(year, start_month, 1)
    end = date(year, end_month, calendar.monthrange(year, end_month)[1])
    return start, end


def tax_year_summary(request: HttpRequest) -> HttpResponse:
    """Generate comprehensive tax year summary with revenue, expenses, and deductions."""
    year = get_year_from_request(request, "year", date.today().year) or date.today().year
    context = TaxYearContextBuilder(year, request.current_practice, request.user).build(
        expense_sort=request.GET.get("sort", "date")
    )
    return render(request, "my_practice/tax_year_summary.html", context)


@require_POST
def save_tax_year_note(request: HttpRequest) -> JsonResponse:
    """
    Save (upsert) a TaxYearNote for the current practice and a given year.

    Accepts a POST body with:
      - year   (int)
      - note   (str, may be blank to clear)

    Returns JSON {saved: true, updated_at: "..."}.
    """
    practice = request.current_practice
    if not practice:
        return JsonResponse({"error": "no practice"}, status=400)

    try:
        year = int(request.POST.get("year", 0))
    except TypeError, ValueError:
        return JsonResponse({"error": "invalid year"}, status=400)

    if not (1900 <= year <= 2100):
        return JsonResponse({"error": "invalid year"}, status=400)

    note_text = request.POST.get("note", "").strip()

    obj, _ = TaxYearNote.objects.update_or_create(
        practice=practice,
        year=year,
        defaults={"allocation_note": note_text},
    )
    return JsonResponse({"saved": True, "updated_at": obj.updated_at.strftime("%d.%m.%Y %H:%M")})


def tax_workday_audit(request: HttpRequest) -> HttpResponse:
    """
    Printable day-by-day workday audit list for a tax year.

    Classifies every Mon–Fri as: practice day, home-office day, public holiday,
    or time-off. Includes session count per day for verification.
    """
    year = get_year_from_request(request, "year", date.today().year) or date.today().year
    practice = request.current_practice

    audit = WorkdayAuditCalculator(practice, year).calculate() if practice else None

    available_years = (
        sorted(
            {
                d.year
                for d in Invoice.objects.filter(practice=practice).dates("invoice_date", "year")
            }
            | {
                d.year
                for d in CompanyExpense.objects.filter(practice=practice).dates("date", "year")
            },
            reverse=True,
        )
        if practice
        else []
    )

    return render(
        request,
        "my_practice/tax_workday_audit.html",
        {"year": year, "audit": audit, "practice": practice, "available_years": available_years},
    )


def tax_quarter_overview(request: HttpRequest) -> HttpResponse:
    """
    Quarterly tax overview for Steuervorauszahlung tracking (P-013 Phase 2).

    Shows per-quarter revenue, deductible expenses, and net profit for the
    selected year, plus a history of tax prepayment withdrawals (category='tax').
    Provides a quick-add link to record a new prepayment.
    """
    year = get_year_from_request(request, "year", date.today().year) or date.today().year
    practice = request.current_practice
    today = date.today()
    current_quarter = (today.month - 1) // 3 + 1

    quarters = []
    for q in range(1, 5):
        start, end = _quarter_date_range(year, q)

        revenue = Invoice.objects.filter(
            practice=practice,
            status="paid",
            paid_date__range=(start, end),
        ).aggregate(total=Sum("total"))["total"] or Decimal("0")

        expenses = CompanyExpense.objects.filter(
            practice=practice,
            date__range=(start, end),
            is_tax_deductible=True,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        tax_withdrawals = CompanyWithdrawal.objects.filter(
            practice=practice,
            category="tax",
            date__range=(start, end),
        ).order_by("date")
        tax_paid = sum(w.amount for w in tax_withdrawals)

        # A quarter is "complete" once its last day has passed
        is_complete = today > end
        is_current = q == current_quarter and year == today.year
        # Flag quarters where money was earned but no prepayment recorded
        needs_attention = (
            (is_complete or is_current) and revenue > 0 and not tax_withdrawals.exists()
        )

        quarters.append(
            {
                "number": q,
                "label": f"Q{q}",
                "start": start,
                "end": end,
                "revenue": revenue,
                "expenses": expenses,
                "net_profit": revenue - expenses,
                "tax_withdrawals": tax_withdrawals,
                "tax_paid": tax_paid,
                "is_complete": is_complete,
                "is_current": is_current,
                "needs_attention": needs_attention,
            }
        )

    total_revenue: Decimal = sum((cast(Decimal, q["revenue"]) for q in quarters), Decimal("0"))
    total_expenses: Decimal = sum((cast(Decimal, q["expenses"]) for q in quarters), Decimal("0"))
    total_tax_paid: Decimal = sum((cast(Decimal, q["tax_paid"]) for q in quarters), Decimal("0"))

    available_years = sorted(
        {d.year for d in Invoice.objects.filter(practice=practice).dates("invoice_date", "year")},
        reverse=True,
    )
    if not available_years:
        available_years = [today.year]

    return render(
        request,
        "my_practice/tax_quarter_overview.html",
        {
            "quarters": quarters,
            "year": year,
            "available_years": available_years,
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "total_tax_paid": total_tax_paid,
            "total_net_profit": total_revenue - total_expenses,
            "current_quarter": current_quarter,
            "add_payment_url": reverse("withdrawal_create") + "?category=tax",
        },
    )
