"""
Date range utility functions.
Centralized logic for date calculations and range handling.
"""

import calendar
from datetime import date

from dateutil.relativedelta import relativedelta


class DateRangeHelper:
    """
    Consistent date range calculations throughout the application.

    Provides helper methods for common date operations like getting
    month ranges, year ranges, and calculating date offsets.
    """

    @staticmethod
    def get_year_range(year_date: date | int) -> tuple[date, date]:
        """
        Get start and end dates for a year.

        Args:
            year_date: date object or int year

        Returns:
            tuple: (year_start, year_end) as date objects

        Example:
            >>> DateRangeHelper.get_year_range(2025)
            (date(2025, 1, 1), date(2025, 12, 31))
            >>> DateRangeHelper.get_year_range(date(2025, 6, 15))
            (date(2025, 1, 1), date(2025, 12, 31))
        """
        if isinstance(year_date, int):
            year = year_date
        else:
            year = year_date.year

        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        return year_start, year_end

    @staticmethod
    def get_month_range(month_date: date) -> tuple[date, date]:
        """
        Get start and end dates for a month.

        Args:
            month_date: date object (any day in the month)

        Returns:
            tuple: (month_start, month_end) as date objects

        Example:
            >>> DateRangeHelper.get_month_range(date(2025, 2, 15))
            (date(2025, 2, 1), date(2025, 2, 28))
            >>> DateRangeHelper.get_month_range(date(2024, 2, 15))  # Leap year
            (date(2024, 2, 1), date(2024, 2, 29))
        """
        month_start = month_date.replace(day=1)
        last_day = calendar.monthrange(month_date.year, month_date.month)[1]
        month_end = date(month_date.year, month_date.month, last_day)
        return month_start, month_end

    @staticmethod
    def get_first_of_month(month_date: date) -> date:
        """
        Get the first day of the month for a given date.

        Args:
            month_date: date object

        Returns:
            date: First day of the month

        Example:
            >>> DateRangeHelper.get_first_of_month(date(2025, 3, 15))
            date(2025, 3, 1)
        """
        return month_date.replace(day=1)

    @staticmethod
    def get_last_of_month(month_date: date) -> date:
        """
        Get the last day of the month for a given date.

        Args:
            month_date: date object

        Returns:
            date: Last day of the month

        Example:
            >>> DateRangeHelper.get_last_of_month(date(2025, 2, 15))
            date(2025, 2, 28)
        """
        last_day = calendar.monthrange(month_date.year, month_date.month)[1]
        return date(month_date.year, month_date.month, last_day)

    @staticmethod
    def add_months(start_date: date, months: int) -> date:
        """
        Add or subtract months from a date.

        Args:
            start_date: date object
            months: int (positive to add, negative to subtract)

        Returns:
            date: New date with months added/subtracted

        Example:
            >>> DateRangeHelper.add_months(date(2025, 1, 15), 2)
            date(2025, 3, 15)
            >>> DateRangeHelper.add_months(date(2025, 3, 15), -1)
            date(2025, 2, 15)
        """
        return start_date + relativedelta(months=months)

    @staticmethod
    def add_years(start_date: date, years: int) -> date:
        """
        Add or subtract years from a date.

        Args:
            start_date: date object
            years: int (positive to add, negative to subtract)

        Returns:
            date: New date with years added/subtracted

        Example:
            >>> DateRangeHelper.add_years(date(2025, 3, 15), 1)
            date(2026, 3, 15)
            >>> DateRangeHelper.add_years(date(2025, 3, 15), -2)
            date(2023, 3, 15)
        """
        return start_date + relativedelta(years=years)

    @staticmethod
    def months_between(start_date: date, end_date: date) -> int:
        """
        Calculate number of months between two dates.

        Args:
            start_date: date object
            end_date: date object

        Returns:
            int: Number of months between dates (can be negative)

        Example:
            >>> DateRangeHelper.months_between(date(2025, 1, 1), date(2025, 4, 1))
            3
            >>> DateRangeHelper.months_between(date(2025, 4, 1), date(2025, 1, 1))
            -3
        """
        return (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)

    @staticmethod
    def generate_month_range(start_date: date, end_date: date) -> list[date]:
        """
        Generate a list of first-of-month dates between start and end.

        Args:
            start_date: date object
            end_date: date object

        Returns:
            list: List of date objects (first day of each month)

        Example:
            >>> DateRangeHelper.generate_month_range(
            ...     date(2025, 1, 15),
            ...     date(2025, 4, 20)
            ... )
            [date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1), date(2025, 4, 1)]
        """
        months = []
        current = DateRangeHelper.get_first_of_month(start_date)
        end_first = DateRangeHelper.get_first_of_month(end_date)

        while current <= end_first:
            months.append(current)
            current = DateRangeHelper.add_months(current, 1)

        return months

    @staticmethod
    def get_current_month_first() -> date:
        """
        Get the first day of the current month.

        Returns:
            date: First day of current month

        Example:
            >>> # If today is 2025-12-22
            >>> DateRangeHelper.get_current_month_first()
            date(2025, 12, 1)
        """
        return DateRangeHelper.get_first_of_month(date.today())

    @staticmethod
    def get_current_year_start() -> date:
        """
        Get the first day of the current year.

        Returns:
            date: January 1st of current year

        Example:
            >>> # If today is 2025-12-22
            >>> DateRangeHelper.get_current_year_start()
            date(2025, 1, 1)
        """
        return date(date.today().year, 1, 1)

    @staticmethod
    def is_leap_year(year: int) -> bool:
        """
        Check if a year is a leap year.

        Args:
            year: int year

        Returns:
            bool: True if leap year, False otherwise

        Example:
            >>> DateRangeHelper.is_leap_year(2024)
            True
            >>> DateRangeHelper.is_leap_year(2025)
            False
        """
        return calendar.isleap(year)

    @staticmethod
    def format_month_year(month_date: date, short: bool = False) -> str:
        """
        Format a date as month-year string.

        Args:
            month_date: date object
            short: bool, if True use short format (Feb 25), otherwise long (February 2025)

        Returns:
            str: Formatted month-year string

        Example:
            >>> DateRangeHelper.format_month_year(date(2025, 2, 15))
            'February 2025'
            >>> DateRangeHelper.format_month_year(date(2025, 2, 15), short=True)
            'Feb 25'
        """
        if short:
            return month_date.strftime("%b %y")
        return month_date.strftime("%B %Y")

    @staticmethod
    def get_quarter_range(year: int, quarter: int) -> tuple[date, date]:
        """
        Get start and end dates for a calendar quarter.

        Args:
            year: int year
            quarter: int quarter (1-4)

        Returns:
            tuple: (quarter_start, quarter_end) as date objects

        Example:
            >>> DateRangeHelper.get_quarter_range(2026, 1)
            (date(2026, 1, 1), date(2026, 3, 31))
            >>> DateRangeHelper.get_quarter_range(2026, 2)
            (date(2026, 4, 1), date(2026, 6, 30))
        """
        if not 1 <= quarter <= 4:
            raise ValueError(f"quarter must be 1-4, got {quarter}")
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        start = date(year, start_month, 1)
        end = date(year, end_month, calendar.monthrange(year, end_month)[1])
        return start, end

    @staticmethod
    def get_quarter_for_date(target_date: date) -> tuple[int, date, date]:
        """
        Get the quarter number and boundaries for the quarter containing a date.

        Args:
            target_date: date object

        Returns:
            tuple: (quarter_number, quarter_start, quarter_end)

        Example:
            >>> DateRangeHelper.get_quarter_for_date(date(2026, 7, 2))
            (3, date(2026, 7, 1), date(2026, 9, 30))
        """
        quarter = (target_date.month - 1) // 3 + 1
        start, end = DateRangeHelper.get_quarter_range(target_date.year, quarter)
        return quarter, start, end

    @staticmethod
    def calculate_year_overlap_days(
        period_start: date, period_end: date, target_year: int | date
    ) -> int:
        """
        Calculate days that overlap with a specific year.

        Useful for calculating vacation days, sick leave, etc. that may
        span multiple calendar years.

        Args:
            period_start: Start date of the period
            period_end: End date of the period
            target_year: Year to calculate overlap for (int or date object)

        Returns:
            int: Number of days in the period that fall within target_year

        Example:
            >>> # Period that spans two years
            >>> DateRangeHelper.calculate_year_overlap_days(
            ...     date(2024, 12, 23), date(2025, 1, 5), 2025
            ... )
            5
            >>> # Full period in target year
            >>> DateRangeHelper.calculate_year_overlap_days(
            ...     date(2025, 8, 9), date(2025, 8, 25), 2025
            ... )
            17
        """
        if isinstance(target_year, date):
            target_year = target_year.year

        year_start = date(target_year, 1, 1)
        year_end = date(target_year, 12, 31)

        # Calculate overlap with the target year
        actual_start = max(period_start, year_start)
        actual_end = min(period_end, year_end)

        # Only count if there's actual overlap
        if actual_start <= actual_end:
            return (actual_end - actual_start).days + 1
        return 0

    @staticmethod
    def count_working_days(
        start_date: date,
        end_date: date,
        holidays: frozenset[date] | set[date] = frozenset(),
    ) -> int:
        """
        Count working days (Monday-Friday, excluding holidays) between two dates (inclusive).

        Args:
            start_date: Start date
            end_date: End date (inclusive)
            holidays: Optional set of dates to exclude (e.g. public holidays).
                      Defaults to empty — i.e. only weekends are excluded.

        Returns:
            int: Number of working days in the period

        Example:
            >>> # Week with weekend
            >>> DateRangeHelper.count_working_days(
            ...     date(2025, 11, 1), date(2025, 11, 7)
            ... )
            5
            >>> # Single day (Friday)
            >>> DateRangeHelper.count_working_days(
            ...     date(2025, 11, 14), date(2025, 11, 14)
            ... )
            1
            >>> # Weekend only
            >>> DateRangeHelper.count_working_days(
            ...     date(2025, 11, 1), date(2025, 11, 2)
            ... )
            0
        """
        from datetime import timedelta

        current = start_date
        working_days = 0

        while current <= end_date:
            if current.weekday() < 5 and current not in holidays:  # Mon-Fri, not a holiday
                working_days += 1
            current += timedelta(days=1)

        return working_days
