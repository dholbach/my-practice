"""
Capacity calculation utilities.

Provides centralized capacity configuration and calculation for different time periods.
Accounts for changes in available working hours over time as the practice evolved.
"""

from datetime import date, timedelta

from django.db.models import FloatField, Sum
from django.db.models.functions import Cast

from ..models import Session
from .date_helpers import DateRangeHelper
from .practice_days import berlin_public_holidays
from .timeoff_helpers import calculate_timeoff_for_period

# Capacity configuration: list of (start_date, hours_per_week)
# Each entry defines capacity from that date onwards until the next entry
CAPACITY_PERIODS = [
    # 2020-2023 Jul: Building practice, ~10 sessions/week capacity
    (date(2020, 1, 1), 10),
    # 2023 Aug onwards: Full capacity, 20 hours/week for therapy sessions
    (date(2023, 8, 1), 20),
]


def get_weekly_capacity_for_date(target_date: date) -> float:
    """
    Get the weekly capacity (hours) for a specific date.

    Args:
        target_date: The date to get capacity for

    Returns:
        Hours per week available for client sessions
    """
    capacity = CAPACITY_PERIODS[0][1]  # Default to first period

    for period_start, hours_per_week in CAPACITY_PERIODS:
        if target_date >= period_start:
            capacity = hours_per_week
        else:
            break

    return capacity


def calculate_period_capacity(
    start_date: date, end_date: date, include_timeoff: bool = True
) -> dict:
    """
    Calculate capacity metrics for a date range.

    Handles periods that span multiple capacity configurations by
    calculating weighted capacity based on days in each period.

    For periods extending far into the future, limits bookings to a 2-week
    horizon from today (since most clients book short-term). Capacity is
    calculated up to the earlier of: end_date or today + 2 weeks.

    Args:
        start_date: Start of period
        end_date: End of period
        include_timeoff: Whether to subtract time off from available days

    Returns:
        dict with capacity metrics
    """
    from datetime import timedelta

    today = date.today()
    two_weeks_ahead = today + timedelta(weeks=2)

    # Determine if we should apply the 2-week horizon limit
    # Only apply if the period extends MORE than 2 weeks into the future
    is_forward_looking = end_date > two_weeks_ahead
    booking_horizon_end = None

    # For periods extending far into the future, cap at today + 2 weeks
    if is_forward_looking:
        booking_horizon_end = two_weeks_ahead
        effective_end_date = booking_horizon_end
    else:
        # For periods ending within 2 weeks (or in the past), use actual end date
        effective_end_date = end_date

    # Build holiday set once for the effective date range
    _holidays: set[date] = set()
    for yr in range(start_date.year, effective_end_date.year + 1):
        _holidays |= berlin_public_holidays(yr)

    # Working days in effective period, excluding public holidays
    working_days = DateRangeHelper.count_working_days(start_date, effective_end_date, _holidays)

    # Subtract time off if requested (timeoff_helpers also uses holiday-aware counts)
    if include_timeoff:
        timeoff_result = calculate_timeoff_for_period(start_date, effective_end_date)
        available_working_days = max(0, working_days - timeoff_result["total_workdays"])
        timeoff_days = timeoff_result["total_workdays"]
    else:
        available_working_days = working_days
        timeoff_days = 0

    available_hours = available_working_days * 8  # 8 hours per working day

    # Calculate weighted capacity based on effective period
    usable_capacity = _calculate_weighted_capacity(
        start_date, effective_end_date, available_working_days, _holidays
    )

    # Calculate booked hours (uses same horizon)
    booked_hours = _get_booked_hours(start_date, end_date)

    return {
        "working_days_total": working_days,
        "working_days_available": available_working_days,
        "available_hours": available_hours,
        "usable_capacity_hours": usable_capacity,
        "booked_hours": booked_hours,
        "capacity_percentage": round(
            (booked_hours / usable_capacity * 100) if usable_capacity > 0 else 0
        ),
        "remaining_hours": max(0, usable_capacity - booked_hours),
        "timeoff_days": timeoff_days,
        "is_forward_looking": is_forward_looking,
        "booking_horizon_end": booking_horizon_end,
    }


