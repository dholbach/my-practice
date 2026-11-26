"""Supervision views (P-009): items per client (create, toggle, resolve, delete) and the
cross-client queue of open ones."""

from datetime import date

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import (
    Client,
    SupervisionItem,
)
from ..utils.view_helpers import get_scoped_client, safe_next


def add_supervision_question(request, client) -> None:
    """File the posted supervision question, if any, as an open item for the client."""
    question = request.POST.get("supervision_question", "").strip()
    if question:
        SupervisionItem.objects.create(client=client, content=question)


@require_POST
def supervision_item_create(request, pk):
    """Create a new SupervisionItem for a client."""
    client = get_scoped_client(request, pk)
    content = request.POST.get("content", "").strip()
    if not content:
        messages.error(request, _("Content must not be empty."))
        return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#ptab-protokoll")

    SupervisionItem.objects.create(client=client, content=content)
    messages.success(request, _("Supervision topic added."))
    return redirect(
        safe_next(
            request,
            fallback=reverse("client_detail", kwargs={"pk": pk}) + "#ptab-protokoll",
        )
    )


@require_POST
def supervision_item_delete(request, pk, item_pk):
    """Delete a SupervisionItem."""
    client = get_scoped_client(request, pk)
    item = get_object_or_404(SupervisionItem, pk=item_pk, client=client)
    item.delete()
    messages.success(request, _("Supervision topic deleted."))
    return redirect(
        safe_next(
            request,
            fallback=reverse("client_detail", kwargs={"pk": pk}) + "#ptab-protokoll",
        )
    )


@require_POST
def supervision_item_toggle(request, pk, item_pk):
    """
    Toggle SupervisionItem status between offen and besprochen.

    Quick one-click toggle with no resolution notes — used for reopening an
    item, and for marking one discussed from the cross-client queue where a
    notes form would be too heavy. To mark discussed with resolution notes
    from the client detail page, use supervision_item_resolve instead.
    """
    client = get_scoped_client(request, pk)
    item = get_object_or_404(SupervisionItem, pk=item_pk, client=client)
    if item.status == SupervisionItem.Status.OFFEN:
        item.status = SupervisionItem.Status.BESPROCHEN
    else:
        item.status = SupervisionItem.Status.OFFEN
        item.resolution_notes = ""
        item.resolved_date = None
    item.save(update_fields=["status", "resolution_notes", "resolved_date"])

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": item.status, "label": item.get_status_display()})
    return redirect(
        safe_next(
            request,
            fallback=reverse("client_detail", kwargs={"pk": pk}) + "#ptab-protokoll",
        )
    )


@require_POST
def supervision_item_resolve(request, pk, item_pk):
    """Mark a SupervisionItem discussed, optionally recording resolution notes."""
    client = get_scoped_client(request, pk)
    item = get_object_or_404(SupervisionItem, pk=item_pk, client=client)

    resolved_date_str = request.POST.get("resolved_date", "").strip()
    try:
        resolved_date = date.fromisoformat(resolved_date_str) if resolved_date_str else date.today()
    except ValueError:
        resolved_date = date.today()

    item.status = SupervisionItem.Status.BESPROCHEN
    item.resolution_notes = request.POST.get("resolution_notes", "").strip()
    item.resolved_date = resolved_date
    item.save(update_fields=["status", "resolution_notes", "resolved_date"])
    messages.success(request, _("Supervision topic marked discussed."))
    return redirect(
        safe_next(
            request,
            fallback=reverse("client_detail", kwargs={"pk": pk}) + "#ptab-protokoll",
        )
    )


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
