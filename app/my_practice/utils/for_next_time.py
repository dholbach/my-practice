"""What to pick up next time with a client, gathered from three places (P-006).

Open reminders (``ScratchItem``) are the only ones that can be ticked off here. The last
session's "ideas for next time" and the case sheet's future-work row are shown beside
them so the whole list is in one spot, but they live where they were written.
"""

import re

from ..models import Client, ScratchItem
from .case_sheet import active_lines, lines_to_markdown
from .session_log_helpers import build_log_context

# Folded away on the card, so showing nearly everything costs no room.
COVERED_SHOWN = 100

# A list marker typed or pasted in front of a reminder: "- ", " - ", "* ", "• ". It must be
# followed by a space or end the line, so "-5 Grad" or "*wichtig*" keep their first character.
_LIST_MARKER = re.compile(r"^\s*[-*•](?:\s+|$)")


def clean_reminder(raw: str) -> str:
    """One reminder as typed: list marker and surrounding whitespace removed, cut to length."""
    max_length = ScratchItem._meta.get_field("text").max_length
    return _LIST_MARKER.sub("", raw).strip()[:max_length]


def build_for_next_time(client: Client) -> dict:
    """The open and recently covered reminders, last ideas and future work of a client."""
    covered = list(
        ScratchItem.objects.filter(client=client, done_at__isnull=False)
        .select_related("covered_in_session__log")
        .order_by("-done_at")[:COVERED_SHOWN]
    )
    context = build_log_context(client, before=None, exclude_log_pk=None)
    future_work_lines = active_lines(client, "future_work")
    future_work = lines_to_markdown(future_work_lines) if future_work_lines else ""
    return {
        "open_items": context["scratch_items"],
        "covered_items": covered,
        "last_ideas_log": context["previous_log"],
        "future_work": future_work,
    }
