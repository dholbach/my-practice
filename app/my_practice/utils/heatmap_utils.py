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

    # Get all invoice items for this month, grouped by client
    invoice_items = InvoiceItem.objects.filter(
        session__session_date__gte=month_start,
        session__session_date__lte=month_end,
        invoice__client__isnull=False,
    )

    if practice:
        invoice_items = invoice_items.filter(invoice__practice=practice)

    invoice_items = invoice_items.select_related("invoice__client", "session")

    # Group items by client code
    client_items: dict[str, list] = {}
    for item in invoice_items:
        client_code = item.invoice.client.client_code
        if client_code not in client_items:
            client_items[client_code] = []
        client_items[client_code].append(item)

    # Calculate hours using centralized session counting
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
    heatmap_data = []

    # Get data for requested time range
    for i in range(months_to_show - 1 + start_offset, start_offset - 1, -1):
        # Calculate year and month correctly for any offset
        total_months = current_year * 12 + current_month - 1 - i
        year = total_months // 12
        month = (total_months % 12) + 1
        month_date = date(year, month, 1)

        month_data = {
            "month": month_date.strftime("%b %y"),
            "month_date": month_date,
            "clients": {},
            "total": 0,
        }

        # Get session data from InvoiceItems (filtered by practice)
        session_data = get_sessions_for_month(month_date, practice=practice)
        month_data["clients"] = session_data
        month_data["total"] = sum(session_data.values())

        heatmap_data.append(month_data)

    # Calculate date range for client totals
    total_months_start = current_year * 12 + current_month - 1 - (months_to_show - 1 + start_offset)
    range_start_year = total_months_start // 12
    range_start_month = (total_months_start % 12) + 1
    range_start_date = date(range_start_year, range_start_month, 1)

    total_months_end = current_year * 12 + current_month - 1 - start_offset
    range_end_year = total_months_end // 12
    range_end_month = (total_months_end % 12) + 1

    # Get end date of the last month
    _, last_day_end = DateRangeHelper.get_month_range(date(range_end_year, range_end_month, 1))
    range_end_date_full = last_day_end

    # Get InvoiceItem totals for the entire range (filtered by practice)
    invoice_items = InvoiceItem.objects.filter(
        session__session_date__gte=range_start_date,
        session__session_date__lte=range_end_date_full,
        invoice__client__isnull=False,
    )

    if practice:
        invoice_items = invoice_items.filter(invoice__practice=practice)

    invoice_items = invoice_items.select_related("invoice__client", "session")

    # Group items by client code
    client_items: dict[str, list] = {}
    for item in invoice_items:
        code = item.invoice.client.client_code
        if code not in client_items:
            client_items[code] = []
        client_items[code].append(item)

    # Calculate hours and last activity using centralized session counting
    client_totals = {}
    for code, items in client_items.items():
        hours = count_sessions(items, exclude_cancellations=True)
        last_date = max(item.session.session_date for item in items)
        client_totals[code] = {"total": hours, "last_activity": last_date}

    # Sort by total hours or by most-recent activity, take top 30
    if sort == "recent":
        sort_key = lambda x: x[1]["last_activity"]  # noqa: E731
    else:
        sort_key = lambda x: x[1]["total"]  # noqa: E731

    active_clients_with_totals = [
        {"code": code, "total": data["total"]}
        for code, data in sorted(
            client_totals.items(),
            key=sort_key,
            reverse=True,
        )[:30]
    ]

    return {
        "heatmap_data": heatmap_data,
        "active_clients_with_totals": active_clients_with_totals,
        "range_start_date": range_start_date,
        "range_end_date_full": range_end_date_full,
    }
