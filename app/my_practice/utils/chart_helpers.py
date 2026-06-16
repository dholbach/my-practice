"""
Chart and data aggregation helpers for consistent data formatting across views.
"""

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from ..utils.calculations import count_sessions

# German month abbreviations (index 0 = January, index 11 = December)
GERMAN_MONTHS_SHORT = [
    "Jan",
    "Feb",
    "Mär",
    "Apr",
    "Mai",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Okt",
    "Nov",
    "Dez",
]


def format_month_key(date_obj: date | datetime) -> str:
    """
    Format date to YYYY-MM month key for aggregation.

    Args:
        date_obj: date or datetime object

    Returns:
        str: Month key in format "YYYY-MM" (e.g., "2025-12")

    Example:
        >>> format_month_key(date(2025, 12, 1))
        '2025-12'
    """
    return date_obj.strftime("%Y-%m")


def format_month_label(month_key: str, format_type: str = "short") -> str:
    """
    Format month key to human-readable label.

    Args:
        month_key: Month in "YYYY-MM" format
        format_type: "short" (mm/yy), "medium" (Mon YYYY), or "long" (Month YYYY)

    Returns:
        str: Formatted month label

    Examples:
        >>> format_month_label("2025-12", "short")
        '12/25'
        >>> format_month_label("2025-12", "medium")
        'Dec 2025'
        >>> format_month_label("2025-12", "long")
        'December 2025'
    """
    month_date = datetime.strptime(month_key, "%Y-%m")

    if format_type == "short":
        return month_date.strftime("%m/%y")
    elif format_type == "medium":
        return month_date.strftime("%b %Y")
    elif format_type == "long":
        return month_date.strftime("%B %Y")
    else:
        return month_date.strftime("%m/%y")  # Default to short


def aggregate_invoice_items_by_month(items, exclude_cancellations: bool = True) -> dict[str, float]:
    """
    Aggregate InvoiceItems by month, calculating session hours.

    Uses centralized count_sessions() for accurate hour calculation.

    Args:
        items: Iterable of InvoiceItem objects
        exclude_cancellations: Whether to exclude "Ausfall" items

    Returns:
        dict: {month_key: hours} where month_key is "YYYY-MM"

    Example:
        >>> items = InvoiceItem.objects.filter(invoice__client=client)
        >>> monthly_data = aggregate_invoice_items_by_month(items)
        >>> monthly_data
        {'2025-01': 6.0, '2025-02': 4.5, '2025-03': 7.5}
    """
    monthly_totals: dict[str, float] = defaultdict(float)

    for item in items:
        if item.session_id:
            month_key = format_month_key(item.session.session_date)
            # Use centralized session counting for accuracy
            hours = count_sessions([item], exclude_cancellations=exclude_cancellations)
            monthly_totals[month_key] += hours

    return dict(monthly_totals)


def prepare_monthly_chart_data(
    monthly_aggregation: dict[str, float],
    label_format: str = "short",
    value_key: str = "value",
    fill_gaps: bool = False,
) -> list[dict[str, Any]]:
    """
    Prepare aggregated monthly data for chart rendering.

    Sorts chronologically and formats labels consistently.

    Args:
        monthly_aggregation: Dict with month keys ("YYYY-MM") and numeric values
        label_format: Format for month labels ("short", "medium", or "long")
        value_key: Key name for the value in output (e.g., "hours", "revenue")
        fill_gaps: If True, fill in missing months between first and last with 0 values

    Returns:
        list: Sorted list of dicts with "month" and value_key

    Example:
        >>> monthly_data = {'2025-01': 6.0, '2025-03': 7.5, '2025-02': 4.5}
        >>> prepare_monthly_chart_data(monthly_data, value_key="hours")
        [
            {"month": "01/25", "hours": 6.0},
            {"month": "02/25", "hours": 4.5},
            {"month": "03/25", "hours": 7.5}
        ]
    """
    if not monthly_aggregation:
        return []

    sorted_months = sorted(monthly_aggregation.keys())

    if fill_gaps and len(sorted_months) >= 1:
        # Generate all months between first and last
        from dateutil.relativedelta import relativedelta

        first_month = datetime.strptime(sorted_months[0], "%Y-%m")
        last_month = datetime.strptime(sorted_months[-1], "%Y-%m")

        all_months = []
        current = first_month
        while current <= last_month:
            all_months.append(current.strftime("%Y-%m"))
            current += relativedelta(months=1)
        sorted_months = all_months

    chart_data = [
        {
            "month": format_month_label(month_key, label_format),
            value_key: monthly_aggregation.get(month_key, 0),
        }
        for month_key in sorted_months
    ]

    return chart_data
