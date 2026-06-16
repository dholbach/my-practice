"""
Analytics Dashboard Builder - Refactored from 185-line function.
Handles analytics data preparation and aggregation for the dashboard view.
"""

from collections import defaultdict
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db.models import Min

from ..models import CompanyExpense, CompanyWithdrawal, Invoice, TimeOff
from ..utils.capacity_helpers import get_capacity_trends
from ..utils.timeoff_helpers import (
    calculate_timeoff_for_period,
    calculate_timeoff_for_year,
)


class AnalyticsDashboardBuilder:
    """
    Build analytics dashboard context data.

    Separates concerns:
    - Date range parsing
    - Data fetching from analyzers
    - TimeOff calculations
    - Context preparation
    """

    # Fallback returned when selected period has no time-off data
    _TIMEOFF_ZERO: dict = {
        "timeoff_label": "-",
        "total_days_off": 0,
        "total_weeks_off": 0.0,
        "total_workdays_off": 0,
        "yearly_timeoff": [],
    }

    def __init__(
        self,
        request,
        period: str = "all",
        custom_start: str | None = None,
        custom_end: str | None = None,
    ):
        """
        Initialize dashboard builder with period filters.

        Args:
            request: HttpRequest object for practice scoping
            period: Time period filter ('all', 'month', 'quarter', 'year', 'custom')
            custom_start: Custom start date (ISO format)
            custom_end: Custom end date (ISO format)
        """
        self.request = request
        self.practice = getattr(request, "current_practice", None)  # Get practice from middleware
        self.period = period
        self.custom_start = custom_start
        self.custom_end = custom_end
        self.today = date.today()

        # Will be set by _parse_date_range()
        self.start_date: date | None = None
        self.end_date: date | None = None
        self.start_year: int = 2017

    def build_context(self) -> dict:
        """
        Build complete dashboard context.

        Returns:
            Dictionary with all dashboard data for template rendering
        """
        # Import analyzers locally to avoid circular import
        # (analytics_utils.py imports from utils/__init__.py)
        from .analytics_utils import (
            ClientAnalyzer,
            ExpenseAnalyzer,
            ProfitCalculator,
            RevenueAnalyzer,
            SessionAnalyzer,
        )

        # Store as instance variables for other methods to use
        self.RevenueAnalyzer = RevenueAnalyzer
        self.SessionAnalyzer = SessionAnalyzer
        self.ClientAnalyzer = ClientAnalyzer
        self.ExpenseAnalyzer = ExpenseAnalyzer
        self.ProfitCalculator = ProfitCalculator

        self._parse_date_range()

        comparison = self._get_comparison_data()
        return {
            **self._get_trend_data(),
            **self._get_distribution_data(),
            **self._get_client_data(),
            **comparison,
            **self._get_timeoff_data(),
            **self._get_filter_data(),
            "seasonality_data": self._get_seasonality_from_capacity(comparison["capacity_trends"]),
            "cumulative_year_data": self._get_cumulative_year_data(comparison["capacity_trends"]),
        }

    def _parse_date_range(self):
        """Parse period filter into start_date, end_date, start_year."""
        if self.period == "month":
            self.start_date = self.today - relativedelta(months=1)
            self.end_date = self.today
            self.start_year = self.start_date.year

        elif self.period == "quarter":
            self.start_date = self.today - relativedelta(months=3)
            self.end_date = self.today
            self.start_year = self.start_date.year

        elif self.period == "year":
            self.start_date = self.today - relativedelta(years=1)
            self.end_date = self.today
            self.start_year = self.start_date.year

        elif self.period == "custom" and self.custom_start and self.custom_end:
            try:
                self.start_date = date.fromisoformat(self.custom_start)
                self.end_date = date.fromisoformat(self.custom_end)
                self.start_year = self.start_date.year
            except ValueError, TypeError:
                # Invalid dates, fall back to all-time
                self._set_all_time()

        else:
            # All-time: 2017 to today
            self._set_all_time()

    def _set_all_time(self):
        """Set date range to all-time (earliest data year onwards)."""
        self.period = "all"
        self.start_year = self._get_earliest_data_year()
        self.start_date = None
        self.end_date = None

    def _get_earliest_data_year(self) -> int:
        """Return the earliest year with any financial data for this practice."""
        practice_filter = {"practice": self.practice} if self.practice else {}
        candidates = []
        for model, field in (
            (Invoice, "invoice_date"),
            (CompanyExpense, "date"),
            (CompanyWithdrawal, "date"),
        ):
            earliest = model.objects.filter(**practice_filter).aggregate(v=Min(field))["v"]
            if earliest:
                candidates.append(earliest.year)
        return min(candidates) if candidates else self.today.year

    @property
    def _common_kwargs(self) -> dict:
        """Shared kwargs forwarded to all analyzer methods."""
        return {
            "start_year": self.start_year,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "practice": self.practice,
        }

    def _get_trend_data(self) -> dict:
        """Get revenue and expense trend data."""
        revenue_trends = self.RevenueAnalyzer.get_monthly_trends(**self._common_kwargs)
        expense_trends = self.ExpenseAnalyzer.get_monthly_trends(**self._common_kwargs)
        days_to_payment = self.RevenueAnalyzer.get_days_to_payment_trends(practice=self.practice)

        # Calculate yearly totals from monthly data
        yearly_totals = {}
        for item in revenue_trends:
            year = item["year"]
            if year not in yearly_totals:
                yearly_totals[year] = 0
            yearly_totals[year] += item["revenue"]

        yearly_data = [
            {"year": year, "revenue": round(revenue, 2)}
            for year, revenue in sorted(yearly_totals.items())
        ]

        max_revenue = max([item["revenue"] for item in revenue_trends]) if revenue_trends else 0

        return {
            "revenue_trends": revenue_trends,
            "expense_trends": expense_trends,
            "max_revenue": max_revenue,
            "yearly_data": yearly_data,
            "days_to_payment": days_to_payment,
        }

    def _get_distribution_data(self) -> dict:
        """Get session and expense distribution data."""
        return {
            "session_distribution": self.SessionAnalyzer.get_type_distribution(
                practice=self.practice
            ),
            "expense_distribution": self.ExpenseAnalyzer.get_expense_breakdown(
                practice=self.practice
            ),
            "cancellation_trends": self.SessionAnalyzer.get_cancellation_trends(
                practice=self.practice
            ),
        }

    def _get_client_data(self) -> dict:
        """Get client-related analytics."""
        # For busiest months, use 2020+ for all-time to reduce noise
        busiest_start_year = self.start_year if self.period != "all" else 2020

        all_months = self.SessionAnalyzer.get_busiest_months(
            start_year=busiest_start_year, practice=self.practice
        )
        busiest_years = sorted({m["year"] for m in all_months})

        return {
            "top_clients": self.ClientAnalyzer.get_top_by_revenue(limit=10, practice=self.practice),
            "busiest_months": all_months[:20],  # Top 20 busiest months
            "busiest_years": busiest_years,
        }

    def _get_cumulative_year_data(self, capacity_trends: list) -> dict:
        """
        Build monthly booked-hours per calendar month (Jan–Dec) for the
        last 3 years with data, plus an average line — for a year-overlay
        line chart.

        Returns:
            dict: {years: [int], datasets: {str(year): [float|None]*12}, average: [float|None]*12}
                  None entries represent months without data (future months in current year).
        """
        from collections import defaultdict

        by_year: dict[int, dict[int, float]] = defaultdict(dict)
        for item in capacity_trends:
            if item["booked_hours"] > 0:
                by_year[item["year"]][item["month_num"]] = item["booked_hours"]

        if not by_year:
            return {}

        years = sorted(by_year.keys())[-4:]

        datasets: dict[str, list] = {}
        for year in years:
            monthly = by_year[year]
            datasets[str(year)] = [
                round(monthly[m], 1) if m in monthly else None for m in range(1, 13)
            ]

        average: list[float | None] = []
        for m_idx in range(12):
            vals = [datasets[str(y)][m_idx] for y in years if datasets[str(y)][m_idx] is not None]
            average.append(round(sum(vals) / len(vals), 1) if vals else None)

        return {"years": years, "datasets": datasets, "average": average}

    def _get_seasonality_from_capacity(self, capacity_trends: list) -> list:
        """
        Derive seasonality (avg capacity % per calendar month) from already-computed
        capacity_trends. This automatically accounts for vacation, capacity period
        changes, and group_size corrections — no extra DB query needed.

        Returns:
            list: 12 items (Jan first), each:
                  {month_name, month_num, avg_capacity_pct, avg_booked_hours,
                   avg_capacity_hours, years_count}
        """
        from collections import defaultdict
        from ..utils.chart_helpers import GERMAN_MONTHS_SHORT

        german_month_names = GERMAN_MONTHS_SHORT

        by_month: dict[int, list] = defaultdict(list)
        for item in capacity_trends:
            by_month[item["month_num"]].append(item)

        result = []
        for m in range(1, 13):
            entries = by_month.get(m, [])
            # Only include months where sessions were actually billed.
            # This excludes pre-practice months (no data yet) and fully
            # vacant months (vacation), so averages reflect normal working months.
            active = [e for e in entries if e["booked_hours"] > 0]
            if active:
                avg_pct = round(sum(e["capacity_percentage"] for e in active) / len(active))
                avg_booked = round(sum(e["booked_hours"] for e in active) / len(active), 1)
                avg_capacity = round(sum(e["capacity_hours"] for e in active) / len(active), 1)
                years_count = len(active)
            else:
                avg_pct, avg_booked, avg_capacity, years_count = 0, 0.0, 0.0, 0
            result.append(
                {
                    "month_name": german_month_names[m - 1],
                    "month_num": m,
                    "avg_capacity_pct": avg_pct,
                    "avg_booked_hours": avg_booked,
                    "avg_capacity_hours": avg_capacity,
                    "years_count": years_count,
                }
            )
        return result

    def _get_comparison_data(self) -> dict:
        """Get financial comparison data (profit, capacity)."""
        return {
            "comparison_data": self.RevenueAnalyzer.get_yearly_comparison(**self._common_kwargs),
            "profit_data": self.ProfitCalculator.calculate_yearly(**self._common_kwargs),
            "capacity_trends": get_capacity_trends(
                start_year=self.start_year,
                start_date=self.start_date,
                end_date=self.end_date,
            ),
        }

    def _get_timeoff_data(self) -> dict:
        """Get time-off statistics and breakdown."""
        # Calculate time-off for selected period
        if self.period in ["quarter", "month", "custom"]:
            if self.start_date is None or self.end_date is None:
                return dict(self._TIMEOFF_ZERO)
            timeoff_result = calculate_timeoff_for_period(self.start_date, self.end_date)
            timeoff_label = self._generate_timeoff_label()
        elif self.period == "year":
            if self.start_date is None:
                return dict(self._TIMEOFF_ZERO)
            timeoff_result = calculate_timeoff_for_year(self.start_date.year)
            timeoff_label = str(self.start_date.year)
        else:
            # For "all", use current year
            timeoff_result = calculate_timeoff_for_year(self.today.year)
            timeoff_label = str(self.today.year)

        # Get yearly breakdown
        yearly_timeoff = self._get_yearly_timeoff_breakdown()

        return {
            "timeoff_label": timeoff_label,
            "total_days_off": timeoff_result["total_days"],
            "total_weeks_off": timeoff_result["total_weeks"],
            "total_workdays_off": timeoff_result["total_workdays"],
            "yearly_timeoff": yearly_timeoff,
        }

    def _generate_timeoff_label(self) -> str:
        """Generate descriptive label for time-off period."""
        if self.start_date is None or self.end_date is None:
            return "-"

        if self.period == "month":
            return self.start_date.strftime("%B %Y")  # e.g., "November 2025"

        elif self.period == "quarter":
            quarter_num = (self.start_date.month - 1) // 3 + 1
            return f"Q{quarter_num} {self.start_date.year}"  # e.g., "Q4 2025"

        else:  # custom
            if self.start_date.year == self.end_date.year:
                if self.start_date.month == 1 and self.end_date.month == 12:
                    return str(self.start_date.year)
                else:
                    return f"{self.start_date.strftime('%b')}-{self.end_date.strftime('%b %Y')}"
            else:
                return f"{self.start_date.strftime('%b %Y')}-{self.end_date.strftime('%b %Y')}"

    def _get_yearly_timeoff_breakdown(self) -> list[dict]:
        """Get time-off breakdown by year and type."""
        # Get all years that have time-off entries
        timeoff_years = sorted(
            set(
                list(TimeOff.objects.values_list("start_date__year", flat=True).distinct())
                + list(TimeOff.objects.values_list("end_date__year", flat=True).distinct())
            ),
            reverse=True,
        )

        yearly_data = []
        for year in timeoff_years:
            year_data = calculate_timeoff_for_year(year)
            type_breakdown = self._get_timeoff_by_type_for_year(year)

            yearly_data.append(
                {
                    "year": year,
                    "total_days": year_data["total_days"],
                    "total_weeks": year_data["total_weeks"],
                    "workdays": year_data["total_workdays"],
                    "vacation": type_breakdown.get("vacation", 0),
                    "training": type_breakdown.get("training", 0),
                    "sick": type_breakdown.get("sick", 0),
                    "holiday": type_breakdown.get("holiday", 0),
                    "other": type_breakdown.get("other", 0),
                }
            )

        return yearly_data

    def _get_timeoff_by_type_for_year(self, year: int) -> dict:
        """Get time-off days broken down by type for a specific year."""
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)

        # Get all timeoff that touches this year
        timeoff_periods = TimeOff.objects.filter(start_date__lte=year_end, end_date__gte=year_start)

        type_days: dict[str, int] = defaultdict(int)

        for t in timeoff_periods:
            # Clamp dates to this year
            actual_start = max(t.start_date, year_start)
            actual_end = min(t.end_date, year_end)
            days = (actual_end - actual_start).days + 1
            type_days[t.type] += days

        return dict(type_days)

    def _get_filter_data(self) -> dict:
        """Get filter parameters for template."""
        return {
            "selected_period": self.period,
            "start_date": (
                self.start_date.isoformat() if self.period == "custom" and self.start_date else ""
            ),
            "end_date": (
                self.end_date.isoformat() if self.end_date and self.period == "custom" else ""
            ),
            "backend_today": self.today.isoformat(),
            "data_start_year": self.start_year,
        }
