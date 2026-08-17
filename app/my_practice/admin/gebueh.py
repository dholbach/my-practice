"""Admin configuration for GebuhZiffer and Leistungserfassung."""

from django.contrib import admin

from ..models import GebuhZiffer, Leistungserfassung


@admin.register(GebuhZiffer)
class GebuhZifferAdmin(admin.ModelAdmin):
    list_display = [
        "nummer",
        "bezeichnung",
        "satz_max",
        "satz_min",
        "max_haeufigkeit",
        "bezugszeitraum_tage",
        "sort_order",
    ]
    list_editable = ["sort_order"]
    ordering = ["sort_order", "nummer"]
    search_fields = ["nummer", "bezeichnung"]


@admin.register(Leistungserfassung)
class LeistungserfassungAdmin(admin.ModelAdmin):
    list_display = ["session", "ziffer", "betrag", "vereinbarter_betrag", "created_at"]
    list_select_related = ["session__client", "ziffer"]
    search_fields = ["session__client__client_code", "ziffer__nummer"]
    date_hierarchy = "created_at"
    readonly_fields = ["betrag", "vereinbarter_betrag"]
