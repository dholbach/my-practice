"""
Clinical documentation views (P-009).

Views for:
  - ClientProfile: get/create on client detail page, save via POST
  - SessionLog: create/edit per session
  - SupervisionItem: create per client, toggle status
  - Supervision queue: cross-client view of open items
  - Triage summary: printable emergency overview (no Fernet access)
"""

from datetime import date

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..utils.view_helpers import safe_next

from ..models import (
    Client,
    ClientNote,
    ClientProfile,
    PendingCalendarEvent,
    Session,
    SessionLog,
    SupervisionItem,
)
from ..models.clinical import (
    SESSION_LOG_TEMPLATE,
    MoodTag,
)


def _get_scoped_client(request, pk):
    """Get a practice-scoped client or 404."""
    return get_object_or_404(Client.objects.for_current_practice(request), pk=pk)


# ─── ClientProfile ─────────────────────────────────────────────────────────────


@require_POST
def client_profile_save(request, pk):
    """Save ClientProfile fields for a client. Creates profile if it doesn't exist."""
    client = _get_scoped_client(request, pk)
    profile, _created = ClientProfile.objects.get_or_create(client=client)

    profile.intake_notes = request.POST.get("intake_notes", profile.intake_notes)
    profile.case_notes = request.POST.get("case_notes", profile.case_notes)
    profile.arbeitsdiagnose = request.POST.get("arbeitsdiagnose", profile.arbeitsdiagnose)
    profile.save()

    messages.success(request, _("Client profile saved."))
    return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#tab-profil")


# ─── SessionLog ────────────────────────────────────────────────────────────────


def session_log_create(request, pk):
    """
    Create a new SessionLog entry for a client.

    GET: Render the log form with boilerplate pre-fill and mood tag choices.
         Accepts ?session_date=YYYY-MM-DD to pre-select a date.
    POST: Create Session (find-or-create) + SessionLog, redirect back to client detail.
    """
    client = _get_scoped_client(request, pk)

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

        # Find or create Session for this client + date
        session, _created = Session.objects.get_or_create(
            client=client,
            session_date=session_date,
            defaults={
                "duration": int(request.POST.get("duration", 60)),
            },
        )

        # Prevent duplicate logs
        if hasattr(session, "log"):
            messages.warning(request, _("A log already exists for this session."))
            return redirect("session_log_edit", client_pk=pk, log_pk=session.log.pk)

        mood_tags = request.POST.getlist("mood_tags")
        SessionLog.objects.create(
            session=session,
            session_type=request.POST.get("session_type", SessionLog.SessionType.STANDARD),
            mood_tags=mood_tags,
            summary=request.POST.get("summary", ""),
            content=request.POST.get("content", ""),
            interventions=request.POST.get("interventions", ""),
            therapist_reflection=request.POST.get("therapist_reflection", ""),
            next_session_ideas=request.POST.get("next_session_ideas", ""),
        )

        supervision_question = request.POST.get("supervision_question", "").strip()
        if supervision_question:
            SupervisionItem.objects.create(client=client, content=supervision_question)

        messages.success(
            request,
            _("Session log for %(date)s saved.") % {"date": session_date.strftime("%d.%m.%Y")},
        )
        return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#tab-sitzungen")

    # GET — render form
    prefill_date = request.GET.get("session_date", "")
    prefill_duration = 60

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
        "content_template": SESSION_LOG_TEMPLATE,
    }
    return render(request, "my_practice/session_log_form.html", context)


def session_log_edit(request, client_pk, log_pk):
    """Edit an existing SessionLog entry."""
    client = _get_scoped_client(request, client_pk)
    log = get_object_or_404(SessionLog, pk=log_pk, session__client=client)

    if request.method == "POST":
        log.session_type = request.POST.get("session_type", log.session_type)
        log.mood_tags = request.POST.getlist("mood_tags")
        log.summary = request.POST.get("summary", log.summary)
        log.content = request.POST.get("content", log.content)
        log.interventions = request.POST.get("interventions", log.interventions)
        log.therapist_reflection = request.POST.get(
            "therapist_reflection", log.therapist_reflection
        )
        log.next_session_ideas = request.POST.get("next_session_ideas", log.next_session_ideas)
        log.save()

        supervision_question = request.POST.get("supervision_question", "").strip()
        if supervision_question:
            SupervisionItem.objects.create(client=client, content=supervision_question)

        # Update session duration if provided
        duration_str = request.POST.get("duration", "").strip()
        if duration_str:
            try:
                new_duration = int(duration_str)
                if new_duration > 0:
                    log.session.duration = new_duration
                    log.session.save(update_fields=["duration"])
            except ValueError:
                pass

        messages.success(request, _("Session log updated."))
        return redirect(reverse("client_detail", kwargs={"pk": client_pk}) + "#tab-sitzungen")

    context = {
        "client": client,
        "log": log,
        "session_type_choices": SessionLog.SessionType.choices,
        "mood_tag_choices": MoodTag.choices,
        "is_edit": True,
    }
    return render(request, "my_practice/session_log_form.html", context)


