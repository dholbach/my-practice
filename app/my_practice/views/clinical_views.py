"""
Clinical documentation views (P-009).

Views for:
  - SessionLog: create/edit per session
  - ClientNote: per-client free-text notes
  - Triage summary: printable emergency overview (no Fernet access)
"""

from datetime import date

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import (
    Client,
    ClientNote,
    PendingCalendarEvent,
    Session,
    SessionLog,
)
from ..models.clinical import SESSION_LOG_PROMPTS, MoodTag
from ..utils.session_log_helpers import (
    build_log_context,
    find_or_create_session,
    parse_duration,
    set_session_duration,
)
from ..utils.view_helpers import get_scoped_client, safe_next
from .scratch_views import add_scratch_items, complete_scratch_items, update_scratch_items
from .supervision_views import add_supervision_question


def _session_log_choices(request, default_type: str) -> tuple[str | None, list[str]]:
    """Return the posted session type (None if not a known one) and the known mood tags.

    The form only offers the choices, but the view saves without a ModelForm, so an
    unknown session type would be stored as-is, or abort with a DataError when too long.
    """
    session_type = request.POST.get("session_type", default_type)
    if session_type not in SessionLog.SessionType.values:
        session_type = None
    mood_tags = [tag for tag in request.POST.getlist("mood_tags") if tag in MoodTag.values]
    return session_type, mood_tags


def _summary(request, default: str) -> str:
    """The posted one-liner, cut to its field length (the encrypted column has no limit)."""
    max_length = SessionLog._meta.get_field("summary").max_length
    return request.POST.get("summary", default)[:max_length]


_NARRATIVE_FIELDS = ("content", "interventions", "therapist_reflection", "next_session_ideas")


# A prompt chip writes "Label: " into a field; clicked and then not filled in, that is not a note.
_BARE_PROMPTS = {f"{label}:" for label, _field in SESSION_LOG_PROMPTS}


def _narrative(request, current: SessionLog | None = None) -> dict[str, str]:
    """The posted narrative fields; a field not posted keeps ``current``'s value (or "").

    A field holding nothing but a prompt chip's label is saved as empty.
    """
    posted = {
        field: request.POST.get(field, getattr(current, field) if current else "")
        for field in _NARRATIVE_FIELDS
    }
    return {
        field: "" if value.strip() in _BARE_PROMPTS else value for field, value in posted.items()
    }


def session_log_create(request, pk):
    """
    Create a new SessionLog entry for a client.

    GET: Render the log form with boilerplate pre-fill and mood tag choices.
         Accepts ?session_date=YYYY-MM-DD to pre-select a date.
    POST: Create Session (find-or-create) + SessionLog, redirect back to client detail.
    """
    client = get_scoped_client(request, pk)

    if request.method == "POST":
        session_date_str = request.POST.get("session_date")
        if not session_date_str:
            messages.error(request, _("Session date is required."))
            return redirect("client_detail", pk=pk)

        try:
            session_date = date.fromisoformat(session_date_str)
        except ValueError:
            messages.error(request, _("Invalid date."))
            return redirect("client_detail", pk=pk)

        duration = parse_duration(request.POST.get("duration", "60"))
        session_type, mood_tags = _session_log_choices(request, SessionLog.SessionType.STANDARD)
        if duration is None:
            messages.error(request, _("Invalid duration."))
            return redirect("client_detail", pk=pk)
        if session_type is None:
            messages.error(request, _("Invalid session type."))
            return redirect("client_detail", pk=pk)

        session = find_or_create_session(client, session_date, duration)

        # Prevent duplicate logs
        if hasattr(session, "log"):
            messages.warning(request, _("A log already exists for this session."))
            return redirect("session_log_edit", client_pk=pk, log_pk=session.log.pk)

        SessionLog.objects.create(
            session=session,
            session_type=session_type,
            mood_tags=mood_tags,
            summary=_summary(request, ""),
            **_narrative(request),
        )

        add_supervision_question(request, client)
        update_scratch_items(request, client)
        complete_scratch_items(request, client, session)
        add_scratch_items(request, client)

        messages.success(
            request,
            _("Session log for %(date)s saved.") % {"date": session_date.strftime("%d.%m.%Y")},
        )
        # The client page offers the optional "anything for the case sheet?" step for this session.
        return redirect(
            reverse("client_detail", kwargs={"pk": pk}) + f"?digest={session.pk}#digest-card"
        )

    # GET — render form
    prefill_date = request.GET.get("session_date", "")
    prefill_duration = 60
    try:
        date.fromisoformat(prefill_date)
    except ValueError:
        prefill_date = ""

    # If pre-filling from a calendar event, inherit its duration
    if prefill_date:
        cal_event = (
            PendingCalendarEvent.objects.filter(
                matched_client=client,
                event_date=prefill_date,
            )
            .order_by("-fetched_at")
            .first()
        )
        if cal_event:
            prefill_duration = cal_event.duration_minutes

    context = {
        "client": client,
        "prefill_date": prefill_date,
        "prefill_duration": prefill_duration,
        "session_type_choices": SessionLog.SessionType.choices,
        "mood_tag_choices": MoodTag.choices,
        "prompts": SESSION_LOG_PROMPTS,
        **build_log_context(
            client,
            before=date.fromisoformat(prefill_date) if prefill_date else None,
            exclude_log_pk=None,
        ),
    }
    return render(request, "my_practice/session_log_form.html", context)


