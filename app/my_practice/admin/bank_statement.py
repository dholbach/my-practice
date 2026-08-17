"""Admin configuration for BankTransaction."""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy

from ..models import BankTransaction


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    """Admin interface for bank transactions and invoice matching."""

    list_display = [
        "transaction_date",
        "payer_name_display",
        "amount_display",
        "confidence_badge",
        "matched_invoice_link",
        "processed",
    ]
    list_filter = [
        "match_confidence",
        "processed",
        "practice",
        "transaction_date",
    ]
    search_fields = [
        "payer_name",
        "reference",
        "extracted_invoice_number",
        "matched_invoice__invoice_number",
    ]
    date_hierarchy = "transaction_date"
    ordering = ["-transaction_date", "-imported_at"]
    readonly_fields = [
        "imported_at",
        "is_income",
        "is_expense",
        "is_matched",
    ]

    fieldsets = (
        (
            gettext_lazy("Transaction Data"),
            {
                "fields": (
                    "practice",
                    "transaction_date",
                    "value_date",
                    "amount",
                    "balance_after",
                ),
            },
        ),
        (
            gettext_lazy("Payment Partner"),
            {
                "fields": ("payer_name", "payer_iban", "reference"),
            },
        ),
        (
            gettext_lazy("Matching"),
            {
                "fields": (
                    "matched_invoice",
                    "match_confidence",
                    "extracted_invoice_number",
                    "notes",
                ),
            },
        ),
        (
            gettext_lazy("Status"),
            {
                "fields": (
                    "processed",
                    "imported_at",
                    "is_income",
                    "is_expense",
                    "is_matched",
                ),
            },
        ),
    )

    @admin.display(description=gettext_lazy("Payer"), ordering="payer_name")
    def payer_name_display(self, obj):
        """Display payer name with truncation."""
        if len(obj.payer_name) > 30:
            return f"{obj.payer_name[:27]}..."
        return obj.payer_name

    @admin.display(description=gettext_lazy("Amount"), ordering="amount")
    def amount_display(self, obj):
        """Display amount with color coding."""
        color = "#16a34a" if obj.is_income else "#dc2626"  # green : red
        amount_str = f"{obj.amount:+.2f}"
        return format_html(
            '<span style="color: {}; font-weight: 600;">{} €</span>',
            color,
            amount_str,
        )

    @admin.display(description=gettext_lazy("Match"), ordering="match_confidence")
    def confidence_badge(self, obj):
        """Display match confidence as a colored badge.

        Reuses BankTransaction.CONFIDENCE_CHOICES (get_match_confidence_display())
        instead of a separate hardcoded label map, so the badge text can't drift
        out of sync with the model's own translated choices.
        """
        badge_styles = {
            "exact": "background: #bbf7d0; color: #14532d;",
            "fuzzy": "background: #fef3c7; color: #713f12;",
            "manual": "background: #ddd6fe; color: #4c1d95;",
            "ignored": "background: #e5e7eb; color: #374151;",
            "unmatched": "background: #fecaca; color: #7f1d1d;",
        }
        style = badge_styles.get(obj.match_confidence, badge_styles["unmatched"])
        return format_html(
            '<span style="{}; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            style,
            obj.get_match_confidence_display(),
        )

    @admin.display(description=gettext_lazy("Invoice"), ordering="matched_invoice")
    def matched_invoice_link(self, obj):
        """Display link to matched invoice."""
        if obj.matched_invoice:
            return format_html(
                '<a href="/admin/my_practice/invoice/{}/change/">{}</a>',
                obj.matched_invoice.pk,
                obj.matched_invoice.invoice_number,
            )
        return "-"
