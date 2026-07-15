"""
Financial calculation utilities for invoice and item calculations.
"""

from decimal import Decimal
from typing import Iterable


def to_float(value: Decimal | int | float | str) -> float:
    """
    Safe conversion of Decimal/int/str to float for calculations.

    Args:
        value: Decimal, int, float, or string to convert

    Returns:
        float: Converted value, or 0.0 if conversion fails

    Examples:
        >>> to_float(Decimal('1.5'))
        1.5
        >>> to_float(60)
        60.0
        >>> to_float('invalid')
        0.0
    """
    try:
        return float(value)
    except ValueError, TypeError, AttributeError:
        return 0.0


def count_sessions(
    items: Iterable,
    exclude_cancellations: bool = True,
    therapist_hours: bool = False,
) -> float:
    """
    Count the total number of sessions from invoice items.

    Sessions are normalized to a 60-minute base:
    - 60 minutes = 1.0 session
    - 90 minutes = 1.5 sessions
    - 15 minutes = 0.25 sessions

    Args:
        items: Iterable of InvoiceItem objects
        exclude_cancellations: If True, exclude items whose service_type code contains "cancel"
        therapist_hours: If True, divide each item's contribution by its
            group_size field.  For individual sessions (group_size=1) this has
            no effect.  For group sessions, it converts per-client billing hours
            into actual therapist time: e.g. 8 participants × 2h / 8 = 2h.
            Use True for analytics that measure therapist workload (busiest
            months, capacity trends).  Leave False (default) for invoice
            calculations and per-client statistics.

    Returns:
        float: Total hours (normalized to 60min base)

    Examples:
        >>> count_sessions([item_60min, item_90min])
        2.5
        >>> # Group session: 8 participants, 2h each
        >>> count_sessions([group_item], therapist_hours=True)  # group_size=8
        2.0  # therapist actually worked 2h, not 16h
    """
    total = 0.0
    for item in items:
        # Skip cancellations if requested
        if exclude_cancellations:
            st = getattr(item, "service_type", None)
            if st and "cancel" in st.code.lower():
                continue

        # Normalize to 60-minute base: (duration / 60) * quantity
        duration = item.session.duration if item.session_id else 60
        sessions = (to_float(duration) / 60.0) * to_float(item.quantity)

        if therapist_hours:
            group_size = to_float(getattr(item, "group_size", 1) or 1)
            sessions = sessions / group_size

        total += sessions

    return total


def count_sessions_rounded(items: Iterable, exclude_cancellations: bool = True) -> int:
    """
    Count sessions and return rounded integer.

    Convenience wrapper around count_sessions() that returns a rounded integer.
    Useful for display in summaries.

    Args:
        items: Iterable of InvoiceItem objects
        exclude_cancellations: If True, exclude items whose service_type code contains "cancel"

    Returns:
        int: Total number of sessions (rounded)
    """
    return round(count_sessions(items, exclude_cancellations))


def count_session_hours(
    sessions: Iterable,
    exclude_cancelled: bool = True,
    therapist_hours: bool = True,
) -> float:
    """
    Count total clinical hours from Session objects.

    Sessions are normalized to a 60-minute base:
    - 60 minutes = 1.0 hour
    - 90 minutes = 1.5 hours

    Uses Session.cancelled and Session.group_size (P-035), so this is the
    preferred function for capacity/analytics calculations. For per-client
    billing statistics, use count_sessions() with InvoiceItem objects instead.

    Args:
        sessions: Iterable of Session objects
        exclude_cancelled: If True (default), skip sessions where cancelled=True
        therapist_hours: If True (default), divide each session's contribution
            by group_size. For individual sessions (group_size=1) this has no
            effect. For group sessions, converts per-session billing hours into
            actual therapist time. Use False only for per-client statistics.

    Returns:
        float: Total hours (normalized to 60-minute base)
    """
    total = 0.0
    for session in sessions:
        if exclude_cancelled and session.cancelled:
            continue
        hours = to_float(session.duration) / 60.0
        if therapist_hours:
            group_size = to_float(getattr(session, "group_size", 1) or 1)
            hours = hours / group_size
        total += hours
    return total


def apply_remainder_distribution(created_items: list, total_amount: Decimal) -> None:
    """
    Apply remainder distribution to ensure exact invoice total.

    Problem: Dividing invoice total by session count creates rounding errors.
    Example: 340€ ÷ 3 = 113.33€ × 3 = 339.99€ (0.01€ lost)

    Solution: Last item gets remainder to guarantee exact total.
    Only applies to items with quantity=1.00 (whole sessions).

    Args:
        created_items: List of InvoiceItem objects to distribute remainder across
        total_amount: Expected total amount of the invoice

    Side effects:
        Modifies and saves the last item with quantity=1.00 to adjust its total and rate
    """
    if not created_items:
        return

    items_with_qty_1 = [item for item in created_items if item.quantity == Decimal("1.00")]
    items_with_other_qty = [item for item in created_items if item.quantity != Decimal("1.00")]

    if items_with_qty_1:
        # Calculate sum of all items except the last qty=1 item
        items_sum = sum(item.total for item in items_with_qty_1[:-1])
        items_sum += sum(item.total for item in items_with_other_qty)

        # Last qty=1 item gets the remainder to ensure exact total
        remainder = total_amount - items_sum
        last_item = items_with_qty_1[-1]

        # Update both total and rate (rate must match to prevent recalculation)
        last_item.total = remainder
        last_item.rate = remainder / last_item.quantity
        last_item.save()
