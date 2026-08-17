"""Admin configuration for ClientAlias."""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy

from ..models import ClientAlias


@admin.register(ClientAlias)
class ClientAliasAdmin(admin.ModelAdmin):
    """Admin interface for client payment name aliases."""

    list_display = ["alias_name", "client_link", "notes_display", "created_at"]
    list_filter = ["client", "created_at"]
    search_fields = ["alias_name", "client__client_code", "client__full_name", "notes"]
    date_hierarchy = "created_at"
    ordering = ["client", "alias_name"]
    readonly_fields = ["created_at"]

    fieldsets = (
        (
            gettext_lazy("Assignment"),
            {
                "fields": ("client", "alias_name"),
            },
        ),
        (
            gettext_lazy("Details"),
            {
                "fields": ("notes", "created_at"),
            },
        ),
    )

    @admin.display(description=gettext_lazy("Client"), ordering="client")
    def client_link(self, obj):
        """Display link to client."""
        return format_html(
            '<a href="/admin/my_practice/client/{}/change/">{}</a>',
            obj.client.pk,
            obj.client.client_code,
        )

    @admin.display(description=gettext_lazy("Notes"))
    def notes_display(self, obj):
        """Display truncated notes."""
        if not obj.notes:
            return "-"
        if len(obj.notes) > 50:
            return f"{obj.notes[:47]}..."
        return obj.notes
