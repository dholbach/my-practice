"""Views for the case review (P-006): go through the sessions since the last one, then finish."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from ..utils.case_review import build_review, finish_review
from ..utils.view_helpers import get_scoped_client


@require_GET
def case_review(request, pk):
    """The review page: sessions since the last review beside the case sheet's key rows."""
    client = get_scoped_client(request, pk)
    return render(
        request,
        "my_practice/case_review.html",
        {"client": client, "review_url": request.path, **build_review(client)},
    )


@require_POST
def case_review_finish(request, pk):
    """Record the review; the next one starts counting from today."""
    client = get_scoped_client(request, pk)
    finish_review(client)
    messages.success(request, _("Review saved."))
    return redirect(reverse("client_detail", kwargs={"pk": pk}) + "#case-sheet")