def _calculate_weighted_capacity(
    start_date: date,
    end_date: date,
    available_working_days: int,
    holidays: set[date] | frozenset[date] = frozenset(),
) -> float:
    """
    Calculate weighted capacity for a period that may span multiple capacity configurations.

    For periods entirely within one capacity config, uses that config's hours/week.
    For periods spanning multiple configs, calculates weighted average based on
    the proportion of working days in each config period.
    """
    # Simple case: single month or short period
    if start_date.year == end_date.year and start_date.month == end_date.month:
        # Use capacity for start of period
        hours_per_week = get_weekly_capacity_for_date(start_date)
        available_weeks = available_working_days / 5
        return available_weeks * hours_per_week

    # Check if period spans a capacity change
    capacity_changes_in_period = [
        (period_start, hours)
        for period_start, hours in CAPACITY_PERIODS
        if start_date < period_start <= end_date
    ]

    if not capacity_changes_in_period:
        # No capacity change within period - use capacity at start
        hours_per_week = get_weekly_capacity_for_date(start_date)
        available_weeks = available_working_days / 5
        return available_weeks * hours_per_week

    # Period spans capacity changes - calculate weighted capacity
    total_capacity: float = 0.0
    current_start = start_date

    for change_date, new_hours in capacity_changes_in_period:
        # Calculate days before this change
        period_end = change_date - timedelta(days=1)
        days_in_segment = DateRangeHelper.count_working_days(current_start, period_end, holidays)
        hours_per_week = get_weekly_capacity_for_date(current_start)

        # Add capacity for this segment (proportional)
        weeks_in_segment: float = days_in_segment / 5
        total_capacity += weeks_in_segment * hours_per_week

        current_start = change_date

    # Add remaining days after last change
    if current_start <= end_date:
        days_remaining = DateRangeHelper.count_working_days(current_start, end_date, holidays)
        hours_per_week = get_weekly_capacity_for_date(current_start)
        weeks_remaining: float = days_remaining / 5
        total_capacity += weeks_remaining * hours_per_week

    return total_capacity


def _get_booked_hours(start_date: date, end_date: date) -> float:
    """
    Get total booked therapist hours from Sessions for a period.

    For periods that extend into the future, only counts sessions up to 2 weeks
    from today (since most clients book sessions short-term).

    Excludes cancelled sessions; divides by group_size for therapist-hour normalisation.
    """
    today = date.today()

    # For forward-looking capacity, only consider the next 2 weeks
    if end_date > today:
        booking_horizon = today + timedelta(weeks=2)
        effective_end_date = min(end_date, booking_horizon)
    else:
        effective_end_date = end_date

    result = Session.objects.filter(
        session_date__gte=start_date,
        session_date__lte=effective_end_date,
        cancelled=False,
    ).aggregate(
        total_minutes=Sum(Cast("duration", FloatField()) / Cast("group_size", FloatField()))
    )
    return (result["total_minutes"] or 0) / 60


def get_monthly_capacity_for_date(target_date: date) -> float:
    """
    Get the monthly capacity (hours) for a specific month.

    Convenience function that calculates capacity for the full month
    containing target_date.

    Args:
        target_date: Any date within the target month

    Returns:
        Hours available for client sessions in that month
    """
    month_start = DateRangeHelper.get_first_of_month(target_date)
    month_end = DateRangeHelper.get_last_of_month(target_date)

    result = calculate_period_capacity(month_start, month_end)
    return float(result["usable_capacity_hours"])


