"""
TimeOff calculation utilities.

Centralized logic for calculating vacation days, workdays off, and
other time-off statistics.
"""

from datetime import date

from .date_helpers import DateRangeHelper
from .practice_days import berlin_public_holidays_between


def overlap(time_off, start_date, end_date):
    """The (start, end) of the part of ``time_off`` inside the period, or None if it misses it."""
    actual_start = max(time_off.start_date, start_date)
    actual_end = min(time_off.end_date, end_date)
    return (actual_start, actual_end) if actual_start <= actual_end else None


def workdays_within(time_off, start_date, end_date, holidays) -> int:
    """Workdays (Mon-Fri, minus ``holidays``) of ``time_off`` that fall inside the period."""
    period = overlap(time_off, start_date, end_date)
    return DateRangeHelper.count_working_days(*period, holidays) if period else 0


def workdays_by_type(entries: list[dict]) -> dict[str, int]:
    """Sum the ``period_workdays`` of ``calculate_timeoff_for_period`` entries by time-off type."""
    by_type: dict[str, int] = {}
    for entry in entries:
        by_type[entry["type"]] = by_type.get(entry["type"], 0) + entry["period_workdays"]
    return by_type


def calculate_timeoff_for_year(year: int) -> dict:
    """Calculate total time-off days, weeks, and workdays for a given year."""
    return calculate_timeoff_for_period(date(year, 1, 1), date(year, 12, 31))  # type: ignore[no-any-return]


def calculate_timeoff_for_period(start_date, end_date):
    """
    Calculate total time-off days, weeks, and workdays for a specific date range.

    Handles time-off periods that span beyond the date range by only
    counting the days that actually fall within the specified range.

    Args:
        start_date (date): Start of the period
        end_date (date): End of the period

    Returns:
        dict: Contains:
            - total_days: int, total days off within the period
            - total_weeks: float, weeks off (rounded to 1 decimal)
            - total_workdays: int, exact workdays off (Mon–Fri only)
            - entries: list of dicts with details about each time-off period
              (including ``period_workdays``, its workdays inside the period)

    Example:
        >>> from datetime import date
        >>> result = calculate_timeoff_for_period(date(2025, 10, 1), date(2025, 12, 31))
        >>> result['total_days']
        10
    """
    from ..models import TimeOff

    # Get all timeoff that overlaps with this period
    timeoff_filtered = TimeOff.objects.filter(start_date__lte=end_date, end_date__gte=start_date)

    # Build holiday set once, covering all years in the range
    _holidays = berlin_public_holidays_between(start_date.year, end_date.year)

    total_days_off = 0
    total_workdays_off = 0
    entries = []

    for t in timeoff_filtered:
        period = overlap(t, start_date, end_date)
        if period is None:
            continue
        actual_start, actual_end = period
        days_in_period = (actual_end - actual_start).days + 1
        workdays_in_period = DateRangeHelper.count_working_days(actual_start, actual_end, _holidays)
        total_days_off += days_in_period
        total_workdays_off += workdays_in_period

        entries.append(
            {
                "title": t.title,
                "type": t.type,
                "full_start": t.start_date,
                "full_end": t.end_date,
                "full_days": t.duration_days,
                "period_start": actual_start,
                "period_end": actual_end,
                "period_days": days_in_period,
                "period_workdays": workdays_in_period,
            }
        )

    total_weeks_off = round(total_days_off / 7, 1)

    return {
        "total_days": total_days_off,
        "total_weeks": total_weeks_off,
        "total_workdays": total_workdays_off,
        "entries": entries,
    }
