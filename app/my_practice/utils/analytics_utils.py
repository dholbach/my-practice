"""
Analytics utilities for generating charts and statistics.
Refactored into cohesive classes for better organization and testability.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from django.utils.translation import gettext as _

from ..models import (
    Client,
    CompanyExpense,
    CompanyWithdrawal,
    Invoice,
    InvoiceItem,
    Session,
)
from . import (
    DateRangeHelper,
    RevenueCalculator,
    count_sessions,
    format_month_key,
    format_month_label,
)


def _resolve_month_range(
    start_year: int = 2020,
    end_date: date | None = None,
    start_date: date | None = None,
) -> tuple[date, date]:
    """
    Resolve the (start_date, end_date) bounds for a monthly trend series.

    Only shows complete months — excludes the current partial month so the
    last data point isn't anomalously low (same guard as get_capacity_trends).
    """
    if end_date is None:
        end_date = timezone.localdate()

    from datetime import timedelta

    first_of_current_month = timezone.localdate().replace(day=1)
    if end_date >= first_of_current_month:
        end_date = first_of_current_month - timedelta(days=1)

    if start_date is None:
        start_date = date(start_year, 1, 1)

    return start_date, end_date


def _build_monthly_series(
    monthly_totals: dict,
    start_date: date,
    end_date: date,
    value_key: str = "value",
) -> list[dict]:
    """
    Build a continuous month-by-month list (gaps filled with 0) from a
    pre-aggregated {"YYYY-MM": value} dict, so callers only need a single
    grouped DB query instead of one query per month.

    Returns:
        list: Monthly data with {month, month_name, year, value_key, date}
    """
    monthly_data = []
    current_date = start_date

    while current_date <= end_date:
        month_key = format_month_key(current_date)
        value = monthly_totals.get(month_key, 0)

        monthly_data.append(
            {
                "month": format_month_label(month_key, "short"),
                "month_name": current_date.strftime("%B"),
                "year": current_date.year,
                value_key: float(value),
                "date": current_date,
            }
        )

        # Move to next month
        current_date = DateRangeHelper.add_months(current_date, 1)

    return monthly_data


def _get_year_financials(
    year: int,
    today: date,
    start_date: date,
    end_date: date,
    practice=None,
) -> tuple["Decimal", "Decimal", "Decimal"]:
    """
    Return (revenue, expenses, withdrawals) for a single calendar year.

    Centralises the date-boundary logic and three querysets that were
    duplicated across RevenueAnalyzer.get_yearly_comparison() and
    ProfitCalculator.calculate_yearly().
    """
    year_start = date(year, 1, 1) if year > start_date.year else start_date
    if year < today.year:
        year_end = date(year, 12, 31)
    elif year == today.year:
        year_end = today  # Use today for current year to avoid future dates
    else:
        year_end = end_date

    revenue = RevenueCalculator.get_paid_revenue_for_range(year_start, year_end, practice=practice)

    # Expenses dated 31.12. each year — filter by year only
    expense_qs = CompanyExpense.objects.filter(date__year=year)
    if practice:
        expense_qs = expense_qs.filter(practice=practice)
    expenses = expense_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    # Withdrawals — year filter for consistency with expenses
    withdrawal_qs = CompanyWithdrawal.objects.filter(date__year=year)
    if practice:
        withdrawal_qs = withdrawal_qs.filter(practice=practice)
    withdrawals = withdrawal_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    return revenue, expenses, withdrawals


def get_yearly_financials_series(
    start_year: int = 2020,
    start_date: date | None = None,
    end_date: date | None = None,
    practice=None,
) -> list[dict]:
    """
    Per-year {year, revenue, expenses, withdrawals} series (Decimal values).

    Computes each year's three queries exactly once. Callers that need both
    RevenueAnalyzer.get_yearly_comparison() and ProfitCalculator.calculate_yearly()
    for the same range (e.g. AnalyticsDashboardBuilder) should compute this once
    and pass it to both via their `yearly_financials` argument, instead of each
    method looping the years independently.
    """
    today = timezone.localdate()
    if end_date is None:
        end_date = today
    if start_date is None:
        start_date = date(start_year, 1, 1)

    series = []
    for year in range(start_date.year, end_date.year + 1):
        revenue, expenses, withdrawals = _get_year_financials(
            year, today, start_date, end_date, practice
        )
        series.append(
            {
                "year": year,
                "revenue": revenue,
                "expenses": expenses,
                "withdrawals": withdrawals,
            }
        )
    return series


class RevenueAnalyzer:
    """Handles all revenue-related calculations and analysis."""

    @staticmethod
    def get_monthly_trends(start_year=2020, end_date=None, start_date=None, practice=None):
        """
        Get monthly revenue data from start_date (or start_year) to end_date.
        Based on payment date (paid_date) for tax purposes.
        Falls back to invoice_date if paid_date is null.
        Returns list of {month, revenue, year} dicts.

        Uses a single grouped query (rather than one query per month) by
        computing an effective_date = paid_date or invoice_date per invoice.

        Args:
            practice: Practice instance for multi-practice filtering
        """
        start_date, end_date = _resolve_month_range(start_year, end_date, start_date)

        qs = (
            Invoice.objects.filter(status="paid")
            .annotate(effective_date=Coalesce("paid_date", "invoice_date"))
            .filter(effective_date__gte=start_date, effective_date__lte=end_date)
        )
        if practice:
            qs = qs.filter(practice=practice)

        rows = (
            qs.annotate(month=TruncMonth("effective_date"))
            .values("month")
            .annotate(total=Sum("total"))
        )
        monthly_totals = {
            row["month"].strftime("%Y-%m"): row["total"] for row in rows if row["month"]
        }

        return _build_monthly_series(monthly_totals, start_date, end_date, value_key="revenue")

    @staticmethod
    def get_days_to_payment_trends(months: int = 24, practice=None) -> list[dict]:
        """
        Average days from invoice_date to paid_date, grouped by month (paid_date).

        Returns list of {month, year, avg_days, count} dicts, oldest first,
        covering only months that have at least one paid invoice.

        Args:
            months: How many months back to look (default 24)
            practice: Practice instance for multi-practice filtering
        """
        today = timezone.localdate()
        start = DateRangeHelper.add_months(date(today.year, today.month, 1), -(months - 1))

        qs = Invoice.objects.filter(
            status="paid",
            paid_date__isnull=False,
            paid_date__gte=start,
        ).annotate(
            delta=ExpressionWrapper(
                F("paid_date") - F("invoice_date"),
                output_field=DurationField(),
            ),
            month=TruncMonth("paid_date"),
        )
        if practice:
            qs = qs.filter(practice=practice)

        rows = (
            qs.values("month").annotate(avg_delta=Avg("delta"), count=Count("id")).order_by("month")
        )

        result = []
        for row in rows:
            month_date = row["month"].date() if hasattr(row["month"], "date") else row["month"]
            avg_delta = row["avg_delta"]
            # avg_delta is a timedelta when averaging DurationField
            avg_days = round(avg_delta.total_seconds() / 86400, 1) if avg_delta else 0.0
            result.append(
                {
                    "month": format_month_label(format_month_key(month_date), "short"),
                    "year": month_date.year,
                    "avg_days": avg_days,
                    "count": row["count"],
                }
            )
        return result

    @staticmethod
    def get_yearly_comparison(
        start_year=2020, start_date=None, end_date=None, practice=None, yearly_financials=None
    ):
        """
        Get yearly comparison of revenue vs withdrawals vs expenses.
        Returns list of {year, revenue, expenses, withdrawals, remaining} dicts.

        Args:
            practice: Practice instance for multi-practice filtering
            yearly_financials: Optional pre-computed get_yearly_financials_series()
                result, to avoid recomputing when the caller also needs
                ProfitCalculator.calculate_yearly() for the same range
        """
        if yearly_financials is None:
            yearly_financials = get_yearly_financials_series(
                start_year, start_date, end_date, practice
            )

        comparison_data = []
        for item in yearly_financials:
            revenue, expenses, withdrawals = item["revenue"], item["expenses"], item["withdrawals"]
            remaining = revenue - expenses - withdrawals
            comparison_data.append(
                {
                    "year": item["year"],
                    "revenue": float(revenue),
                    "expenses": float(expenses),
                    "withdrawals": float(withdrawals),
                    "remaining": float(remaining),
                }
            )

        return comparison_data


class SessionAnalyzer:
    """Handles all session-related statistics and analysis."""

    @staticmethod
    def get_type_distribution(practice=None):
        """
        Get distribution of session types from InvoiceItems.
        Returns dict with counts and percentages.

        Args:
            practice: Practice instance for multi-practice filtering
        """

        # Get all non-cancelled invoice items
        base_qs = InvoiceItem.objects.filter(session__cancelled=False)
        if practice:
            base_qs = base_qs.filter(invoice__practice=practice)
        total_items = base_qs.count()

        if total_items == 0:
            return {
                "total": 0,
                "types": [],
            }

        # Count by session duration / service type
        service_counts = {}

        # 60min sessions
        count_60 = base_qs.filter(session__duration=60).count()
        if count_60 > 0:
            service_counts[_("60-min sessions")] = {
                "count": count_60,
                "percentage": round((count_60 / total_items) * 100, 1),
            }

        # 90min sessions
        count_90 = base_qs.filter(session__duration=90).count()
        if count_90 > 0:
            service_counts[_("90-min sessions")] = {
                "count": count_90,
                "percentage": round((count_90 / total_items) * 100, 1),
            }

        # Group sessions
        count_group = base_qs.filter(group_size__gt=1).count()
        if count_group > 0:
            service_counts[_("Group sessions")] = {
                "count": count_group,
                "percentage": round((count_group / total_items) * 100, 1),
            }

        # Check-in sessions
        count_checkin = base_qs.filter(service_type__code__icontains="check").count()
        if count_checkin > 0:
            service_counts["Check-Ins"] = {
                "count": count_checkin,
                "percentage": round((count_checkin / total_items) * 100, 1),
            }

        # Sort by count descending
        sorted_types = dict(
            sorted(service_counts.items(), key=lambda x: x[1]["count"], reverse=True)
        )

        return {
            "total": total_items,
            "types": sorted_types,
        }

    @staticmethod
    def get_busiest_months(start_year=2020, practice=None):
        """
        Get session counts per month to identify busiest periods from InvoiceItems.
        Uses InvoiceItems as data source.
        Returns list of {month, session_count} dicts sorted by count.

        Args:
            practice: Practice instance for multi-practice filtering
        """
        month_sessions = defaultdict(float)

        # Get from InvoiceItems - group by month first
        items_qs = InvoiceItem.objects.filter(
            session__session_date__year__gte=start_year
        ).select_related("invoice", "session", "service_type")
        if practice:
            items_qs = items_qs.filter(invoice__practice=practice)
        invoice_items = items_qs

        # Group items by month for proper session counting
        month_items: dict[str, list] = defaultdict(list)
        for item in invoice_items:
            month_key = format_month_key(item.session.session_date)
            month_items[month_key].append(item)

        # Use centralized session counting (handles duration, quantity, and Ausfall)
        # therapist_hours=True: group sessions counted once per therapist, not per participant
        for month_key, items in month_items.items():
            hours = count_sessions(items, exclude_cancellations=True, therapist_hours=True)
            month_sessions[month_key] = hours

        # Convert to list and sort
        result = []
        for month_key, hours in month_sessions.items():
            year, month = month_key.split("-")
            month_date = date(int(year), int(month), 1)
            # Revenue: sum item totals for paid invoices only (exclude cancellations)
            items_in_month = month_items[month_key]
            revenue = sum(
                float(item.total) for item in items_in_month if item.invoice.status == "paid"
            )
            result.append(
                {
                    "month": format_month_label(month_key, "medium"),
                    "month_date": month_date,
                    "year": int(year),
                    "session_hours": round(hours, 1),
                    "revenue": round(revenue),
                }
            )

        # Sort by revenue descending (months with highest earnings first)
        result.sort(key=lambda x: x["revenue"], reverse=True)  # type: ignore[arg-type,return-value]

        return result

    @staticmethod
    def get_cancellation_trends(months: int = 24, practice=None) -> list[dict]:
        """
        Get monthly cancellation rates for the last N months.

        Returns list of {month, year, date, total, cancelled, rate} dicts,
        oldest first, covering only months that have at least one session.

        Args:
            months: How many months back to look (default 24)
            practice: Practice instance for multi-practice filtering
        """
        today = timezone.localdate()
        start = DateRangeHelper.add_months(date(today.year, today.month, 1), -(months - 1))

        qs = Session.objects.filter(session_date__gte=start).annotate(
            month=TruncMonth("session_date")
        )
        if practice:
            qs = qs.filter(client__practice=practice)

        rows = (
            qs.values("month")
            .annotate(
                total=Count("id"),
                cancelled=Count("id", filter=Q(cancelled=True)),
            )
            .order_by("month")
        )

        result = []
        for row in rows:
            month_date = row["month"].date() if hasattr(row["month"], "date") else row["month"]
            total = row["total"]
            cancelled = row["cancelled"]
            rate = round(cancelled / total * 100, 1) if total else 0.0
            result.append(
                {
                    "month": format_month_label(format_month_key(month_date), "short"),
                    "year": month_date.year,
                    "date": month_date,
                    "total": total,
                    "cancelled": cancelled,
                    "rate": rate,
                }
            )
        return result


class ClientAnalyzer:
    """Handles client-related statistics and rankings."""

    @staticmethod
    def get_top_by_revenue(limit=10, practice=None):
        """
        Get top clients ranked by total revenue (paid invoices).
        Returns list of {client, total_revenue, invoice_count, session_hours} dicts.
        Uses centralized session counting for accurate hour calculations.

        Args:
            practice: Practice instance for multi-practice filtering
        """
        # Get clients with revenue aggregation
        clients_qs = Client.objects.annotate(
            total_revenue=Sum("invoices__total", filter=Q(invoices__status="paid")),
            invoice_count=Count("invoices", filter=Q(invoices__status="paid"), distinct=True),
        ).filter(total_revenue__gt=0)
        if practice:
            clients_qs = clients_qs.filter(practice=practice)
        clients_with_revenue = clients_qs.order_by("-total_revenue")[:limit]

        # Format results with proper session counting
        result = []
        for client in clients_with_revenue:
            # Get all invoice items for this client (paid invoices only)
            items = InvoiceItem.objects.filter(
                invoice__client=client, invoice__status="paid"
            ).select_related("session", "service_type")

            # Use centralized session counting (handles duration, quantity, and Ausfall)
            session_hours = count_sessions(items, exclude_cancellations=True)

            result.append(
                {
                    "client": client,
                    "total_revenue": float(client.total_revenue),
                    "invoice_count": client.invoice_count,
                    "session_hours": round(session_hours, 1),
                }
            )

        return result


class ExpenseAnalyzer:
    """Handles expense-related calculations and breakdowns."""

    @staticmethod
    def get_monthly_trends(start_year=2020, end_date=None, start_date=None, practice=None):
        """
        Get monthly expense data from start_date (or start_year) to end_date.
        Note: All expenses are dated 31.12. of each year, so we aggregate by year
        (single grouped query) and distribute equally across all months of that
        year for chart display.
        Returns list of {month, expenses, year} dicts.

        Args:
            practice: Practice instance for multi-practice filtering
        """
        start_date, end_date = _resolve_month_range(start_year, end_date, start_date)

        expense_qs = CompanyExpense.objects.filter(
            date__year__gte=start_date.year, date__year__lte=end_date.year
        )
        if practice:
            expense_qs = expense_qs.filter(practice=practice)
        year_totals = dict(
            expense_qs.values_list("date__year")
            .annotate(total=Sum("amount"))
            .values_list("date__year", "total")
        )

        monthly_totals = {}
        current_date = start_date
        while current_date <= end_date:
            year_total = year_totals.get(current_date.year) or Decimal("0")
            monthly_totals[format_month_key(current_date)] = year_total / 12
            current_date = DateRangeHelper.add_months(current_date, 1)

        return _build_monthly_series(monthly_totals, start_date, end_date, value_key="expenses")

    @staticmethod
    def get_expense_breakdown(practice=None):
        """
        Get expense breakdown by category with totals and percentages.
        Returns dict with category breakdown.

        Args:
            practice: Practice instance for multi-practice filtering
        """
        # Start with all expenses (filtered by practice if provided)
        expense_qs = CompanyExpense.objects.all()
        if practice:
            expense_qs = expense_qs.filter(practice=practice)
        total_expenses = expense_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")

        if total_expenses == 0:
            return {
                "total": 0,
                "categories": [],
            }

        # Get expenses by category
        category_data = (
            expense_qs.values("category").annotate(total=Sum("amount")).order_by("-total")
        )

        categories = []
        for item in category_data:
            # Get human-readable category name
            category_name = dict(CompanyExpense.CATEGORY_CHOICES).get(
                item["category"], item["category"]
            )

            categories.append(
                {
                    "category": category_name,
                    "category_key": item["category"],
                    "amount": float(item["total"]),
                    "percentage": round((float(item["total"]) / float(total_expenses)) * 100, 1),
                }
            )

        return {
            "total": float(total_expenses),
            "categories": categories,
        }


class ProfitCalculator:
    """Handles profit calculations and financial summaries."""

    @staticmethod
    def calculate_yearly(
        start_year=None,
        end_year=None,
        start_date=None,
        end_date=None,
        practice=None,
        yearly_financials=None,
    ):
        """
        Calculate profit: Revenue - Expenses
        Returns yearly breakdown with cumulative profit and withdrawals.

        Args:
            practice: Practice instance for multi-practice filtering
            yearly_financials: Optional pre-computed get_yearly_financials_series()
                result, to avoid recomputing when the caller also needs
                RevenueAnalyzer.get_yearly_comparison() for the same range
        """
        today = timezone.localdate()

        if end_date is None:
            end_date = today
        if end_year is None:
            end_year = end_date.year
        if start_year is None:
            start_year = today.year
        if start_date is None:
            start_date = date(start_year, 1, 1)

        if yearly_financials is None:
            yearly_financials = []
            for year in range(start_date.year, end_year + 1):
                revenue, expenses, withdrawals = _get_year_financials(
                    year, today, start_date, end_date, practice
                )
                yearly_financials.append(
                    {
                        "year": year,
                        "revenue": revenue,
                        "expenses": expenses,
                        "withdrawals": withdrawals,
                    }
                )

        profit_data = []
        cumulative_profit: float = 0.0

        for item in yearly_financials:
            revenue, expenses = item["revenue"], item["expenses"]
            profit = revenue - expenses
            cumulative_profit += float(profit)

            profit_data.append(
                {
                    "year": item["year"],
                    "revenue": float(revenue),
                    "expenses": float(expenses),
                    "profit": float(profit),
                    "cumulative_profit": round(cumulative_profit, 2),
                    "withdrawals": float(item["withdrawals"]),
                }
            )

        return profit_data
