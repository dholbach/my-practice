"""Admin configuration for ClientTag."""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy, ngettext

from ..models import ClientTag


@admin.register(ClientTag)
class ClientTagAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "category_badge",
        "color_badge",
        "client_count",
        "is_system",
        "created_at",
    ]
    list_filter = ["category", "color", "is_system", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["slug", "created_at", "updated_at"]
    prepopulated_fields = {}  # Slug is auto-generated in save()

    fieldsets = (
        (
            gettext_lazy("Tag Information"),
            {"fields": ("name", "slug", "category", "color", "description")},
        ),
        (
            gettext_lazy("Settings"),
            {"fields": ("is_system",)},
        ),
        (
            gettext_lazy("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description=gettext_lazy("Tag"))
    def color_badge(self, obj):
        """Display tag with its color"""
        color_map = {
            "red": "#f56565",
            "orange": "#ed8936",
            "yellow": "#ecc94b",
            "green": "#48bb78",
            "blue": "#4299e1",
            "purple": "#9f7aea",
            "pink": "#ed64a6",
            "gray": "#718096",
        }
        bg_color = color_map.get(obj.color, "#718096")
        text_color = "white" if obj.color != "yellow" else "#2d3748"

        return format_html(
            '<span style="background: {}; color: {}; padding: 4px 10px; '
            'border-radius: 12px; font-size: 0.85em; font-weight: 600;">{}</span>',
            bg_color,
            text_color,
            obj.name,
        )

    @admin.display(description=gettext_lazy("Category"))
    def category_badge(self, obj):
        """Display category as a colored badge"""
        badge_styles = {
            "attention": "background: #fed7d7; color: #742a2a; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;",
            "general": "background: #bee3f8; color: #2c5282; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;",
            "exit": "background: #e9d8fd; color: #44337a; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;",
        }
        style = badge_styles.get(obj.category, badge_styles["general"])
        return format_html(
            '<span style="{}">{}</span>',
            style,
            obj.get_category_display(),
        )

    @admin.display(description=gettext_lazy("Used By"))
    def client_count(self, obj):
        """Display number of clients with this tag"""
        count = obj.clients.count()
        return format_html(
            '<span style="font-weight: 600; color: #667eea;">{}</span>',
            ngettext("%(count)s client", "%(count)s clients", count) % {"count": count},
        )

    def get_readonly_fields(self, request, obj=None):
        """Make is_system readonly for existing system tags"""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_system:
            readonly.append("is_system")
            readonly.append("name")
        return readonly