# ─── SupervisionItem ───────────────────────────────────────────────────────────


@require_POST
def supervision_item_create(request, pk):
    """Create a new SupervisionItem for a client."""
    client = _get_scoped_client(request, pk)
    content = request.POST.get("content", "").strip()
    if not content:
        messages.error(request, _("Content must not be empty."))
        return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#tab-supervision")

    SupervisionItem.objects.create(client=client, content=content)
    messages.success(request, _("Supervision topic added."))
    return redirect(
        safe_next(
            request,
            fallback=reverse("client_detail", kwargs={"pk": pk}) + "#tab-supervision",
        )
    )


@require_POST
def supervision_item_delete(request, pk, item_pk):
    """Delete a SupervisionItem."""
    client = _get_scoped_client(request, pk)
    item = get_object_or_404(SupervisionItem, pk=item_pk, client=client)
    item.delete()
    messages.success(request, _("Supervision topic deleted."))
    return redirect(
        safe_next(
            request,
            fallback=reverse("client_detail", kwargs={"pk": pk}) + "#tab-supervision",
        )
    )


@require_POST
def supervision_item_toggle(request, pk, item_pk):
    """Toggle SupervisionItem status between offen and besprochen."""
    client = _get_scoped_client(request, pk)
    item = get_object_or_404(SupervisionItem, pk=item_pk, client=client)
    item.status = (
        SupervisionItem.Status.BESPROCHEN
        if item.status == SupervisionItem.Status.OFFEN
        else SupervisionItem.Status.OFFEN
    )
    item.save(update_fields=["status"])

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": item.status, "label": item.get_status_display()})
    return redirect(
        safe_next(
            request,
            fallback=reverse("client_detail", kwargs={"pk": pk}) + "#tab-supervision",
        )
    )


# ─── Supervision queue ─────────────────────────────────────────────────────────


def supervision_queue(request):
    """
    Cross-client supervision queue.

    Shows all open SupervisionItems grouped by client.
    Does not require Fernet key for rendering the grouping structure —
    item content is decrypted lazily when accessed in the template.
    """
    open_items = (
        SupervisionItem.objects.filter(
            client__in=Client.objects.for_current_practice(request),
            status=SupervisionItem.Status.OFFEN,
        )
        .select_related("client")
        .order_by("client__client_code", "-created_at")
    )

    # Group by client
    from itertools import groupby

    grouped = []
    for client, items in groupby(open_items, key=lambda x: x.client):
        grouped.append({"client": client, "items": list(items)})

    context = {
        "grouped_items": grouped,
        "total_open": open_items.count(),
    }
    return render(request, "my_practice/supervision_queue.html", context)


# ─── ClientNote ────────────────────────────────────────────────────────────────


@require_POST
def client_note_create(request, pk):
    """Create a dated freeform note for a client."""
    client = _get_scoped_client(request, pk)
    note_date_str = request.POST.get("note_date", "").strip()
    content = request.POST.get("content", "").strip()

    if not content or not note_date_str:
        messages.error(request, _("Date and content are required."))
        return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#tab-notizen")

    try:
        note_date = date.fromisoformat(note_date_str)
    except ValueError:
        messages.error(request, _("Invalid date."))
        return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#tab-notizen")

    note_type = request.POST.get("note_type", ClientNote.NoteType.NOTE)
    if note_type not in ClientNote.NoteType.values:
        note_type = ClientNote.NoteType.NOTE

    ClientNote.objects.create(
        client=client, note_date=note_date, content=content, note_type=note_type
    )

    if note_type == ClientNote.NoteType.SUPERVISION:
        messages.success(request, _("Supervision note saved."))
        return redirect(
            safe_next(
                request,
                fallback=reverse("client_detail", kwargs={"pk": pk}) + "#tab-protokoll",
            )
        )

    messages.success(request, _("Note saved."))
    return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#tab-notizen")


@require_POST
def client_note_update(request, pk, note_pk):
    """Update content and date of a client note."""
    client = _get_scoped_client(request, pk)
    note = get_object_or_404(ClientNote, pk=note_pk, client=client)

    content = request.POST.get("content", "").strip()
    note_date_str = request.POST.get("note_date", "").strip()

    if not content:
        messages.error(request, _("Content must not be empty."))
        return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#tab-protokoll")

    if note_date_str:
        try:
            note.note_date = date.fromisoformat(note_date_str)
        except ValueError:
            messages.error(request, _("Invalid date."))
            return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#tab-protokoll")

    note.content = content
    note.save()
    messages.success(request, _("Note updated."))
    return redirect(
        safe_next(
            request,
            fallback=reverse("client_detail", kwargs={"pk": pk}) + "#tab-protokoll",
        )
    )


