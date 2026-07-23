"""
Focus Queue views (P-050 phase 3).

Single merged queue of manual and materialized Task rows — the working
surface that answers "what should I do next," replacing /todos/ and the
dashboard's "Needs Action" pane (see docs/projects/todo/P-050_FOCUS_QUEUE.md).
"""

from datetime import timedelta
from typing import Any

from django.db.models import Case, IntegerField, Value, When
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import PracticeTodo
from .crud_mixins import PracticeScopedListView

_PRIORITY_RANK = Case(
    When(priority=PracticeTodo.Priority.URGENT, then=Value(0)),
    When(priority=PracticeTodo.Priority.HIGH, then=Value(1)),
    When(priority=PracticeTodo.Priority.MEDIUM, then=Value(2)),
    When(priority=PracticeTodo.Priority.LOW, then=Value(3)),
    default=Value(4),
    output_field=IntegerField(),
)

# Snooze presets offered on each row — deliberately just a few fixed options
# rather than a date picker, to keep triage fast (v1 scope, see P-050 doc).
SNOOZE_PRESET_DAYS = {"1": 1, "3": 3, "7": 7}


def _open_tasks_queryset(request: HttpRequest, task_type: str = ""):
    today = timezone.now().date()
    qs = (
        PracticeTodo.objects.for_current_practice(request)
        .filter(completed_at__isnull=True)
        .exclude(snoozed_until__gte=today)
    )
    if task_type:
        qs = qs.filter(task_type=task_type)
    return qs.annotate(priority_rank=_PRIORITY_RANK).order_by("priority_rank", "created_at")


def _build_focus_queue_context(request: HttpRequest) -> dict[str, Any]:
    """Build context for the focus queue partial (HTMX swap target)."""
    task_type = request.GET.get("type", "")
    today = timezone.now().date()
    snoozed_qs = PracticeTodo.objects.for_current_practice(request).filter(
        completed_at__isnull=True, snoozed_until__gte=today
    )
    if task_type:
        snoozed_qs = snoozed_qs.filter(task_type=task_type)
    return {
        "tasks": _open_tasks_queryset(request, task_type),
        "snoozed_count": snoozed_qs.count(),
        "current_type": task_type,
        "task_types": PracticeTodo.TASK_TYPE_CHOICES,
    }


class FocusQueueView(PracticeScopedListView):
    """
    Single queue of open (non-snoozed, non-done) Task rows across manual and
    materialized types — sorted by priority, then longest-outstanding first.
    Filterable by task_type via ?type=.
    """

    model = PracticeTodo
    template_name = "my_practice/focus_queue.html"
    context_object_name = "tasks"
    paginate_by = 50

    def get_queryset(self):
        return _open_tasks_queryset(self.request, self.request.GET.get("type", ""))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        task_type = self.request.GET.get("type", "")
        today = timezone.now().date()
        snoozed_qs = PracticeTodo.objects.for_current_practice(self.request).filter(
            completed_at__isnull=True, snoozed_until__gte=today
        )
        if task_type:
            snoozed_qs = snoozed_qs.filter(task_type=task_type)
        context["snoozed_count"] = snoozed_qs.count()
        context["current_type"] = task_type
        context["task_types"] = PracticeTodo.TASK_TYPE_CHOICES
        return context


@require_POST
def focus_queue_toggle_complete(request: HttpRequest, pk: int) -> HttpResponse:
    """Mark a task completed. HTMX partial swap, falls back to a redirect."""
    task = get_object_or_404(PracticeTodo.objects.for_current_practice(request), pk=pk)
    task.mark_completed()

    if request.headers.get("HX-Request"):
        return render(
            request, "includes/focus_queue_content.html", _build_focus_queue_context(request)
        )
    return redirect(reverse("focus_queue"))


@require_POST
def focus_queue_snooze(request: HttpRequest, pk: int) -> HttpResponse:
    """Snooze a task by a preset number of days. HTMX partial swap."""
    task = get_object_or_404(PracticeTodo.objects.for_current_practice(request), pk=pk)
    days = SNOOZE_PRESET_DAYS.get(request.POST.get("days"), 1)
    task.snoozed_until = timezone.now().date() + timedelta(days=days)
    task.save(update_fields=["snoozed_until"])

    if request.headers.get("HX-Request"):
        return render(
            request, "includes/focus_queue_content.html", _build_focus_queue_context(request)
        )
    return redirect(reverse("focus_queue"))
