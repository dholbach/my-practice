"""The review of a client's case sheet (P-006): what happened since the last one.

A review is a quiet, optional pause to go through the sessions since the last one and
carry what matters into the case sheet. Nothing here nags: the client page only offers it
once a few sessions have piled up.
"""

from dataclasses import dataclass, field
from datetime import date

from django.utils import timezone

from ..models import CaseReview, Client, ClinicalFact, Session, SupervisionItem
from .calculations import held_sessions
from .case_sheet import build_case_sheet, describe_fact

# The client page offers a review once this many sessions have been held since the last one.
INVITE_AFTER_SESSIONS = 3
HYPOTHESIS = "hypothesis"
IN_THEIR_WORDS = "in_their_words"


def last_review(client: Client) -> CaseReview | None:
    """The most recent review, or None if the sheet was never reviewed."""
    return client.case_reviews.first()


def sessions_since(client: Client, review: CaseReview | None, *, today: date | None = None):
    """Sessions held after ``review`` (all of them if None): not cancelled, none after today."""
    sessions = held_sessions(client.sessions, today=today)
    if review is not None:
        sessions = sessions.filter(session_date__gt=review.reviewed_on)
    return sessions.select_related("log").order_by("session_date", "pk")


def review_invitation(client: Client) -> dict | None:
    """``{"count", "since"}`` when enough sessions have piled up since the last review, else None."""
    review = last_review(client)
    count = sessions_since(client, review).count()
    if count < INVITE_AFTER_SESSIONS:
        return None
    return {"count": count, "since": review.reviewed_on if review else None}


@dataclass
class SessionBlock:
    """One session of the review: its text broken into lines that can go to the case sheet."""

    session: Session
    summary: str = ""
    mood_tags: list[str] = field(default_factory=list)
    note_lines: list[str] = field(default_factory=list)
    idea_lines: list[str] = field(default_factory=list)
    reflection: str = ""  # shown to read, never offered for the sheet: it stays out of an export

    @property
    def has_log(self) -> bool:
        return bool(self.summary or self.note_lines or self.idea_lines or self.reflection)


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _block(session: Session) -> SessionBlock:
    log = getattr(session, "log", None)  # no log: RelatedObjectDoesNotExist, an AttributeError
    if log is None:
        return SessionBlock(session=session)
    return SessionBlock(
        session=session,
        summary=log.summary,
        mood_tags=list(log.mood_tags),
        note_lines=_lines(log.content),
        idea_lines=_lines(log.next_session_ideas),
        reflection=log.therapist_reflection,
    )


def build_review(client: Client, *, today: date | None = None) -> dict:
    """Everything the review page shows."""
    today = today or timezone.localdate()
    review = last_review(client)
    sheet = build_case_sheet(client)

    hypothesis = next(row for row in sheet if row.row.kind == HYPOTHESIS).cells[0]
    words = list(
        ClinicalFact.objects.filter(client=client, kind=IN_THEIR_WORDS).order_by("noted_on", "pk")
    )
    then_and_now = (words[0], words[-1]) if len(words) >= 2 else None
    still_empty = [
        row.row.label
        for row in sheet
        if row.row.kind != "notes" and not any(cell.lines for cell in row.cells)
    ]
    return {
        "last_review": review,
        "blocks": [_block(session) for session in sessions_since(client, review, today=today)],
        "sheet": sheet,
        "hypothesis": hypothesis,
        "then_and_now": then_and_now,
        "still_empty": still_empty,
        "added_today": added_on(client, today),
        "open_supervision": list(
            client.supervision_items.filter(status=SupervisionItem.Status.OFFEN)
        ),
    }


def added_on(client: Client, day: date) -> list[dict]:
    """The lines noted on ``day``, with where they went (the changes of a review in progress)."""
    return [
        describe_fact(fact)
        for fact in ClinicalFact.objects.filter(client=client, noted_on=day).order_by("pk")
    ]


def finish_review(client: Client, *, today: date | None = None) -> CaseReview:
    """Record that the sheet was reviewed today (once per day)."""
    review, _created = CaseReview.objects.get_or_create(
        client=client, reviewed_on=today or timezone.localdate()
    )
    return review
