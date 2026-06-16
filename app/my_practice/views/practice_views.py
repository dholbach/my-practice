"""
Views for multi-practice management.
"""

import logging
from typing import Any, cast
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from ..forms import PracticeEditForm
from ..models import Practice, UserPractice
from ..utils import get_user_practices, is_practice_owner, switch_practice
from ..utils.file_processing import compress_image_inplace

logger = logging.getLogger(__name__)


def practice_switch(request, slug):
    """
    Switch current practice by slug.
    """
    if switch_practice(request, slug):
        practice = Practice.objects.get(slug=slug)
        messages.success(request, f"Zur Praxis '{practice.name}' gewechselt.")
    else:
        messages.error(request, "Praxis nicht gefunden oder kein Zugriff.")

    # Smart redirect: If on a practice-specific URL, redirect to the same page for new practice
    referer = request.META.get("HTTP_REFERER", "")
    if "/practice/" in referer and "/edit/" in referer:
        # User was on a practice edit page - redirect to new practice's edit page
        return redirect("practice_edit", slug=slug)

    # Extract path only to prevent open redirect via HTTP_REFERER
    referer_path = urlparse(referer).path
    return redirect(referer_path or "dashboard")


def practice_select(request):
    """
    Practice selection page for users without a current practice.
    """
    practices = get_user_practices(request.user)

    if not practices:
        messages.error(
            request,
            "Sie haben keinen Zugriff auf eine Praxis. Bitte kontaktieren Sie den Administrator.",
        )
        return redirect("dashboard")

    # If only one practice, auto-select it
    if len(practices) == 1:
        switch_practice(request, practices[0].slug)
        return redirect("dashboard")

    return render(
        request,
        "my_practice/practice_select.html",
        {
            "practices": practices,
        },
    )


class PracticeManagementView(ListView):
    """
    List all practices the user has access to.
    Allows owners to create, edit, and manage practices.
    """

    model = Practice
    template_name = "my_practice/practice_management.html"
    context_object_name = "practices"

    def get_queryset(self):
        """Return only practices the user has access to."""
        return get_user_practices(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add ownership info for each practice
        practices_with_ownership = [
            {
                "practice": practice,
                "is_owner": is_practice_owner(self.request.user, practice),
            }
            for practice in context["practices"]
        ]
        context["practices_with_ownership"] = practices_with_ownership

        return context


class PracticeCreateView(CreateView):
    """
    Create a new practice.
    User is automatically assigned as owner.
    """

    model = Practice
    template_name = "my_practice/practice_form.html"
    fields = [
        "name",
        "short_title",
        "title",
        "subtitle_de",
        "subtitle_en",
        "street",
        "postal_code",
        "city",
        "country",
        "email",
        "email_from_name",
        "website",
        "phone",
        "bank_name",
        "iban",
        "bic",
        "tax_id",
    ]
    success_url = reverse_lazy("practice_management")

    def form_valid(self, form: Any) -> HttpResponse:
        response = super().form_valid(form)

        # Create UserPractice relationship with ownership
        assert self.object is not None
        UserPractice.objects.create(
            user=cast(User, self.request.user), practice=self.object, is_owner=True
        )

        # Switch to new practice
        switch_practice(self.request, self.object.slug)

        messages.success(self.request, f"Praxis '{self.object.name}' erfolgreich erstellt.")
        return response


class PracticeUpdateView(UpdateView):
    """
    Update practice settings.
    Only owners can edit.
    """

    model = Practice
    template_name = "my_practice/practice_form.html"
    form_class = PracticeEditForm
    success_url = reverse_lazy("practice_management")
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def dispatch(self, request, *args, **kwargs):
        """Check if user is owner before allowing edit."""
        practice = self.get_object()
        if not is_practice_owner(request.user, practice):
            messages.error(request, "Sie haben keine Berechtigung, diese Praxis zu bearbeiten.")
            return redirect("practice_management")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        for field_name in ("logo", "signature"):
            if field_name in self.request.FILES:
                field = getattr(self.object, field_name)
                if field and field.name:
                    try:
                        compress_image_inplace(field.path)
                    except Exception:
                        logger.exception("Failed to compress practice %s", field_name)
        messages.success(self.request, f"Praxis '{self.object.name}' erfolgreich aktualisiert.")
        return response


class PracticeDeleteView(DeleteView):
    """
    Delete practice (sets is_active=False).
    Only owners can delete.
    """

    model = Practice
    template_name = "my_practice/practice_confirm_delete.html"
    success_url = reverse_lazy("practice_management")
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def dispatch(self, request, *args, **kwargs):
        """Check if user is owner before allowing delete."""
        practice = self.get_object()
        if not is_practice_owner(request.user, practice):
            messages.error(request, "Sie haben keine Berechtigung, diese Praxis zu löschen.")
            return redirect("practice_management")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: Any) -> HttpResponse:
        """Soft delete: set is_active=False instead of deleting."""
        practice = self.object
        practice.is_active = False
        practice.save()

        messages.success(self.request, f"Praxis '{practice.name}' deaktiviert.")

        # If this was current practice, clear session
        if self.request.session.get("current_practice_slug") == practice.slug:
            del self.request.session["current_practice_slug"]

        return redirect(self.success_url)