def get_capacity_trends(start_year=2020, end_date=None, start_date=None):
    """
    Calculate capacity utilization trends over time (monthly).

    Uses Session data (P-035) to track booked hours vs available capacity.
    Cancellations are properly excluded via Session.cancelled; group sessions
    count once for the therapist via Session.group_size.
    Capacity hours per week vary by time period (see CAPACITY_PERIODS).

    Optimized to use only 2 queries regardless of time range.

    Args:
        start_year: Starting year for data collection (default 2020)
        end_date: End date (defaults to today)
        start_date: Start date (overrides start_year if provided)

    Returns:
        list: Monthly capacity data with month, year, booked_hours,
              capacity_hours, capacity_percentage, timeoff_days
    """
    from collections import defaultdict

    from django.db.models.functions import TruncMonth

    from ..models import TimeOff
    from . import format_month_key, format_month_label

    if end_date is None:
        end_date = date.today()

    if start_date is None:
        start_date = date(start_year, 1, 1)

    # Query 1: Get all booked therapist hours grouped by month (single query).
    # Excludes cancelled sessions; divides by group_size so group sessions count
    # once for the therapist regardless of participant count.
    booked_by_month = defaultdict(float)
    monthly_sessions = (
        Session.objects.filter(
            session_date__gte=start_date,
            session_date__lte=end_date,
            cancelled=False,
        )
        .annotate(month=TruncMonth("session_date"))
        .values("month")
        .annotate(
            total_minutes=Sum(Cast("duration", FloatField()) / Cast("group_size", FloatField()))
        )
    )
    for row in monthly_sessions:
        if row["month"]:
            month_key = row["month"].strftime("%Y-%m")
            booked_by_month[month_key] = (row["total_minutes"] or 0) / 60

    # Query 2: Get all time-off periods that overlap with our range (single query)
    timeoff_periods = list(
        TimeOff.objects.filter(start_date__lte=end_date, end_date__gte=start_date)
    )

    # Pre-build holiday set covering all years in the range (used in the loop below)
    _holidays: set[date] = set()
    for yr in range(start_date.year, end_date.year + 1):
        _holidays |= berlin_public_holidays(yr)

    # Build capacity data iterating through months (no DB queries in loop)
    capacity_data = []
    current_date = start_date

    while current_date <= end_date:
        # Calculate month boundaries
        month_start = current_date.replace(day=1)
        if current_date.month == 12:
            next_month = current_date.replace(year=current_date.year + 1, month=1, day=1)
        else:
            next_month = current_date.replace(month=current_date.month + 1, day=1)
        month_end = next_month - timedelta(days=1)

        # Don't go beyond end_date
        if month_end > end_date:
            month_end = end_date

        # Working days in the month, excluding public holidays
        working_days = DateRangeHelper.count_working_days(month_start, month_end, _holidays)

        # Time-off days: count actual non-holiday working days in each overlapping period
        timeoff_days = 0
        for t in timeoff_periods:
            if t.start_date <= month_end and t.end_date >= month_start:
                actual_start = max(t.start_date, month_start)
                actual_end = min(t.end_date, month_end)
                timeoff_days += DateRangeHelper.count_working_days(
                    actual_start, actual_end, _holidays
                )

        available_working_days = max(0, working_days - timeoff_days)

        # Calculate capacity based on period configuration
        hours_per_week = get_weekly_capacity_for_date(month_start)
        available_weeks = available_working_days / 5
        usable_capacity = available_weeks * hours_per_week

        # Get booked hours from cached data
        month_key = format_month_key(current_date)
        booked_hours = booked_by_month.get(month_key, 0)

        capacity_percentage = round(
            (booked_hours / usable_capacity * 100) if usable_capacity > 0 else 0
        )

        capacity_data.append(
            {
                "month": format_month_label(month_key, "short"),
                "month_name": current_date.strftime("%B"),
                "month_num": current_date.month,
                "year": current_date.year,
                "booked_hours": round(booked_hours, 1),
                "capacity_hours": round(usable_capacity, 1),
                "capacity_percentage": capacity_percentage,
                "timeoff_days": timeoff_days,
            }
        )

        # Move to next month
        current_date = DateRangeHelper.add_months(current_date, 1)

    return capacity_data
