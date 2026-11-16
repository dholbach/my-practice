"""
Utilities for generating activity heatmap data from InvoiceItems.
"""

from datetime import date

from ..models import InvoiceItem
from ..models.base import PracticeScope, scope_to_practice
from . import DateRangeHelper, count_sessions


def get_heatmap_data(
    current_year,
    current_month,
    months_to_show=12,
    start_offset=0,
    *,
    practice: PracticeScope,
    sort="total",
):
    """
    Generate heatmap data from InvoiceItems only.

    Args:
        current_year: Current year
        current_month: Current month (1-12)
        months_to_show: Number of months to display
        start_offset: How many months back from today to start (can be negative for future)
        practice: Practice to scope to; None gives nothing, ALL_PRACTICES everything

    Returns:
        dict with keys:
            - heatmap_data: List of month data dicts
            - active_clients_with_totals: List of top 30 active clients
            - range_start_date: Start of date range
            - range_end_date_full: End of date range
    """
    # Compute the date range once
    current_month_start = date(current_year, current_month, 1)
    range_start_date = DateRangeHelper.add_months(
        current_month_start, -(months_to_show - 1 + start_offset)
    )
    _, range_end_date_full = DateRangeHelper.get_month_range(
        DateRangeHelper.add_months(current_month_start, -start_offset)
    )

    # Single query covering the full range; partition by month in Python
    qs = InvoiceItem.objects.filter(
        session__session_date__range=(range_start_date, range_end_date_full),
        invoice__client__isnull=False,
    ).select_related("invoice__client", "session", "service_type")

    qs = scope_to_practice(qs, practice, "invoice__practice")

    # Build per-month and per-client buckets in one pass
    month_buckets: dict[tuple, dict[str, list]] = {}  # (year, month) -> {client_code: [items]}
    client_buckets: dict[str, list] = {}  # client_code -> [items] for totals

    for item in qs:
        session_date = item.session.session_date
        key = (session_date.year, session_date.month)
        code = item.invoice.client.client_code

        if key not in month_buckets:
            month_buckets[key] = {}
        bucket = month_buckets[key]
        if code not in bucket:
            bucket[code] = []
        bucket[code].append(item)

        if code not in client_buckets:
            client_buckets[code] = []
        client_buckets[code].append(item)

    # Build heatmap_data in display order (oldest first)
    heatmap_data = []
    for i in range(months_to_show - 1 + start_offset, start_offset - 1, -1):
        month_date = DateRangeHelper.add_months(current_month_start, -i)
        year, month = month_date.year, month_date.month

        session_data: dict[str, float] = {}
        for code, items in month_buckets.get((year, month), {}).items():
            hours = count_sessions(items, exclude_cancellations=True)
            if hours > 0:
                session_data[code] = hours

        heatmap_data.append(
            {
                "month": month_date.strftime("%b %y"),
                "month_date": month_date,
                "clients": session_data,
                "total": sum(session_data.values()),
            }
        )

    # Client totals: by-product of the same fetch
    client_totals: dict[str, dict] = {}
    for code, items in client_buckets.items():
        hours = count_sessions(items, exclude_cancellations=True)
        if hours > 0:
            last_date = max(item.session.session_date for item in items)
            client_totals[code] = {"total": hours, "last_activity": last_date}

    sort_field = "last_activity" if sort == "recent" else "total"

    active_clients_with_totals = [
        {"code": code, "total": data["total"]}
        for code, data in sorted(
            client_totals.items(), key=lambda x: x[1][sort_field], reverse=True
        )[:30]
    ]

    return {
        "heatmap_data": heatmap_data,
        "active_clients_with_totals": active_clients_with_totals,
        "range_start_date": range_start_date,
        "range_end_date_full": range_end_date_full,
    }