@require_POST
def client_note_delete(request, pk, note_pk):
    """Delete a dated client note."""
    client = _get_scoped_client(request, pk)
    note = get_object_or_404(ClientNote, pk=note_pk, client=client)
    note.delete()
    messages.success(request, _("Note deleted."))
    return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#tab-notizen")


@require_POST
def session_log_delete(request, client_pk, log_pk):
    """Delete a SessionLog entry (and its linked Session if it has no InvoiceItem)."""
    client = _get_scoped_client(request, client_pk)
    log = get_object_or_404(SessionLog, pk=log_pk, session__client=client)
    session = log.session
    log.delete()
    # Also remove the bare Session if it was created solely for this log
    # (i.e. no InvoiceItem is linked — not billed)
    if not session.invoice_items.exists():
        session.delete()
    messages.success(request, _("Session log deleted."))
    return redirect(reverse("client_detail", kwargs={"pk": client_pk}) + "#tab-sitzungen")


@require_POST
def session_duration_edit(request, pk, session_pk):
    """Update a session's duration. Used to correct calendar-imported sessions."""
    client = _get_scoped_client(request, pk)
    session = get_object_or_404(Session, pk=session_pk, client=client)
    try:
        new_duration = int(request.POST.get("duration", 0))
        if new_duration > 0:
            session.duration = new_duration
            session.save(update_fields=["duration"])
            messages.success(
                request,
                _("Session duration updated to %(min)s min.") % {"min": new_duration},
            )
        else:
            messages.error(request, _("Invalid duration."))
    except ValueError, TypeError:
        messages.error(request, _("Invalid duration."))
    return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#tab-sitzungen")


@require_POST
def session_delete(request, client_pk, session_pk):
    """
    Delete a bare Session (no log, or log without billed invoice item).

    Blocked if the session has a linked InvoiceItem (already billed).
    The SessionLog cascades automatically if present.
    """
    client = _get_scoped_client(request, client_pk)
    session = get_object_or_404(Session, pk=session_pk, client=client)
    if session.invoice_items.exists():
        messages.error(
            request,
            _("Session of %(date)s cannot be deleted: it has already been billed. "
              "Remove the invoice item first.")
            % {"date": session.session_date.strftime("%d.%m.%Y")},
        )
    else:
        date_str = session.session_date.strftime("%d.%m.%Y")
        session.delete()  # SessionLog cascades via OneToOne(on_delete=CASCADE)
        messages.success(request, _("Session of %(date)s deleted.") % {"date": date_str})
    return redirect(reverse("client_detail", kwargs={"pk": client_pk}) + "#tab-sitzungen")


@require_POST
def session_log_mark_noshow(request, client_pk, log_pk):
    """Quick-mark a session log as Ausfall / Absage."""
    client = _get_scoped_client(request, client_pk)
    log = get_object_or_404(SessionLog, pk=log_pk, session__client=client)
    log.session_type = SessionLog.SessionType.AUSFALL
    log.save(update_fields=["session_type"])
    messages.success(request, _("Marked as no-show / cancellation."))
    return redirect(reverse("client_detail", kwargs={"pk": client_pk}) + "#tab-sitzungen")


@require_POST
def session_bill(request, pk, session_pk):
    """
    Add an unbilled Session to the client's draft invoice (P-036 Phase 2).

    POST-only. Calls bill_session() helper which determines service type / rate
    from the linked PendingCalendarEvent and creates InvoiceItem + PracticeTodo.
    """
    from ..utils.calendar_import_helpers import bill_session as _bill_session

    client = _get_scoped_client(request, pk)
    session = get_object_or_404(Session, pk=session_pk, client=client)
    success, message = _bill_session(session, request.current_practice)
    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#tab-sitzungen")


# ─── Triage summary ────────────────────────────────────────────────────────────


def client_triage_summary(request):
    """
    Printable triage summary for emergency use (P-010).

    Shows last-5-session mood tag patterns per client.
    Uses ONLY unencrypted fields — no Fernet access required.
    Sorted by client code; highlights clients with recent crisis mood tags.
    """
    from datetime import date

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
        "generated_date": date.today(),
    }
    return render(request, "my_practice/client_triage.html", context)


@require_POST
def session_toggle_billable(request, client_pk, session_pk):
    """Toggle Session.billable — marks intro calls / non-billable sessions as excluded."""
    client = get_object_or_404(Client, pk=client_pk)
    session = get_object_or_404(Session, pk=session_pk, client=client)
    session.billable = not session.billable
    session.save(update_fields=["billable"])
    return redirect(safe_next(request, fallback=reverse("client_detail", kwargs={"pk": client_pk})))
