"""Helper functions for tag operations"""

from typing import TYPE_CHECKING

from django.db.models import QuerySet
from django.utils import timezone

if TYPE_CHECKING:
    from ..models import Client, ClientTag

# How far back to look for sessions missing a log entry.
# Used by the update_client_tags command (tag assignment) and the client list
# view (live 📝 indicator on client cards).
SESSION_LOG_WINDOW_DAYS = 14

# Sessions shorter than this threshold (in minutes) are treated as introductory
# calls (imported from Google Calendar as ~20-30 min slots) and do NOT require
# a session log entry.  Raise this value if regular sessions are still slipping
# through; lower it if introductory calls start getting flagged.
SESSION_LOG_MIN_DURATION = 30

# A client counts as "recently active" (and thus eligible for the
# no-next-session tag) if their last session is at most this many days ago.
# Shared by the update_client_tags command and sync_no_next_session_tag.
RECENT_ACTIVITY_WINDOW_DAYS = 90


def sync_no_next_session_tag(client: "Client") -> bool | None:
    """
    Add or remove the 'no-next-session' system tag for a single client,
    based on whether they have a future (non-cancelled) session scheduled.

    Mirrors the rule in the ``update_client_tags`` management command:
    the tag applies to active clients whose last session is within
    RECENT_ACTIVITY_WINDOW_DAYS and who have no future session.

    Call this after anything that changes a client's sessions (creation,
    cancellation, reschedule) so the tag updates in real time without
    waiting for the next ``update_client_tags`` run.

    Args:
        client: The Client whose tag should be reconsidered.

    Returns:
        True if the tag was added, False if it was removed, None if
        nothing changed (including when the tag doesn't exist yet —
        update_client_tags creates it on its next run).
    """
    from django.db.models import Max

    from ..models import ClientTag
    from ..models.session import Session

    tag = ClientTag.objects.filter(slug="no-next-session").first()
    if tag is None:
        return None

    today = timezone.now().date()
    has_future_sessions = Session.objects.filter(
        client=client,
        session_date__gte=today,
        cancelled=False,
    ).exists()
    has_tag = client.tags.filter(pk=tag.pk).exists()

    if has_future_sessions or not client.active:
        if has_tag:
            client.tags.remove(tag)
            return False
        return None

    last_session_date = Session.objects.filter(client=client, cancelled=False).aggregate(
        last=Max("session_date")
    )["last"]
    recently_active = (
        last_session_date is not None
        and (today - last_session_date).days <= RECENT_ACTIVITY_WINDOW_DAYS
    )
    if recently_active and not has_tag:
        client.tags.add(tag)
        return True
    return None


def sort_tags_by_category(
    tags: QuerySet | list["ClientTag"],
) -> list["ClientTag"]:
    """Sort tags by category priority (attention → general → exit), then alphabetically.

    Priority mapping:
    - attention: 1 (highest priority - urgent action needed)
    - general: 2 (medium priority - informational)
    - exit: 3 (lowest priority - archived/documentation)

    Args:
        tags: Queryset or list of ClientTag objects

    Returns:
        List of sorted tags
    """
    CATEGORY_PRIORITY = {
        "attention": 1,
        "general": 2,
        "exit": 3,
    }

    return sorted(
        tags,
        key=lambda t: (
            CATEGORY_PRIORITY.get(getattr(t, "category", "general"), 99),
            t.name.lower(),
        ),
    )
