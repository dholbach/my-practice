"""Admin configuration for Client."""

from django.contrib import admin
from django.utils.html import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from ..models import Client, ClientDocument


class ClientDocumentInline(admin.TabularInline):
    model = ClientDocument
    extra = 0
    fields = ["document_type", "file", "description", "document_date"]
    readonly_fields = ["created_at"]


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Client admin with improved search (Django 5.1 field lookups)"""

    list_display = [
        "client_code",
        "full_name",
        "email",
        "language",
        "practice",
        "online_badge",
        "active_status",
        "hourly_rate_60",
        "hourly_rate_90",
        "tag_list",
    ]
    list_filter = [
        "active",
        "is_online_client",
        "language",
        "practice",
        "tags",
        "created_at",
    ]

    # Django 5.1 feature: Field lookups in search (istartswith for better matching)
    search_fields = [
        "client_code",
        "full_name__istartswith",  # Case-insensitive prefix search
        "email__icontains",
        "notes__icontains",
    ]

    readonly_fields = ["created_at", "updated_at"]
    filter_horizontal = ["tags"]
    inlines = [ClientDocumentInline]

    fieldsets = (
        (
            gettext_lazy("Basic Information"),
            {
                "fields": (
                    "client_code",
                    "full_name",
                    "date_of_birth",
                    "language",
                    "practice",
                )
            },
        ),
        (gettext_lazy("Contact"), {"fields": ("email", "phone", "address")}),
        (
            gettext_lazy("Email Settings"),
            {
                "fields": ("salutation",),
                "description": gettext_lazy(
                    "Custom email salutation (e.g., 'Dear John', 'Liebe Maria'). If empty, "
                    "defaults to 'Dear {name}' (EN) or 'Liebe:r {name}' (DE)"
                ),
            },
        ),
        (
            gettext_lazy("Rates"),
            {
                "fields": ("hourly_rate_60", "hourly_rate_90", "cancellation_fee"),
                "description": gettext_lazy("Standard hourly rates for this client"),
            },
        ),
        (
            gettext_lazy("Organization"),
            {
                "fields": ("tags",),
                "description": gettext_lazy("Tags for organizing and categorizing clients"),
            },
        ),
        (
            gettext_lazy("Additional"),
            {
                "fields": (
                    "notes",
                    "active",
                    "is_online_client",
                    "needs_gebueh_invoice",
                    "gebueh_no_diagnosis",
                )
            },
        ),
        (
            gettext_lazy("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description=gettext_lazy("Status"))
    def active_status(self, obj):
        if obj.active:
            return mark_safe(
                f'<span style="color: green; font-weight: bold;">✓ {_("Active")}</span>'
            )
        return mark_safe(f'<span style="color: red;">✗ {_("Inactive")}</span>')

    @admin.display(description=gettext_lazy("Format"), ordering="is_online_client")
    def online_badge(self, obj):
        if obj.is_online_client:
            return mark_safe(f'<span style="color: #667eea;">💻 {_("Online")}</span>')
        return mark_safe(f'<span style="color: #48bb78;">🏢 {_("On-site")}</span>')

    @admin.display(description=gettext_lazy("Tags"))
    def tag_list(self, obj):
        tags = obj.tags.all()
        if not tags:
            return "-"
        return ", ".join([tag.name for tag in tags])
