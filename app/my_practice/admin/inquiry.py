"""Admin configuration for ClientInquiry and MarketingPeriod."""

from django.contrib import admin
from django.utils.translation import gettext_lazy

from ..models import INQUIRY_PERSONAL_FIELDS, ClientInquiry, MarketingPeriod


@admin.register(ClientInquiry)
class ClientInquiryAdmin(admin.ModelAdmin):
    list_display = ["full_name", "source", "status", "inquiry_date", "practice"]
    list_filter = ["status", "source", "practice"]
    search_fields = ["full_name", "email", "phone"]
    ordering = ["-inquiry_date"]
    raw_id_fields = ["converted_client"]
    date_hierarchy = "inquiry_date"

    def get_readonly_fields(self, request, obj=None):
        """Keep an anonymised inquiry's personal fields empty."""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.anonymised_at:
            readonly += [*INQUIRY_PERSONAL_FIELDS, "anonymised_at"]
        return readonly


@admin.register(MarketingPeriod)
class MarketingPeriodAdmin(admin.ModelAdmin):
    list_display = ["description", "start_date", "end_date", "is_active_badge", "practice"]
    list_filter = ["practice"]
    ordering = ["-start_date"]

    @admin.display(description=gettext_lazy("Active"), boolean=True)
    def is_active_badge(self, obj):
        return obj.is_active()
