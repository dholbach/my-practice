"""Views for the "for next time" reminders (P-006): add, tick off or reopen, delete."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import ScratchItem
from ..utils.for_next_time import clean_reminder
from ..utils.view_helpers import get_scoped_client, safe_next


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
def scratch_item_toggle(request, pk, item_pk):
    """Mark a reminder covered, or open it again."""
    client = get_scoped_client(request, pk)
    item = get_object_or_404(ScratchItem, pk=item_pk, client=client)
    item.done_at = None if item.done_at else timezone.now()
    item.save(update_fields=["done_at", "updated_at"])
    return _back(request, pk)


@require_POST
def scratch_item_delete(request, pk, item_pk):
    """Delete a reminder."""
    client = get_scoped_client(request, pk)
    get_object_or_404(ScratchItem, pk=item_pk, client=client).delete()
    return _back(request, pk)
