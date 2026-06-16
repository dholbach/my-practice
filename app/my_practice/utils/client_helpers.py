"""Helper functions for client-related operations"""

from datetime import date
from typing import Any, Dict


def annotate_activity_status(clients, today=None):
    """
    Annotate clients with activity status attributes.

    Requires clients to have `last_session_date` attribute (from annotation).
    Adds the following attributes:
    - days_since_session: Number of days since last session (9999 if no sessions)
    - last_session_year: Year of last session (None if no sessions)

    Args:
        clients: QuerySet or iterable of Client objects with last_session_date
        today: Reference date (defaults to today)

    Returns:
        Same clients iterable with added attributes
    """
    if today is None:
        today = date.today()

    for client in clients:
        if hasattr(client, "last_session_date") and client.last_session_date:
            client.days_since_session = (today - client.last_session_date).days
            client.last_session_year = client.last_session_date.year
        else:
            client.days_since_session = 9999  # No session
            client.last_session_year = None

    return clients


def flatten_invoice_items(invoices):
    """
    Flatten all invoice items from a collection of invoices.

    IMPORTANT: Assumes invoices have items prefetched to avoid N+1 queries.
    Use Invoice.objects.prefetch_related('items') before calling this.

    Args:
        invoices: Iterable of Invoice objects (should have items prefetched)

    Returns:
        list: All InvoiceItem objects from all invoices
    """
    return [item for invoice in invoices for item in invoice.items.all()]


def calculate_client_session_stats(items) -> Dict[str, Any]:
    """
    Calculate comprehensive session statistics from invoice items.

    Args:
        items: QuerySet or list of InvoiceItem objects

    Returns:
        dict: {
            'total_hours': float - Total session hours (using count_sessions)
            'session_count': int - Number of non-cancelled sessions
            'avg_duration': int - Average duration in minutes
        }
    """
    from .calculations import count_sessions

    items_list = list(items) if hasattr(items, "__iter__") else items

    total_hours = count_sessions(items_list, exclude_cancellations=True)
    session_count = len(
        [item for item in items_list if not (item.session_id and item.session.cancelled)]
    )

    total_minutes = sum(
        (item.session.duration if item.session_id else 0)
        for item in items_list
        if not (item.session_id and item.session.cancelled)
    )
    avg_duration = round(total_minutes / session_count) if session_count > 0 else 0

    return {
        "total_hours": total_hours,
        "session_count": session_count,
        "avg_duration": avg_duration,
    }


def group_clients_by_activity(clients, use_attention_category=True):
    """
    Group clients into workflow categories.

    Requires clients to have:
    - active: boolean field
    - days_since_session: int attribute (use annotate_activity_status first)
    - tags: prefetched relation

    Args:
        clients: List of Client objects with required attributes
        use_attention_category: If True, uses tag.category=='attention' to determine priority.
                               If False, falls back to hardcoded slug list.

    Returns:
        dict: {
            'needs_attention': list of clients,
            'active_ok': list of clients,
            'inactive': list of clients
        }
    """
    clients_needs_attention = []
    clients_active_ok = []
    clients_inactive = []

    for client in clients:
        # Get client tags (assuming tags are prefetched)
        client_tags = list(client.tags.all())

        # Inactive clients go to inactive section
        if not client.active:
            clients_inactive.append(client)
        else:
            # Check if client needs attention
            needs_attention = False

            if use_attention_category:
                # Use tag category to determine priority
                needs_attention = any(tag.category == "attention" for tag in client_tags)
            else:
                # Fallback: hardcoded attention tag slugs
                attention_tag_slugs = [
                    "urgent",
                    "follow-up",
                    "documentation",
                    "missing-paperwork",
                ]
                client_tag_slugs = {tag.slug for tag in client_tags}
                needs_attention = any(slug in client_tag_slugs for slug in attention_tag_slugs)

            # Also check days since session
            if needs_attention or client.days_since_session > 90:
                clients_needs_attention.append(client)
            else:
                clients_active_ok.append(client)

    return {
        "needs_attention": clients_needs_attention,
        "active_ok": clients_active_ok,
        "inactive": clients_inactive,
    }


def group_clients_by_year(clients):
    """
    Group clients by year of their last session.

    Requires clients to have last_session_year attribute
    (use annotate_activity_status first).

    Args:
        clients: List of Client objects with last_session_year attribute

    Returns:
        dict: {year: [clients], ...} sorted by year descending
              Uses "Keine Sessions" as key for clients without sessions
    """
    clients_by_year: dict[int | str, list] = {}

    for client in clients:
        year = client.last_session_year if hasattr(client, "last_session_year") else None
        if year is None:
            year = "Keine Sessions"

        if year not in clients_by_year:
            clients_by_year[year] = []
        clients_by_year[year].append(client)

    # Sort years in descending order (most recent first)
    # "Keine Sessions" should come last
    sorted_dict = dict(
        sorted(
            clients_by_year.items(),
            key=lambda x: (x[0] == "Keine Sessions", x[0]),
            reverse=True,
        )
    )

    return sorted_dict
