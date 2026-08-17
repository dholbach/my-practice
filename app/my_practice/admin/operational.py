"""Admin configuration for OperationalChecklistCompletion and ChecklistItemPause."""

from django.contrib import admin
from django.utils.translation import gettext_lazy

from ..models import ChecklistItemPause, OperationalChecklistCompletion


@admin.register(OperationalChecklistCompletion)
class OperationalChecklistCompletionAdmin(admin.ModelAdmin):
    list_display = ["checklist_type", "year_month", "completed_at", "notes"]
    list_filter = ["checklist_type"]
    ordering = ["-year_month", "checklist_type"]
    readonly_fields = ["completed_at"]


@admin.register(ChecklistItemPause)
class ChecklistItemPauseAdmin(admin.ModelAdmin):
    list_display = [
        "checklist_type",
        "item_id",
        "reason",
        "paused_until",
        "is_active",
        "created_at",
    ]
    list_filter = ["checklist_type"]
    ordering = ["checklist_type", "item_id"]
    readonly_fields = ["created_at"]

    @admin.display(boolean=True, description=gettext_lazy("Active"))
    def is_active(self, obj: ChecklistItemPause) -> bool:
        return obj.is_active
