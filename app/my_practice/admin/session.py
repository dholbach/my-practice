"""Admin configuration for Session."""

from django.contrib import admin
from django.db.models import Exists, OuterRef
from django.utils.translation import gettext_lazy

from ..models import InvoiceItem, Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    """Central session hub — links billing and clinical records."""

    list_display = [
        "__str__",
        "client",
        "session_date",
        "duration",
        "cancelled",
        "group_size",
        "has_log",
        "has_invoice_item",
    ]
    list_filter = ["cancelled", "session_date", "client__practice"]
    search_fields = ["client__client_code", "client__full_name", "calendar_event_id"]
    date_hierarchy = "session_date"
    ordering = ["-session_date"]
    autocomplete_fields = ["client"]
    readonly_fields = ["calendar_event_id"]

    def get_queryset(self, request):
        """Fetch what the list columns read, so a page costs the same for 10 rows or 100."""
        return (
            super()
            .get_queryset(request)
            .select_related("client", "log")
            .annotate(_has_invoice_item=Exists(InvoiceItem.objects.filter(session=OuterRef("pk"))))
        )

    @admin.display(description=gettext_lazy("Log"), boolean=True)
    def has_log(self, obj):
        return hasattr(obj, "log")

    @admin.display(description=gettext_lazy("Invoice"), boolean=True)
    def has_invoice_item(self, obj):
        return obj._has_invoice_item
