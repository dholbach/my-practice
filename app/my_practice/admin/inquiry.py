"""Admin configuration for ClientInquiry and MarketingPeriod."""

from django.contrib import admin
from django.utils.translation import gettext_lazy

from ..models import ClientInquiry, MarketingPeriod


@admin.register(ClientInquiry)
class ClientInquiryAdmin(admin.ModelAdmin):
    list_display = ["full_name", "source", "status", "inquiry_date", "practice"]
    list_filter = ["status", "source", "practice"]
    search_fields = ["full_name", "email", "phone"]
    ordering = ["-inquiry_date"]
    raw_id_fields = ["converted_client"]
    date_hierarchy = "inquiry_date"


@admin.register(MarketingPeriod)
class MarketingPeriodAdmin(admin.ModelAdmin):
    list_display = ["description", "start_date", "end_date", "is_active_badge", "practice"]
    list_filter = ["practice"]
    ordering = ["-start_date"]

    @admin.display(description=gettext_lazy("Active"), boolean=True)
    def is_active_badge(self, obj):
        return obj.is_active()
