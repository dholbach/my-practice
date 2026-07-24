"""
TODO/Task management views for practice planning.

The standalone /todos/ list page was retired in favour of the Focus Queue
page (P-050 phase 4), which shows manual and materialized tasks together.
These CRUD views remain — Focus Queue reuses them for creating/editing a
manual task — as do the two toggle endpoints, still used inline by the
dashboard's WeeklyFocus widget.
"""

from urllib.parse import urlparse

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from ..models import Client, PracticeTodo
from ..utils import WeeklyFocusWidgetBuilder
from .crud_mixins import (
    NextRedirectMixin,
    PracticeScopedCreateView,
    PracticeScopedDeleteView,
    PracticeScopedUpdateView,
)


class TodoCreateView(NextRedirectMixin, PracticeScopedCreateView):
    """
    Create new TODO.

    Accepts an optional ?client=<pk> so a task can be created already linked
    to a client (e.g. a "+ Task" button on the client detail page) — sets
    related_object so it renders with a link back to that client in the
    Focus Queue, the same as a materialized missing-session-log/invoice task.
    """

    model = PracticeTodo
    template_name = "my_practice/todo_form.html"
    fields = ["title", "description", "category", "priority", "due_date"]
    success_url = reverse_lazy("focus_queue")
    success_message = gettext_lazy("'{obj.title}' created successfully.")

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("client"):
            initial["category"] = PracticeTodo.Category.CLIENT
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client_pk = self.request.GET.get("client")
        if client_pk:
            context["for_client"] = get_object_or_404(
                Client.objects.for_current_practice(self.request), pk=client_pk
            )
        return context

    def form_valid(self, form):
        """Ensure practice is set before saving, and link the client if given"""
        form.instance.practice = self.request.current_practice
        client_pk = self.request.GET.get("client")
        if client_pk:
            client = get_object_or_404(
                Client.objects.for_current_practice(self.request), pk=client_pk
            )
            form.instance.related_object = client
        return super().form_valid(form)


class TodoUpdateView(PracticeScopedUpdateView):
    """Update existing TODO"""

    model = PracticeTodo
    template_name = "my_practice/todo_form.html"
    fields = [
        "title",
        "description",
        "category",
        "priority",
        "due_date",
        "completed_at",
    ]
    success_url = reverse_lazy("focus_queue")
    success_message = gettext_lazy("'{obj.title}' updated successfully.")


class TodoDeleteView(PracticeScopedDeleteView):
    """Delete TODO with confirmation"""

    model = PracticeTodo
    template_name = "my_practice/todo_confirm_delete.html"
    success_url = reverse_lazy("focus_queue")
    context_object_name = "todo"
    success_message = gettext_lazy("'{obj.title}' deleted successfully.")


def todo_toggle_complete(request: HttpRequest, pk: int) -> HttpResponse | JsonResponse:
    """
    Toggle TODO completion status.

    Supports both GET (for direct links) and POST (for AJAX).
    - GET: Toggles status and redirects back to referrer or dashboard
    - POST: Returns JSON response with new status
    """
    todo = get_object_or_404(PracticeTodo.objects.for_current_practice(request), pk=pk)

    # Toggle completion
    if todo.is_completed:
        todo.mark_incomplete()
        message = _("'%(title)s' marked as open.") % {"title": todo.title}
    else:
        todo.mark_completed()
        message = _("'%(title)s' marked as completed.") % {"title": todo.title}

    # Return HTMX partial
    if request.headers.get("HX-Request"):
        if request.GET.get("ctx") == "weekly_focus":
            builder = WeeklyFocusWidgetBuilder(request.current_practice)
            return render(
                request, "includes/weekly_focus_widget_content.html", builder.build_context()
            )
    # For GET requests (direct links): redirect with success message
    messages.success(request, message)

    # Redirect to referrer if available, otherwise to dashboard
    referrer_path = urlparse(request.META.get("HTTP_REFERER", "")).path
    return redirect(referrer_path or reverse("dashboard"))


def todo_toggle_focus(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Toggle is_focus flag on a PracticeTodo.

    POST only, used by the dashboard's WeeklyFocus widget. Returns an HTMX
    partial on HTMX requests, otherwise redirects back to referrer.
    """
    todo = get_object_or_404(PracticeTodo.objects.for_current_practice(request), pk=pk)

    todo.is_focus = not todo.is_focus
    todo.save(update_fields=["is_focus"])

    if request.headers.get("HX-Request"):
        builder = WeeklyFocusWidgetBuilder(request.current_practice)
        return render(request, "includes/weekly_focus_widget_content.html", builder.build_context())

    referrer_path = urlparse(request.META.get("HTTP_REFERER", "")).path
    return redirect(referrer_path or reverse("focus_queue"))
