"""Admin configuration for ExpenseCategoryRule."""

from django.contrib import admin
from django.utils.translation import gettext_lazy

from ..models import ExpenseCategoryRule


@admin.register(ExpenseCategoryRule)
class ExpenseCategoryRuleAdmin(admin.ModelAdmin):
    """Admin interface for learned counterparty -> expense category rules."""

    list_display = ["match_key", "category_display", "practice", "updated_at"]
    list_filter = ["category", "practice"]
    search_fields = ["match_key"]
    ordering = ["match_key"]
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(description=gettext_lazy("Category"), ordering="category")
    def category_display(self, obj):
        """Display category with label"""
        return obj.get_category_display()
