"""Admin configuration for TimeOff."""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from ..models import TimeOff


@admin.register(TimeOff)
class TimeOffAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "type",
        "start_date",
        "end_date",
        "duration_days",
        "status_badge",
    )
    list_filter = ("type", "start_date", "end_date")
    search_fields = ("title", "notes")
    date_hierarchy = "start_date"
    ordering = ("-start_date",)

    fieldsets = (
        (
            None,
            {
                "fields": ("title", "type", "start_date", "end_date"),
            },
        ),
        (
            gettext_lazy("Additional Information"),
            {
                "fields": ("notes",),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description=gettext_lazy("Status"))
    def status_badge(self, obj):
        """Display colored status badge"""
        if obj.is_current:
            color = "#48bb78"  # green
            status = f"🏖️ {_('Currently Off')}"
        elif obj.is_upcoming:
            color = "#667eea"  # blue
            status = f"📅 {_('Upcoming')}"
        else:
            color = "#a0aec0"  # gray
            status = f"✅ {_('Past')}"

        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 0.85em;">{}</span>',
            color,
            status,
        )
