"""What to pick up next time with a client, gathered from three places (P-006).

Open reminders (``ScratchItem``) are the only ones that can be ticked off here. The last
session's "ideas for next time" and the case notes' future-work section are shown beside
them so the whole list is in one spot, but they live where they were written.
"""

from ..models import Client, ScratchItem
from .session_log_helpers import FUTURE_WORK_HEADING, build_log_context

COVERED_SHOWN = 10


def build_for_next_time(client: Client) -> dict:
    """The open and recently covered reminders, last ideas and future work of a client."""
    covered = list(
        ScratchItem.objects.filter(client=client, done_at__isnull=False).order_by("-done_at")[
            :COVERED_SHOWN
        ]
    )
    context = build_log_context(client, before=None, exclude_log_pk=None)
    future_work = next(
        (text for heading, text in context["case_sheet_excerpt"] if heading == FUTURE_WORK_HEADING),
        "",
    )
    return {
        "open_items": context["scratch_items"],
        "covered_items": covered,
        "last_ideas_log": context["previous_log"],
        "future_work": future_work,
    }
