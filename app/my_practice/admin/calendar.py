"""Admin configuration for PendingCalendarEvent."""

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy, ngettext

from ..models import PendingCalendarEvent


@admin.register(PendingCalendarEvent)
class PendingCalendarEventAdmin(admin.ModelAdmin):
    """Admin for pending calendar events queue (P-013)."""

    list_display = [
        "event_date",
        "client_code",
        "summary",
        "duration_minutes",
        "status",
        "fetched_at",
    ]
    list_filter = ["status", "practice", "event_date"]
    search_fields = ["summary", "matched_client__client_code", "google_event_id"]
    ordering = ["-event_date"]
    readonly_fields = ["google_event_id", "fetched_at"]
    date_hierarchy = "event_date"
    actions = ["mark_pending", "mark_skipped"]

    @admin.display(description=gettext_lazy("Client"))
    def client_code(self, obj: PendingCalendarEvent) -> str:
        return obj.matched_client.client_code if obj.matched_client else "—"

    @admin.action(description=gettext_lazy("Mark as pending"))
    def mark_pending(self, request, queryset):
        updated = queryset.update(status=PendingCalendarEvent.Status.PENDING)
        self.message_user(
            request,
            ngettext(
                "%(count)s event marked as pending.", "%(count)s events marked as pending.", updated
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=gettext_lazy("Mark as skipped"))
    def mark_skipped(self, request, queryset):
        updated = queryset.update(status=PendingCalendarEvent.Status.SKIPPED)
        self.message_user(
            request,
            ngettext(
                "%(count)s event marked as skipped.", "%(count)s events marked as skipped.", updated
            )
            % {"count": updated},
            messages.SUCCESS,
        )
