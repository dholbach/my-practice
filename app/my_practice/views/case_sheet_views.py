"""Views for the case sheet (P-006): add a line, reword one, mark one as no longer applying."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import ClinicalFact
from ..models.case_sheet import ROWS_BY_KIND
from ..utils.case_sheet import add_line, change_line, resolve_line, valid_cell
from ..utils.view_helpers import get_scoped_client, safe_next


def _back(request, client_pk, kind=""):
    """Back to where the request came from, else to the row on the client page."""
    anchor = f"#case-row-{kind}" if kind else "#case-sheet"
    return redirect(
        safe_next(request, fallback=reverse("client_detail", kwargs={"pk": client_pk}) + anchor)
    )


@require_POST
def case_fact_add(request, pk):
    """Add a line to a cell of the case sheet (in a single-line cell it replaces the current one).

    The cell comes as ``kind`` and ``sub``, or as one ``target`` ("kind|sub", the digest card's
    picker). ``source_session`` names the session the line came from, when it has to belong
    to this client; anything else is ignored.
    """
    client = get_scoped_client(request, pk)
    if "target" in request.POST:
        kind, _bar, sub = request.POST["target"].partition("|")
    else:
        kind, sub = request.POST.get("kind", ""), request.POST.get("sub", "")
    if not valid_cell(kind, sub):
        messages.error(request, _("Unknown case sheet row."))
        return _back(request, pk)
    raw_session = request.POST.get("source_session", "")
    source_session = (
        client.sessions.filter(pk=int(raw_session)).first() if raw_session.isdigit() else None
    )
    if (
        add_line(client, kind, sub, request.POST.get("content", ""), source_session=source_session)
        is None
    ):
        messages.error(request, _("The line must not be empty."))
    elif source_session is not None:
        messages.success(request, _("Added to “%(row)s”.") % {"row": ROWS_BY_KIND[kind].label})
    return _back(request, pk, kind)


@require_POST
def case_fact_update(request, pk, fact_pk):
    """Reword a line: the new wording becomes a new line, the old one stays as an earlier version."""
    client = get_scoped_client(request, pk)
    fact = get_object_or_404(ClinicalFact, pk=fact_pk, client=client)
    content = request.POST.get("content", "")
    if not content.strip():
        messages.error(request, _("The line must not be empty."))
    else:
        change_line(fact, content)
    return _back(request, pk, fact.kind)


@require_POST
def case_fact_resolve(request, pk, fact_pk):
    """Mark a line as no longer applying; it stays in the row's earlier versions."""
    client = get_scoped_client(request, pk)
    fact = get_object_or_404(ClinicalFact, pk=fact_pk, client=client)
    resolve_line(fact)
    return _back(request, pk, fact.kind)
