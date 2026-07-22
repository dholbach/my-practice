"""
Tax year summary view - provides comprehensive financial overview for tax purposes.
"""

from datetime import date
from decimal import Decimal
from typing import cast

from django.db.models import Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import CompanyExpense, CompanyWithdrawal, TaxYearNote
from ..utils import DateRangeHelper, RevenueCalculator, TaxYearContextBuilder
from ..utils.tax_context_builder import available_data_years
from ..utils.practice_days import WorkdayAuditCalculator
from ..utils.view_helpers import get_year_from_request


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
        return JsonResponse({"error": _("No practice selected")}, status=400)

    try:
        year = int(request.POST.get("year", 0))
    except TypeError, ValueError:
        return JsonResponse({"error": _("Invalid year")}, status=400)

    if not (1900 <= year <= 2100):
        return JsonResponse({"error": _("Invalid year")}, status=400)

    note_text = request.POST.get("note", "").strip()

    defaults: dict = {"allocation_note": note_text}

    raw_amount = request.POST.get("settlement_amount", "").strip()
    if raw_amount != "":
        try:
            from decimal import Decimal, InvalidOperation

            defaults["settlement_amount"] = Decimal(raw_amount.replace(",", "."))
        except InvalidOperation:
            return JsonResponse({"error": _("Invalid amount")}, status=400)
    elif "settlement_amount" in request.POST:
        defaults["settlement_amount"] = None

    raw_date = request.POST.get("settlement_date", "").strip()
    if raw_date != "":
        from datetime import date as _date

        try:
            defaults["settlement_date"] = _date.fromisoformat(raw_date)
        except ValueError:
            return JsonResponse({"error": _("Invalid date")}, status=400)
    elif "settlement_date" in request.POST:
        defaults["settlement_date"] = None

    obj, _created = TaxYearNote.objects.update_or_create(
        practice=practice,
        year=year,
        defaults=defaults,
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

    available_years = available_data_years(practice) if practice else []

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
    current_quarter = DateRangeHelper.get_quarter_for_date(today)[0]

    quarters = []
    for q in range(1, 5):
        start, end = DateRangeHelper.get_quarter_range(year, q)

        # Same paid-date rule (with invoice_date fallback) as the year summary,
        # so quarters sum to the year total
        revenue = RevenueCalculator.get_paid_revenue_for_range(start, end, practice=practice)

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

    available_years = available_data_years(practice, include_expenses=False) or [today.year]

    tax_note = (
        TaxYearNote.objects.filter(practice=practice, year=year).first() if practice else None
    )
    settlement_amount = tax_note.settlement_amount if tax_note else None
    settlement_date = tax_note.settlement_date if tax_note else None
    net_tax_position = total_tax_paid + settlement_amount if settlement_amount is not None else None

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
            "settlement_amount": settlement_amount,
            "settlement_date": settlement_date,
            "net_tax_position": net_tax_position,
            "save_note_url": reverse("save_tax_year_note"),
        },
    )
