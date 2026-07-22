"""
Analytics utilities for generating charts and statistics.
Refactored into cohesive classes for better organization and testability.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Avg, Count, ExpressionWrapper, DurationField, F, Q, Sum
from django.db.models.functions import TruncMonth
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


def _get_monthly_aggregation(
    queryset_filter_func,
    value_key="value",
    start_year=2020,
    end_date=None,
    start_date=None,
):
    """
    Generic helper for aggregating data by month.

    Args:
        queryset_filter_func: Function that takes (year, month) and returns aggregated value
        value_key: Key name for the value in output (e.g., "revenue", "expenses")
        start_year: Starting year for data collection
        end_date: End date (defaults to today)
        start_date: Start date (overrides start_year if provided)

    Returns:
        list: Monthly data with {month, month_name, year, value_key, date}
    """
    if end_date is None:
        end_date = date.today()

    # Only show complete months — exclude the current partial month so the last
    # data point isn't anomalously low (same guard as get_capacity_trends).
    from datetime import timedelta

    first_of_current_month = date.today().replace(day=1)
    if end_date >= first_of_current_month:
        end_date = first_of_current_month - timedelta(days=1)

    if start_date is None:
        start_date = date(start_year, 1, 1)

    monthly_data = []
    current_date = start_date

    while current_date <= end_date:
        # Get aggregated value for this month
        value = queryset_filter_func(current_date.year, current_date.month)

        month_key = format_month_key(current_date)
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


class RevenueAnalyzer:
    """Handles all revenue-related calculations and analysis."""

    @staticmethod
    def get_monthly_trends(start_year=2020, end_date=None, start_date=None, practice=None):
        """
        Get monthly revenue data from start_date (or start_year) to end_date.
        Based on payment date (paid_date) for tax purposes.
        Falls back to invoice_date if paid_date is null.
        Returns list of {month, revenue, year} dicts.

        Args:
            practice: Practice instance for multi-practice filtering
        """

        def get_month_revenue(year, month):
            """Get revenue for a specific month using centralized calculator."""
            return RevenueCalculator.get_month_revenue(
                year, month, use_paid_date=True, practice=practice
            )["total"]

        return _get_monthly_aggregation(
            get_month_revenue,
            value_key="revenue",
            start_year=start_year,
            end_date=end_date,
            start_date=start_date,
        )

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
        today = date.today()
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
    def get_yearly_comparison(start_year=2020, start_date=None, end_date=None, practice=None):
        """
        Get yearly comparison of revenue vs withdrawals vs expenses.
        Returns list of {year, revenue, expenses, withdrawals, remaining} dicts.

        Args:
            practice: Practice instance for multi-practice filtering
        """
        today = date.today()

        if end_date is None:
            end_date = today
        if start_date is None:
            start_date = date(start_year, 1, 1)

        # Get years from start_date to end_date
        years = list(range(start_date.year, end_date.year + 1))
        comparison_data = []

        for year in years:
            revenue, expenses, withdrawals = _get_year_financials(
                year, today, start_date, end_date, practice
            )
            remaining = revenue - expenses - withdrawals
            comparison_data.append(
                {
                    "year": year,
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
        ).select_related("invoice", "session")
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
        today = date.today()
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
            items = InvoiceItem.objects.filter(invoice__client=client, invoice__status="paid")

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
        and distribute across all months of that year for chart display.
        Returns list of {month, expenses, year} dicts.

        Args:
            practice: Practice instance for multi-practice filtering
        """

        def get_year_expenses(year, month):
            """
            Get all expenses for the year and distribute across months.
            Since all expenses are dated 31.12., we filter by year only.
            """
            # Get total expenses for the entire year
            expense_qs = CompanyExpense.objects.filter(date__year=year)
            if practice:
                expense_qs = expense_qs.filter(practice=practice)
            year_total = expense_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")

            # Distribute equally across 12 months for chart visualization
            return year_total / 12

        return _get_monthly_aggregation(
            get_year_expenses,
            value_key="expenses",
            start_year=start_year,
            end_date=end_date,
            start_date=start_date,
        )

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
        start_year=None, end_year=None, start_date=None, end_date=None, practice=None
    ):
        """
        Calculate profit: Revenue - Expenses
        Returns yearly breakdown with cumulative profit and withdrawals.

        Args:
            practice: Practice instance for multi-practice filtering
        """
        today = date.today()

        if end_date is None:
            end_date = today
        if end_year is None:
            end_year = end_date.year
        if start_year is None:
            start_year = today.year
        if start_date is None:
            start_date = date(start_year, 1, 1)

        profit_data = []
        cumulative_profit: float = 0.0

        years = list(range(start_date.year, end_year + 1))

        for year in years:
            revenue, expenses, withdrawals = _get_year_financials(
                year, today, start_date, end_date, practice
            )
            profit = revenue - expenses
            cumulative_profit += float(profit)

            profit_data.append(
                {
                    "year": year,
                    "revenue": float(revenue),
                    "expenses": float(expenses),
                    "profit": float(profit),
                    "cumulative_profit": round(cumulative_profit, 2),
                    "withdrawals": float(withdrawals),
                }
            )

        return profit_data
