"""Rules behind the session-log views: which session a log belongs to, its duration, and the
context shown beside the form."""

from datetime import date

from ..models import Client, ClientProfile, Session, SessionLog
from .markdown_sections import has_content, split_sections

# A whole day: room for intensive or workshop days, while keeping out typos and values
# that would overflow the integer column. The duration inputs use the same max.
MAX_SESSION_MINUTES = 24 * 60


def parse_duration(raw: str | None) -> int | None:
    """Return the duration in minutes, or None unless it is 1 to MAX_SESSION_MINUTES."""
    try:
        minutes = int((raw or "").strip())
    except ValueError:
        return None
    return minutes if 0 < minutes <= MAX_SESSION_MINUTES else None


def find_or_create_session(client: Client, session_date: date, duration: int) -> Session:
    """The session a new log on ``session_date`` attaches to, created if there is none.

    A client can have several sessions on one date (calendar import keys on date +
    time, and a reschedule can leave a cancelled twin behind), so this takes the
    first live one still without a log rather than get_or_create, which raises
    MultipleObjectsReturned. Cancelled sessions are only considered when no live
    one exists that day.
    """
    same_day = Session.objects.filter(client=client, session_date=session_date).order_by(
        "session_time", "pk"
    )
    live = same_day.filter(cancelled=False)
    pool = live if live.exists() else same_day
    session = pool.filter(log__isnull=True).first() or pool.first()
    if session is None:
        session = Session.objects.create(
            client=client, session_date=session_date, duration=duration
        )
    return session


def is_session_billed(session: Session) -> bool:
    """True if any invoice item (cancelled invoices included) points at the session."""
    return session.invoice_items.exists()


def set_session_duration(session: Session, minutes: int) -> bool:
    """Save a new duration; False, and nothing saved, once the session is billed.

    session.duration feeds the session count and the GebüH fee of the invoice item,
    whose service type, rate and total are resolved from it at billing time and not
    recalculated, so it is frozen until the invoice item is removed.
    """
    if is_session_billed(session):
        return False
    session.duration = minutes
    session.save(update_fields=["duration"])
    return True


# What the form shows from the case notes while a log is written: (profile field, heading).
CASE_SHEET_EXCERPT: tuple[tuple[str, str], ...] = (
    ("intake_notes", "Arbeitshypothese"),
    ("intake_notes", "Aktuelle Trigger"),
    ("intake_notes", "Ressourcen"),
    ("case_notes", "Zukünftige Arbeit / Fragen"),
)
RECENT_LOGS_SHOWN = 3


def case_sheet_excerpt(client: Client) -> list[tuple[str, str]]:
    """The filled ``(heading, text)`` sections of CASE_SHEET_EXCERPT for the client.

    Reads the profile without creating it: opening a log form must not write.
    """
    profile = ClientProfile.objects.filter(client=client).first()
    if profile is None:
        return []
    parsed = {
        field: split_sections(getattr(profile, field))
        for field in {f for f, _h in CASE_SHEET_EXCERPT}
    }
    return [
        (heading, parsed[field][heading])
        for field, heading in CASE_SHEET_EXCERPT
        if has_content(parsed[field].get(heading, ""))
    ]


def build_log_context(client: Client, *, before: date | None, exclude_log_pk: int | None) -> dict:
    """What to show beside the log form: the last logs, their ideas, the case sheet excerpt.

    ``before`` limits it to sessions dated earlier (the day being logged), None for all;
    ``exclude_log_pk`` keeps the log being edited out of its own context.
    """
    logs = SessionLog.objects.filter(session__client=client).select_related("session")
    if before is not None:
        logs = logs.filter(session__session_date__lt=before)
    if exclude_log_pk is not None:
        logs = logs.exclude(pk=exclude_log_pk)
    recent = list(logs.order_by("-session__session_date", "-pk")[:RECENT_LOGS_SHOWN])
    return {
        "previous_log": recent[0] if recent and recent[0].next_session_ideas.strip() else None,
        "recent_logs": [log for log in recent if log.summary],
        "case_sheet_excerpt": case_sheet_excerpt(client),
    }
