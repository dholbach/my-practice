"""
Builder for the tax year summary view context.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ..models import CompanyExpense, Invoice, TaxYearNote
from .aggregation_helpers import get_category_breakdown, get_grand_total
from .chart_helpers import format_month_key, format_month_label
from .practice_days import HomeOfficeDayCalculator, PracticeDayCalculator
from .revenue_helpers import RevenueCalculator


def available_data_years(practice, include_expenses: bool = True) -> list[int]:
    """
    Return a descending list of years that have Invoice data for the practice.

    If include_expenses is True (the default), years from CompanyExpense records
    are merged in too — useful for tax views that cover both income and expenses.
    """
    years = {
        d.year for d in Invoice.objects.filter(practice=practice).dates("invoice_date", "year")
    }
    if include_expenses:
        years |= {
            d.year for d in CompanyExpense.objects.filter(practice=practice).dates("date", "year")
        }
    return sorted(years, reverse=True)


@dataclass
class PracticeSplitCalc:
    """Revenue and session-day split ratios for this practice in a multi-practice context."""

    revenue_share: Decimal
    session_share: Decimal
    total_revenue_all: Decimal
    this_revenue: Decimal
    total_session_days_all: int
    this_session_days: int


class TaxYearContextBuilder:
    """
    Assembles the context dict for the tax year summary view.

    Usage:
        builder = TaxYearContextBuilder(year, practice, user)
        context = builder.build(expense_sort=request.GET.get("sort", "date"))
    """

    def __init__(self, year: int, practice: Any, user: Any) -> None:
        self.year = year
        self.practice = practice
        self.user = user
        self._practice_split = self._compute_practice_split()
        # Set by _build_deductions(); used by _build_split_context()
        self._fahrtkosten_deduction = Decimal("0")
        self._home_office_deduction = Decimal("0")

    # ── Public API ────────────────────────────────────────────────────────────

    def build(self, expense_sort: str = "date") -> dict:
        context: dict = {"year": self.year}
        context.update(self._build_revenue())
        context.update(self._build_expenses(expense_sort))
        context.update(self._build_deductions())
        context.update(self._build_available_years())
        context.update(self._build_split_context())
        context["gross_profit"] = (
            Decimal(str(context["total_revenue"]))
            - Decimal(context["total_expenses"])
            - self._fahrtkosten_deduction
            - self._home_office_deduction
        )
        context["tax_year_note"] = (
            TaxYearNote.objects.filter(practice=self.practice, year=self.year).first()
            if self.practice
            else None
        )
        return context

    # ── Private builders ──────────────────────────────────────────────────────

    def _build_revenue(self) -> dict:
        paid_invoices = (
            Invoice.objects.filter(
                RevenueCalculator.build_paid_date_filter(self.year),
                status="paid",
                practice=self.practice,
            )
            .select_related("client")
            .order_by("paid_date", "invoice_date")
        )
        year_stats = RevenueCalculator.get_year_revenue(
            self.year, use_paid_date=True, practice=self.practice
        )

        monthly_revenue: dict[str, dict[str, Any]] = {}
        for invoice in paid_invoices:
            payment_date = invoice.paid_date or invoice.invoice_date
            month_key = format_month_key(payment_date)
            if month_key not in monthly_revenue:
                monthly_revenue[month_key] = {
                    "month": format_month_label(month_key, "long"),
                    "amount": Decimal("0"),
                    "count": 0,
                }
            monthly_revenue[month_key]["amount"] += invoice.total
            monthly_revenue[month_key]["count"] += 1

        return {
            "paid_invoices": paid_invoices,
            "total_revenue": year_stats["total"],
            "invoice_count": year_stats["count"],
            "monthly_revenue": [monthly_revenue[k] for k in sorted(monthly_revenue)],
        }

    def _build_expenses(self, expense_sort: str) -> dict:
        order = (
            ["-is_filed_in_tax_return", "date", "category"]
            if expense_sort == "se"
            else ["date", "category"]
        )
        expenses = CompanyExpense.objects.filter(
            date__year=self.year, is_tax_deductible=True, practice=self.practice
        ).order_by(*order)

        return {
            "expenses": expenses,
            "total_expenses": get_grand_total(expenses),
            "expense_count": expenses.count(),
            "expense_by_category": get_category_breakdown(
                expenses, category_choices=dict(CompanyExpense.CATEGORY_CHOICES)
            ),
            "expense_sort": expense_sort,
        }

    def _build_deductions(self) -> dict:
        fahrtkosten = (
            PracticeDayCalculator(self.practice, self.year).calculate() if self.practice else None
        )
        self._fahrtkosten_deduction = (
            Decimal(str(fahrtkosten.deduction_total))
            if fahrtkosten and fahrtkosten.is_configured
            else Decimal("0")
        )

        home_office = (
            HomeOfficeDayCalculator(self.practice, self.year).calculate() if self.practice else None
        )
        self._home_office_deduction = (
            Decimal(str(home_office.deduction_total))
            if home_office and home_office.is_configured
            else Decimal("0")
        )

        return {
            "fahrtkosten": fahrtkosten,
            "fahrtkosten_deduction": self._fahrtkosten_deduction,
            "home_office": home_office,
            "home_office_deduction": self._home_office_deduction,
        }

    def _build_available_years(self) -> dict:
        return {"available_years": available_data_years(self.practice)}

    def _build_split_context(self) -> dict:
        ps = self._practice_split
        fd, hd = self._fahrtkosten_deduction, self._home_office_deduction
        return {
            "show_multi_practice_allocation_notice": ps is not None,
            "active_practice_count": self.user.practices.filter(is_active=True).count(),
            "practice_split": ps,
            "home_office_split_revenue": (
                (hd * ps.revenue_share).quantize(Decimal("0.01")) if ps else None
            ),
            "home_office_split_sessions": (
                (hd * ps.session_share).quantize(Decimal("0.01")) if ps else None
            ),
            "fahrtkosten_split_revenue": (
                (fd * ps.revenue_share).quantize(Decimal("0.01")) if ps else None
            ),
            "fahrtkosten_split_sessions": (
                (fd * ps.session_share).quantize(Decimal("0.01")) if ps else None
            ),
            "revenue_share_pct": (
                (ps.revenue_share * 100).quantize(Decimal("0.1")) if ps else None
            ),
            "session_share_pct": (
                (ps.session_share * 100).quantize(Decimal("0.1")) if ps else None
            ),
        }

    def _compute_practice_split(self) -> PracticeSplitCalc | None:
        from ..models import Session

        active_practices = list(self.user.practices.filter(is_active=True))
        if len(active_practices) <= 1:
            return None

        total_revenue_all = Decimal("0")
        this_revenue = Decimal("0")
        for p in active_practices:
            rev = RevenueCalculator.get_year_revenue(self.year, use_paid_date=True, practice=p)[
                "total"
            ]
            total_revenue_all += rev
            if p.pk == self.practice.pk:
                this_revenue = rev

        total_session_days_all = 0
        this_session_days = 0
        for p in active_practices:
            days = (
                Session.objects.filter(
                    client__practice=p,
                    session_date__year=self.year,
                    cancelled=False,
                )
                .dates("session_date", "day")
                .count()
            )
            total_session_days_all += days
            if p.pk == self.practice.pk:
                this_session_days = days

        revenue_share = (
            (this_revenue / total_revenue_all).quantize(Decimal("0.0001"))
            if total_revenue_all > 0
            else Decimal("1")
        )
        session_share = (
            (Decimal(str(this_session_days)) / Decimal(str(total_session_days_all))).quantize(
                Decimal("0.0001")
            )
            if total_session_days_all > 0
            else Decimal("1")
        )

        return PracticeSplitCalc(
            revenue_share=revenue_share,
            session_share=session_share,
            total_revenue_all=total_revenue_all,
            this_revenue=this_revenue,
            total_session_days_all=total_session_days_all,
            this_session_days=this_session_days,
        )
