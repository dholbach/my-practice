"""Helper functions for client-related operations"""

from django.utils import timezone


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
        today = timezone.localdate()

    for client in clients:
        if hasattr(client, "last_session_date") and client.last_session_date:
            client.days_since_session = max(0, (today - client.last_session_date).days)
            client.last_session_year = client.last_session_date.year
        else:
            client.days_since_session = 9999  # No session
            client.last_session_year = None

    return clients


def group_clients_by_activity(clients, use_attention_category=True, track_session_inactivity=True):
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
        track_session_inactivity: If False, skips the days-since-last-session
            check entirely — only tag-based attention applies. Pass False for
            practices where clients aren't session-based (Practice.allows_free_form_items,
            P-122): those clients never have a session, so days_since_session
            is permanently 9999 and would otherwise flag them as needing
            attention forever.

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
            if needs_attention or (track_session_inactivity and client.days_since_session > 90):
                clients_needs_attention.append(client)
            else:
                clients_active_ok.append(client)

    return {
        "needs_attention": clients_needs_attention,
        "active_ok": clients_active_ok,
        "inactive": clients_inactive,
    }
