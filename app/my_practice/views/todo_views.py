"""
TODO/Task management views for practice planning.
"""

from datetime import date
from typing import Any
from urllib.parse import urlparse

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from ..models import PracticeTodo
from ..utils import AgendaWidgetBuilder, WeeklyFocusWidgetBuilder
from .crud_mixins import (
    PracticeScopedCreateView,
    PracticeScopedDeleteView,
    PracticeScopedListView,
    PracticeScopedUpdateView,
)


class TodoListView(PracticeScopedListView):
    """List all TODOs with filtering options"""

    model = PracticeTodo
    template_name = "my_practice/todo_list.html"
    context_object_name = "todos"
    paginate_by = 50

    def get_queryset(self):
        """Filter TODOs by status"""
        # P-050: materialized/derived tasks (missing session log, unpaid/
        # unsent invoices, operational checklists) aren't shown here yet —
        # they surface once the dedicated Focus Queue page (phase 3) exists.
        queryset = super().get_queryset().filter(task_type=PracticeTodo.TaskType.MANUAL)

        status = self.request.GET.get("status", "active")
        if status == "completed":
            queryset = queryset.filter(completed_at__isnull=False)
        elif status == "active":
            queryset = queryset.filter(completed_at__isnull=True)
        # else: all

        # Filter by category
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category=category)

        # Filter by priority
        priority = self.request.GET.get("priority")
        if priority:
            queryset = queryset.filter(priority=priority)

        # Ordering: overdue first, then by priority, then by due_date
        return queryset.order_by("-completed_at", "due_date", "-priority")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        # Get status filter
        context["current_status"] = self.request.GET.get("status", "active")
        context["current_category"] = self.request.GET.get("category", "")
        context["current_priority"] = self.request.GET.get("priority", "")

        # Calculate stats
        all_todos = PracticeTodo.objects.for_current_practice(self.request).filter(
            task_type=PracticeTodo.TaskType.MANUAL
        )
        context["stats"] = {
            "total": all_todos.count(),
            "active": all_todos.filter(completed_at__isnull=True).count(),
            "completed": all_todos.filter(completed_at__isnull=False).count(),
            "overdue": all_todos.filter(
                completed_at__isnull=True, due_date__lt=date.today()
            ).count(),
        }

        # Categories and priorities for filters
        context["categories"] = PracticeTodo.CATEGORY_CHOICES
        context["priorities"] = PracticeTodo.PRIORITY_CHOICES

        return context


class TodoCreateView(PracticeScopedCreateView):
    """Create new TODO"""

    model = PracticeTodo
    template_name = "my_practice/todo_form.html"
    fields = ["title", "description", "category", "priority", "due_date"]
    success_url = reverse_lazy("todo_list")
    success_message = gettext_lazy("'{obj.title}' created successfully.")

    def form_valid(self, form):
        """Ensure practice is set before saving"""
        form.instance.practice = self.request.current_practice
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
    success_url = reverse_lazy("todo_list")
    success_message = gettext_lazy("'{obj.title}' updated successfully.")


class TodoDeleteView(PracticeScopedDeleteView):
    """Delete TODO with confirmation"""

    model = PracticeTodo
    template_name = "my_practice/todo_confirm_delete.html"
    success_url = reverse_lazy("todo_list")
    context_object_name = "todo"
    success_message = gettext_lazy("'{obj.title}' deleted successfully.")


def _build_todo_context(request: HttpRequest) -> dict[str, Any]:
    """
    Build context for the todo list partial.
    Used by TodoListView and todo_toggle_complete (HTMX response).
    """
    all_todos = PracticeTodo.objects.for_current_practice(request).filter(
        task_type=PracticeTodo.TaskType.MANUAL
    )
    status = request.GET.get("status", "active")
    category = request.GET.get("category", "")
    priority = request.GET.get("priority", "")

    todos = all_todos
    if status == "completed":
        todos = todos.filter(completed_at__isnull=False)
    elif status == "active":
        todos = todos.filter(completed_at__isnull=True)
    if category:
        todos = todos.filter(category=category)
    if priority:
        todos = todos.filter(priority=priority)
    todos = todos.order_by("-completed_at", "due_date", "-priority")

    return {
        "todos": todos,
        "stats": {
            "total": all_todos.count(),
            "active": all_todos.filter(completed_at__isnull=True).count(),
            "completed": all_todos.filter(completed_at__isnull=False).count(),
            "overdue": all_todos.filter(
                completed_at__isnull=True, due_date__lt=date.today()
            ).count(),
        },
        "current_status": status,
        "current_category": category,
        "current_priority": priority,
        "categories": PracticeTodo.CATEGORY_CHOICES,
        "priorities": PracticeTodo.PRIORITY_CHOICES,
        "is_paginated": False,
    }


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
        if request.GET.get("ctx") == "agenda":
            builder = AgendaWidgetBuilder(request.current_practice, target_date=date.today())
            ctx = builder.build_context()
            return render(
                request,
                "includes/agenda_widget_content.html",
                {
                    "agenda_items": ctx["agenda_items"],
                    "target_date": ctx["target_date"],
                    "is_today": ctx["is_today"],
                },
            )
        elif request.GET.get("ctx") == "weekly_focus":
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

    POST only. Returns HTMX partial (todo_content.html) on HTMX requests,
    otherwise redirects back to referrer.
    """
    todo = get_object_or_404(PracticeTodo.objects.for_current_practice(request), pk=pk)

    todo.is_focus = not todo.is_focus
    todo.save(update_fields=["is_focus"])

    if request.headers.get("HX-Request"):
        if request.GET.get("ctx") == "weekly_focus":
            builder = WeeklyFocusWidgetBuilder(request.current_practice)
            return render(
                request, "includes/weekly_focus_widget_content.html", builder.build_context()
            )
        ctx = _build_todo_context(request)
        return render(request, "includes/todo_content.html", ctx)

    referrer_path = urlparse(request.META.get("HTTP_REFERER", "")).path
    return redirect(referrer_path or reverse("todo_list"))