def session_log_edit(request, client_pk, log_pk):
    """Edit an existing SessionLog entry."""
    client = get_scoped_client(request, client_pk)
    log = get_object_or_404(SessionLog, pk=log_pk, session__client=client)

    if request.method == "POST":
        # Bad metadata never costs the narrative text: the log is saved, the field kept.
        session_type, mood_tags = _session_log_choices(request, log.session_type)
        log.session_type = session_type or log.session_type
        log.mood_tags = mood_tags
        log.summary = _summary(request, log.summary)
        for field, value in _narrative(request, log).items():
            setattr(log, field, value)
        log.save()

        add_supervision_question(request, client)
        update_scratch_items(request, client)
        complete_scratch_items(request, client, log.session)
        add_scratch_items(request, client)

        duration_str = request.POST.get("duration", "").strip()
        new_duration = parse_duration(duration_str) if duration_str else None
        if duration_str and new_duration is None:
            messages.warning(request, _("Invalid duration."))
        elif (
            new_duration is not None
            and new_duration != log.session.duration
            and not set_session_duration(log.session, new_duration)  # False: already billed
        ):
            messages.warning(
                request,
                _(
                    "The duration was not changed: this session has already been billed. "
                    "Remove the invoice item first."
                ),
            )

        messages.success(request, _("Session log updated."))
        return redirect(reverse("client_detail", kwargs={"pk": client_pk}) + "#ptab-protokoll")

    context = {
        "client": client,
        "log": log,
        "session_type_choices": SessionLog.SessionType.choices,
        "mood_tag_choices": MoodTag.choices,
        "prompts": SESSION_LOG_PROMPTS,
        "is_edit": True,
        **build_log_context(client, before=log.session.session_date, exclude_log_pk=log.pk),
    }
    return render(request, "my_practice/session_log_form.html", context)


@require_POST
def client_note_create(request, pk):
    """Create a dated freeform note for a client."""
    client = get_scoped_client(request, pk)
    note_date_str = request.POST.get("note_date", "").strip()
    content = request.POST.get("content", "").strip()

    if not content or not note_date_str:
        messages.error(request, _("Date and content are required."))
        return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#ptab-protokoll")

    try:
        note_date = date.fromisoformat(note_date_str)
    except ValueError:
        messages.error(request, _("Invalid date."))
        return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#ptab-protokoll")

    ClientNote.objects.create(client=client, note_date=note_date, content=content)
    messages.success(request, _("Note saved."))
    return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#ptab-protokoll")


@require_POST
def client_note_update(request, pk, note_pk):
    """Update content and date of a client note."""
    client = get_scoped_client(request, pk)
    note = get_object_or_404(ClientNote, pk=note_pk, client=client)

    content = request.POST.get("content", "").strip()
    note_date_str = request.POST.get("note_date", "").strip()

    if not content:
        messages.error(request, _("Content must not be empty."))
        return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#ptab-protokoll")

    if note_date_str:
        try:
            note.note_date = date.fromisoformat(note_date_str)
        except ValueError:
            messages.error(request, _("Invalid date."))
            return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#ptab-protokoll")

    note.content = content
    note.save()
    messages.success(request, _("Note updated."))
    return redirect(
        safe_next(
            request,
            fallback=reverse("client_detail", kwargs={"pk": pk}) + "#ptab-protokoll",
        )
    )


@require_POST
def client_note_delete(request, pk, note_pk):
    """Delete a dated client note."""
    client = get_scoped_client(request, pk)
    note = get_object_or_404(ClientNote, pk=note_pk, client=client)
    note.delete()
    messages.success(request, _("Note deleted."))
    return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#ptab-protokoll")


def client_triage_summary(request):
    """
    Printable triage summary for emergency use (P-010).

    Shows last-5-session mood tag patterns per client.
    Uses ONLY unencrypted fields — no Fernet access required.
    Sorted by client code; highlights clients with recent crisis mood tags.
    """

    from django.db.models import Prefetch

    clients = (
        Client.objects.for_current_practice(request)
        .filter(active=True)
        .prefetch_related(
            Prefetch(
                "sessions",
                queryset=Session.objects.prefetch_related("log").order_by("-session_date"),
                to_attr="recent_sessions_list",
            )
        )
        .order_by("client_code")
    )

    triage_data = []
    for client in clients:
        recent = getattr(client, "recent_sessions_list", [])[:5]
        # Collect unencrypted metadata only
        session_snapshots = []
        for s in recent:
            log = getattr(s, "log", None)
            session_snapshots.append(
                {
                    "date": s.session_date,
                    "session_type": log.session_type if log else None,
                    "mood_tags": log.mood_tags if log else [],
                    "has_crisis_tag": "krise" in (log.mood_tags if log else []),
                }
            )
        triage_data.append(
            {
                "client": client,
                "sessions": session_snapshots,
                "has_crisis_tag_recent": any(s["has_crisis_tag"] for s in session_snapshots),
            }
        )

    context = {
        "triage_data": triage_data,
        "generated_date": timezone.localdate(),
    }
    return render(request, "my_practice/client_triage.html", context)
