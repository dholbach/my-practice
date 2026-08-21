"""Admin configuration for CompanyWithdrawal and CompanyExpense."""

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy, ngettext

from ..models import CompanyExpense, CompanyWithdrawal


@admin.register(CompanyWithdrawal)
class CompanyWithdrawalAdmin(admin.ModelAdmin):
    list_display = ("date", "amount", "category", "description_short")
    list_filter = ("category", "date")
    search_fields = ("description",)
    date_hierarchy = "date"
    ordering = ("-date",)

    fieldsets = (
        (gettext_lazy("Withdrawal"), {"fields": ("date", "amount", "category", "practice")}),
        (gettext_lazy("Details"), {"fields": ("description",)}),
    )

    actions = ["mark_as_tax_year"]

    @admin.action(description=gettext_lazy("Flag for current tax year"))
    def mark_as_tax_year(self, request, queryset):
        current_year = timezone.localdate().year
        updated = queryset.filter(date__year=current_year).count()
        self.message_user(
            request,
            ngettext(
                "%(count)s withdrawal found for tax year %(year)s.",
                "%(count)s withdrawals found for tax year %(year)s.",
                updated,
            )
            % {"count": updated, "year": current_year},
            messages.SUCCESS,
        )

    @admin.display(description=gettext_lazy("Notes"))
    def description_short(self, obj):
        """Truncate description for list view"""
        if obj.description:
            return obj.description[:50] + "..." if len(obj.description) > 50 else obj.description
        return "-"


@admin.register(CompanyExpense)
class CompanyExpenseAdmin(admin.ModelAdmin):
    list_display = [
        "date",
        "description_short",
        "category_display",
        "amount_display",
        "has_invoice",
        "is_tax_deductible",
    ]
    list_filter = ["category", "date", "is_tax_deductible", "has_invoice"]
    search_fields = ["description"]
    date_hierarchy = "date"
    ordering = ["-date"]

    actions = ["mark_tax_deductible", "mark_not_tax_deductible", "mark_has_invoice"]

    @admin.action(description=gettext_lazy("Mark as tax deductible"))
    def mark_tax_deductible(self, request, queryset):
        updated = queryset.update(is_tax_deductible=True)
        self.message_user(
            request,
            ngettext(
                "%(count)s expense marked as tax deductible.",
                "%(count)s expenses marked as tax deductible.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=gettext_lazy("Not tax deductible"))
    def mark_not_tax_deductible(self, request, queryset):
        updated = queryset.update(is_tax_deductible=False)
        self.message_user(
            request,
            ngettext(
                "%(count)s expense marked as not deductible.",
                "%(count)s expenses marked as not deductible.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=gettext_lazy("Mark as invoice available"))
    def mark_has_invoice(self, request, queryset):
        updated = queryset.update(has_invoice=True)
        self.message_user(
            request,
            ngettext(
                "%(count)s expense marked with invoice.",
                "%(count)s expenses marked with invoice.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    fieldsets = (
        (
            gettext_lazy("General"),
            {"fields": ("date", "description", "category", "amount")},
        ),
        (
            gettext_lazy("Details"),
            {"fields": ("has_invoice", "is_tax_deductible")},
        ),
    )

    @admin.display(description=gettext_lazy("Description"))
    def description_short(self, obj):
        """Truncate description for list view"""
        if obj.description:
            return obj.description[:60] + "..." if len(obj.description) > 60 else obj.description
        return "-"

    @admin.display(description=gettext_lazy("Category"))
    def category_display(self, obj):
        """Display category with label"""
        return obj.get_category_display()

    @admin.display(description=gettext_lazy("Amount"))
    def amount_display(self, obj):
        """Format amount with Euro symbol"""
        amount_str = f"{float(obj.amount):.2f}"
        return format_html("<strong>{} €</strong>", amount_str)
