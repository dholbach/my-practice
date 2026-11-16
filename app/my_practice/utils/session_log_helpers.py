"""Rules behind the session-log views: which session a log belongs to, and its duration."""

from datetime import date

from ..models import Client, Session

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
