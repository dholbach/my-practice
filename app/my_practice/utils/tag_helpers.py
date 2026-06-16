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


def remove_no_next_session_tag(client: "Client") -> bool:
    """
    Remove the 'no-next-session' system tag from a client if they now have
    at least one future session scheduled (session_date >= today).

    Call this immediately after any new session is created so the tag
    disappears in real-time without waiting for the next
    ``update_client_tags`` management-command run.

    Args:
        client: The Client whose tag should be reconsidered.

    Returns:
        True if the tag was removed, False if it wasn't present or there
        are still no future sessions.
    """
    from ..models import ClientTag
    from ..models.session import Session

    try:
        tag = ClientTag.objects.get(slug="no-next-session")
    except ClientTag.DoesNotExist:
        return False

    if not client.tags.filter(pk=tag.pk).exists():
        return False

    today = timezone.now().date()
    has_future_sessions = Session.objects.filter(
        client=client,
        session_date__gte=today,
        cancelled=False,
    ).exists()

    if has_future_sessions:
        client.tags.remove(tag)
        return True

    return False


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
