"""Admin configuration for Invoice and InvoiceItem."""

from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy, ngettext
from django.utils import timezone

from ..models import Invoice, InvoiceItem


class InvoiceItemAdminForm(forms.ModelForm):
    """Runs InvoiceItem's session/description checks as form-level checks —
    session is blank=True on the model (P-122), so without this the admin
    would only find out about a violation via a raw ValidationError raised
    inside save(), producing an unhandled 500 instead of a normal form
    error. Reuses InvoiceItem.validate_*() (models/invoice.py) rather than
    re-deriving the same rules here."""

    class Meta:
        model = InvoiceItem
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        has_session = bool(cleaned_data.get("session"))
        has_description = bool(cleaned_data.get("description"))
        InvoiceItem.validate_exclusive_session_or_description(has_session, has_description)
        # self.instance.invoice_id: set for edits and admin-inline creates
        # under an already-saved Invoice; still None while creating a new
        # Invoice + items together, same limitation as InvoiceItem.clean().
        if self.instance.invoice_id:
            InvoiceItem.validate_free_form_allowed(has_description, self.instance.invoice.practice)
        return cleaned_data


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    form = InvoiceItemAdminForm
    extra = 1
    fields = ["session", "description", "service_type", "rate", "quantity", "group_size", "total"]
    readonly_fields = ["total"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Invoice admin with improved search (Django 5.1)"""

    list_display = [
        "invoice_number",
        "client",
        "invoice_date",
        "status",
        "paid_date",
        "total_formatted",
    ]
    list_filter = ["status", "invoice_date", "paid_date", "created_at"]

    # Django 5.1: Enhanced search with field lookups
    search_fields = [
        "invoice_number",
        "client__full_name__icontains",
        "client__client_code__istartswith",
        "notes__icontains",
    ]

    date_hierarchy = "invoice_date"
    readonly_fields = ["created_at", "updated_at", "subtotal", "tax_amount", "total"]
    inlines = [InvoiceItemInline]

    # Django 5.1: Organize actions in groups
    actions = ["mark_as_sent", "mark_as_paid", "mark_as_cancelled"]

    @admin.action(description=gettext_lazy("Mark as sent"))
    def mark_as_sent(self, request, queryset):
        updated = queryset.update(status="sent")
        self.message_user(
            request,
            ngettext(
                "%(count)s invoice marked as sent.", "%(count)s invoices marked as sent.", updated
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=gettext_lazy("Mark as paid"))
    def mark_as_paid(self, request, queryset):
        updated = 0
        for invoice in queryset:
            invoice.status = "paid"
            if not invoice.paid_date:
                invoice.paid_date = timezone.localdate()
            invoice.save()
            updated += 1
        self.message_user(
            request,
            ngettext(
                "%(count)s invoice marked as paid.", "%(count)s invoices marked as paid.", updated
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=gettext_lazy("Mark as cancelled"))
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status="cancelled")
        self.message_user(
            request,
            ngettext(
                "%(count)s invoice marked as cancelled.",
                "%(count)s invoices marked as cancelled.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    fieldsets = (
        (
            gettext_lazy("Invoice Information"),
            {
                "fields": (
                    "invoice_number",
                    "client",
                    "invoice_date",
                    "status",
                    "paid_date",
                )
            },
        ),
        (
            gettext_lazy("Amounts"),
            {
                "fields": ("subtotal", "tax_rate", "tax_amount", "total"),
                "description": gettext_lazy(
                    "Amounts are calculated automatically from invoice items"
                ),
            },
        ),
        (gettext_lazy("Additional"), {"fields": ("notes",)}),
        (
            gettext_lazy("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description=gettext_lazy("Total"))
    def total_formatted(self, obj):
        return format_html("<strong>{} €</strong>", f"{obj.total:.2f}")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.calculate_total()
        obj.save()


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    form = InvoiceItemAdminForm
    list_display = [
        "invoice",
        "session",
        "service_type",
        "rate",
        "total",
    ]
    list_filter = ["service_type"]
    search_fields = ["invoice__invoice_number", "description"]
    readonly_fields = ["total"]

    fieldsets = (
        (gettext_lazy("Session"), {"fields": ("invoice", "session", "service_type")}),
        (gettext_lazy("Billing"), {"fields": ("rate", "quantity", "total")}),
        (gettext_lazy("Details"), {"fields": ("description",), "classes": ("collapse",)}),
    )
