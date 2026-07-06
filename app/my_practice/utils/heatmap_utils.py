"""
Utilities for generating activity heatmap data from InvoiceItems.
"""

from datetime import date

from ..models import InvoiceItem
from . import DateRangeHelper, count_sessions


def get_sessions_for_month(month_date, practice=None):
    """
    Get session data from InvoiceItems for a given month.

    Args:
        month_date: Date object representing the month
        practice: Optional Practice instance for multi-practice filtering

    Returns dict: {client_code: hours}
    """
    result = {}
    month_start, month_end = DateRangeHelper.get_month_range(month_date)

    invoice_items = InvoiceItem.objects.filter(
        session__session_date__gte=month_start,
        session__session_date__lte=month_end,
        invoice__client__isnull=False,
    )

    if practice:
        invoice_items = invoice_items.filter(invoice__practice=practice)

    invoice_items = invoice_items.select_related("invoice__client", "session")

    client_items: dict[str, list] = {}
    for item in invoice_items:
        client_code = item.invoice.client.client_code
        if client_code not in client_items:
            client_items[client_code] = []
        client_items[client_code].append(item)

    for client_code, items in client_items.items():
        hours = count_sessions(items, exclude_cancellations=True)
        if hours > 0:
            result[client_code] = hours

    return result


def get_heatmap_data(
    current_year, current_month, months_to_show=12, start_offset=0, practice=None, sort="total"
):
    """
    Generate heatmap data from InvoiceItems only.

    Args:
        current_year: Current year
        current_month: Current month (1-12)
        months_to_show: Number of months to display
        start_offset: How many months back from today to start (can be negative for future)
        practice: Optional Practice instance for multi-practice filtering

    Returns:
        dict with keys:
            - heatmap_data: List of month data dicts
            - active_clients_with_totals: List of top 30 active clients
            - range_start_date: Start of date range
            - range_end_date_full: End of date range
    """
    # Compute the date range once
    total_months_start = current_year * 12 + current_month - 1 - (months_to_show - 1 + start_offset)
    range_start_year = total_months_start // 12
    range_start_month = (total_months_start % 12) + 1
    range_start_date = date(range_start_year, range_start_month, 1)

    total_months_end = current_year * 12 + current_month - 1 - start_offset
    range_end_year = total_months_end // 12
    range_end_month = (total_months_end % 12) + 1
    _, range_end_date_full = DateRangeHelper.get_month_range(
        date(range_end_year, range_end_month, 1)
    )

    # Single query covering the full range; partition by month in Python
    qs = InvoiceItem.objects.filter(
        session__session_date__range=(range_start_date, range_end_date_full),
        invoice__client__isnull=False,
    ).select_related("invoice__client", "session")

    if practice:
        qs = qs.filter(invoice__practice=practice)

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

    # Build heatmap_data in display order (newest first)
    heatmap_data = []
    for i in range(months_to_show - 1 + start_offset, start_offset - 1, -1):
        total_months = current_year * 12 + current_month - 1 - i
        year = total_months // 12
        month = (total_months % 12) + 1
        month_date = date(year, month, 1)

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

    if sort == "recent":
        sort_key = lambda x: x[1]["last_activity"]  # noqa: E731
    else:
        sort_key = lambda x: x[1]["total"]  # noqa: E731

    active_clients_with_totals = [
        {"code": code, "total": data["total"]}
        for code, data in sorted(client_totals.items(), key=sort_key, reverse=True)[:30]
    ]

    return {
        "heatmap_data": heatmap_data,
        "active_clients_with_totals": active_clients_with_totals,
        "range_start_date": range_start_date,
        "range_end_date_full": range_end_date_full,
    }
