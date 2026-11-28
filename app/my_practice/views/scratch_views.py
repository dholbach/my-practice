"""Views for the "for next time" reminders (P-006): add, tick off or reopen, delete."""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import Client, ScratchItem
from ..utils.for_next_time import clean_reminder
from ..utils.view_helpers import get_scoped_client, json_error, safe_next


def _back(request, client_pk):
    """Back to where the request came from, else the client page's profile tab."""
    fallback = reverse("client_detail", kwargs={"pk": client_pk}) + "#ptab-profil"
    return redirect(safe_next(request, fallback=fallback))


@require_POST
def scratch_item_create(request, pk):
    """Add a reminder for next time."""
    client = get_scoped_client(request, pk)
    text = clean_reminder(request.POST.get("text", ""))
    if not text:
        messages.error(request, _("Reminder must not be empty."))
    else:
        ScratchItem.objects.create(client=client, text=text)
    return _back(request, pk)


@require_POST
def scratch_quick_add(request):
    """Add a reminder from the command palette: ``code`` names the client, ``text`` is the note.

    Answers JSON with the line the palette shows, so the script holds no wording.
    The code is matched on its own (case-insensitively, within the current
    practice); an unknown code or empty text saves nothing.
    """
    code = request.POST.get("code", "").strip()
    client = Client.objects.for_current_practice(request).filter(client_code__iexact=code).first()
    if client is None:
        return json_error(_("No client with code %(code)s.") % {"code": code}, status=404)
    text = clean_reminder(request.POST.get("text", ""))
    if not text:
        return json_error(_("Reminder must not be empty."))
    ScratchItem.objects.create(client=client, text=text)
    return JsonResponse(
        {
            "success": True,
            "message": _("Reminder added for %(code)s.") % {"code": client.client_code},
        }
    )


@require_POST
def scratch_item_update(request, pk, item_pk):
    """Fix a reminder's wording."""
    client = get_scoped_client(request, pk)
    item = get_object_or_404(ScratchItem, pk=item_pk, client=client)
    text = clean_reminder(request.POST.get("text", ""))
    if not text:
        messages.error(request, _("Reminder must not be empty."))
    elif text != item.text:
        item.text = text
        item.save(update_fields=["text", "updated_at"])
    return _back(request, pk)


@require_POST
def scratch_item_toggle(request, pk, item_pk):
    """Mark a reminder covered, or open it again."""
    client = get_scoped_client(request, pk)
    item = get_object_or_404(ScratchItem, pk=item_pk, client=client)
    item.done_at = None if item.done_at else timezone.now()
    item.covered_in_session = None  # ticked here, or opened again: no log covered it
    item.save(update_fields=["done_at", "covered_in_session", "updated_at"])
    return _back(request, pk)


@require_POST
def scratch_item_delete(request, pk, item_pk):
    """Delete a reminder."""
    client = get_scoped_client(request, pk)
    get_object_or_404(ScratchItem, pk=item_pk, client=client).delete()
    return _back(request, pk)


def update_scratch_items(request, client) -> None:
    """Save the wording of open reminders edited in the log form's side panel."""
    edited = {
        int(name.removeprefix("scratch_edit_")): clean_reminder(value)
        for name, value in request.POST.items()
        if name.startswith("scratch_edit_") and name.removeprefix("scratch_edit_").isdigit()
    }
    for item in ScratchItem.objects.filter(client=client, pk__in=edited, done_at__isnull=True):
        # A cleared field leaves the reminder as it was: removing one is the client page's job.
        if edited[item.pk] and edited[item.pk] != item.text:
            item.text = edited[item.pk]
            item.save(update_fields=["text", "updated_at"])


def complete_scratch_items(request, client, session) -> None:
    """Mark the reminders ticked in the log form's side panel as covered in ``session``."""
    ids = [int(raw) for raw in request.POST.getlist("scratch_done") if raw.isdigit()]
    if ids:
        ScratchItem.objects.filter(client=client, pk__in=ids, done_at__isnull=True).update(
            done_at=timezone.now(), covered_in_session=session
        )


MAX_NEW_SCRATCH_ITEMS = 10


def add_scratch_items(request, client) -> None:
    """Create a reminder for next time per non-empty line of the log form's side panel."""
    lines = [clean_reminder(line) for line in request.POST.get("scratch_new", "").splitlines()]
    ScratchItem.objects.bulk_create(
        [ScratchItem(client=client, text=line) for line in lines if line][:MAX_NEW_SCRATCH_ITEMS]
    )
