"""Admin configuration for PracticeTodo."""

from django.contrib import admin, messages
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext_lazy, ngettext

from ..models import PracticeTodo


@admin.register(PracticeTodo)
class PracticeTodoAdmin(admin.ModelAdmin):
    """Practice TODO admin for task management and weekly planning."""

    list_display = [
        "status_icon",
        "title_display",
        "category_badge",
        "priority_badge",
        "due_date",
        "created_at",
        "completed_at",
    ]
    list_filter = [
        "completed_at",
        "category",
        "priority",
        "task_type",
        "due_date",
        "practice",
        "created_at",
    ]
    search_fields = ["title", "description"]
    date_hierarchy = "created_at"
    ordering = ["-completed_at", "-priority", "due_date", "-created_at"]
    readonly_fields = ["task_type", "content_type", "object_id"]

    actions = ["mark_completed", "mark_incomplete", "set_high_priority"]

    fieldsets = (
        (
            gettext_lazy("Task Information"),
            {"fields": ("practice", "title", "description")},
        ),
        (
            gettext_lazy("Organization"),
            {"fields": ("category", "priority", "due_date")},
        ),
        (
            gettext_lazy("Status"),
            {"fields": ("completed_at", "snoozed_until")},
        ),
        (
            gettext_lazy("Focus Queue (P-050)"),
            {
                "fields": ("task_type", "content_type", "object_id"),
                "description": gettext_lazy(
                    "Set automatically for materialized tasks — not manually editable."
                ),
            },
        ),
    )

    @admin.display(description="", ordering="completed_at")
    def status_icon(self, obj):
        """Display checkmark for completed tasks."""
        if obj.is_completed:
            return mark_safe('<span style="font-size: 18px;">✅</span>')
        if obj.is_overdue:
            return mark_safe('<span style="font-size: 18px;">⚠️</span>')
        return mark_safe('<span style="font-size: 18px;">⏳</span>')

    @admin.display(description=gettext_lazy("Task"), ordering="title")
    def title_display(self, obj):
        """Display title with strikethrough if completed."""
        if obj.is_completed:
            return format_html(
                '<span style="text-decoration: line-through; color: #a0aec0;">{}</span>',
                obj.title,
            )
        return obj.title

    @admin.display(description=gettext_lazy("Category"), ordering="category")
    def category_badge(self, obj):
        """Display category as a colored badge."""
        badge_styles = {
            "admin": "background: #bee3f8; color: #2c5282;",
            "learning": "background: #c6f6d5; color: #22543d;",
            "financial": "background: #fbd38d; color: #744210;",
            "client": "background: #fbb6ce; color: #702459;",
            "practice": "background: #d6bcfa; color: #44337a;",
            "other": "background: #e2e8f0; color: #2d3748;",
        }
        base_style = badge_styles.get(obj.category, badge_styles["other"])
        return format_html(
            '<span style="{}; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            base_style,
            obj.get_category_display(),
        )

    @admin.display(description=gettext_lazy("Priority"), ordering="priority")
    def priority_badge(self, obj):
        """Display priority as a colored badge."""
        badge_styles = {
            "urgent": "background: #feb2b2; color: #742a2a; font-weight: 700;",
            "high": "background: #fed7aa; color: #7c2d12;",
            "medium": "background: #fef3c7; color: #78350f;",
            "low": "background: #e2e8f0; color: #4a5568;",
        }
        style = badge_styles.get(obj.priority, badge_styles["medium"])
        return format_html(
            '<span style="{}; padding: 3px 8px; border-radius: 4px; font-size: 11px; text-transform: uppercase;">{}</span>',
            style,
            obj.get_priority_display(),
        )

    @admin.action(description=gettext_lazy("Mark as completed"))
    def mark_completed(self, request, queryset):
        """Mark selected tasks as completed."""
        updated = 0
        for todo in queryset.filter(completed_at__isnull=True):
            todo.mark_completed()
            updated += 1
        self.message_user(
            request,
            ngettext(
                "%(count)s task marked as completed.",
                "%(count)s tasks marked as completed.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=gettext_lazy("Mark as incomplete"))
    def mark_incomplete(self, request, queryset):
        """Mark selected tasks as incomplete."""
        updated = 0
        for todo in queryset.filter(completed_at__isnull=False):
            todo.mark_incomplete()
            updated += 1
        self.message_user(
            request,
            ngettext(
                "%(count)s task marked as incomplete.",
                "%(count)s tasks marked as incomplete.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=gettext_lazy("Set high priority"))
    def set_high_priority(self, request, queryset):
        """Set selected tasks to high priority."""
        updated = queryset.update(priority="high")
        self.message_user(
            request,
            ngettext(
                "%(count)s task set to high priority.",
                "%(count)s tasks set to high priority.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )
