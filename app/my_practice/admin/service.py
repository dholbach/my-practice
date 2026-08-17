"""Admin configuration for ServiceType."""

from django.contrib import admin
from django.utils.html import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from ..models import ServiceType


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "practice_scope", "default_duration"]
    list_filter = ["practice"]
    search_fields = ["code", "name"]

    fieldsets = (
        (
            gettext_lazy("Service Type"),
            {"fields": ("code", "name", "name_de", "name_en", "practice")},
        ),
        (gettext_lazy("Settings"), {"fields": ("default_duration",)}),
    )

    @admin.display(description=gettext_lazy("Scope"))
    def practice_scope(self, obj):
        if obj.practice:
            return obj.practice.name
        return mark_safe(
            f'<span style="color: #667eea; font-weight: bold;">🌍 {_("GLOBAL")}</span>'
        )
