"""Admin configuration for Invoice and InvoiceItem."""

from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext, gettext_lazy, ngettext

from ..models import Invoice, InvoiceItem
from ..utils.formatting import format_currency_de


class InvoiceItemAdminForm(forms.ModelForm):
    """Runs InvoiceItem's session/description checks as form-level checks —
    session is blank=True on the model (P-122), so without this the admin
    would only find out about a violation via a raw ValidationError raised
    inside save(), producing an unhandled 500 instead of a normal form
    error. Reuses InvoiceItem.validate_*() (models/invoice.py) rather than
    re-deriving the same rules here."""

    class Meta:
        model = InvoiceItem
        # The set "__all__" expanded to, written out: this form backs both
        # InvoiceItemInline and the standalone InvoiceItemAdmin, so `invoice`
        # has to stay editable for the latter. Listing them means a new model
        # field is no longer silently exposed here.
        fields = [
            "invoice",
            "session",
            "description",
            "service_type",
            "rate",
            "quantity",
            "group_size",
            "total",
        ]

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

    # Items of an issued invoice are frozen (signals.py); show them read-only
    # rather than letting a save fail with an error page.
    def has_add_permission(self, request, obj=None):
        return not (obj and obj.is_protected) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return not (obj and obj.is_protected) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not (obj and obj.is_protected) and super().has_delete_permission(request, obj)


class InvoiceAdminForm(forms.ModelForm):
    """Refuses moving an issued invoice back to draft as a form error, rather
    than as the signal's InvoiceLockedError surfacing as an error page."""

    class Meta:
        model = Invoice
        # Matches InvoiceAdmin.fieldsets minus the read-only fields.
        fields = [
            "invoice_number",
            "client",
            "invoice_date",
            "status",
            "paid_date",
            "tax_rate",
            "notes",
        ]

    def clean_status(self):
        status = self.cleaned_data["status"]
        if self.instance.pk and self.instance.is_protected and status == Invoice.Status.DRAFT:
            raise forms.ValidationError(
                gettext(
                    "An issued invoice cannot be set back to draft. "
                    "Cancel it and create a corrected copy instead."
                )
            )
        return status


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Invoice admin with improved search (Django 5.1)"""

    form = InvoiceAdminForm

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
        return format_html("<strong>{}</strong>", format_currency_de(obj.total))

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_protected:
            # What the client was sent (LOCKED_INVOICE_FIELDS); status,
            # paid_date and notes stay editable.
            readonly += ["invoice_number", "client", "invoice_date", "tax_rate"]
        return readonly

    def has_delete_permission(self, request, obj=None):
        return not (obj and obj.is_protected) and super().has_delete_permission(request, obj)

    def delete_queryset(self, request, queryset):
        """Bulk delete skips issued invoices still within retention."""
        protected = [invoice for invoice in queryset if invoice.is_protected]
        if protected:
            self.message_user(
                request,
                ngettext(
                    "%(count)s issued invoice was kept: it is still within its retention period.",
                    "%(count)s issued invoices were kept: they are still within their "
                    "retention period.",
                    len(protected),
                )
                % {"count": len(protected)},
                messages.WARNING,
            )
        super().delete_queryset(request, queryset.exclude(pk__in=[i.pk for i in protected]))

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # An issued invoice keeps the totals it was sent with (signals.py), even
        # where older data disagrees with its items.
        if not obj.is_locked:
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

    def has_change_permission(self, request, obj=None):
        return not (obj and obj.invoice.is_protected) and super().has_change_permission(
            request, obj
        )

    def has_delete_permission(self, request, obj=None):
        return not (obj and obj.invoice.is_protected) and super().has_delete_permission(
            request, obj
        )

    fieldsets = (
        (gettext_lazy("Session"), {"fields": ("invoice", "session", "service_type")}),
        (gettext_lazy("Billing"), {"fields": ("rate", "quantity", "total")}),
        (gettext_lazy("Details"), {"fields": ("description",), "classes": ("collapse",)}),
    )
