"""
Django Admin configuration for payments app.
"""

from django.contrib import admin, messages
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, ngettext

from .models import (
    BankTransaction,
    ChecklistItemPause,
    Client,
    ClientAlias,
    ClientDocument,
    ClientInquiry,
    ClientNote,
    ClientProfile,
    ClientTag,
    CompanyExpense,
    CompanyWithdrawal,
    GebuhZiffer,
    Invoice,
    InvoiceItem,
    Leistungserfassung,
    MarketingPeriod,
    OperationalChecklistCompletion,
    PendingCalendarEvent,
    Practice,
    PracticeTodo,
    ServiceType,
    Session,
    SessionLog,
    SupervisionItem,
    TimeOff,
)


@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin):
    """Practice admin with field groups for better organization (Django 5.1 feature)"""

    fieldsets = (
        (
            gettext_lazy("Basic Information"),
            {
                "fields": (
                    "name",
                    "short_title_de",
                    "short_title_en",
                    "title",
                    "subtitle_de",
                    "subtitle_en",
                ),
                "description": gettext_lazy("Basic information about the practice"),
            },
        ),
        (
            gettext_lazy("Address"),
            {
                "fields": ("street", "postal_code", "city", "country"),
                "classes": ("collapse",),  # Collapsible group
            },
        ),
        (
            gettext_lazy("Contact"),
            {
                "fields": ("email", "email_from_name", "website", "phone"),
                "classes": ("collapse",),
            },
        ),
        (
            gettext_lazy("Bank Details"),
            {
                "fields": ("bank_name", "iban", "bic", "private_bank_account"),
                "classes": ("collapse",),
                "description": gettext_lazy(
                    "Business account for invoices. The private bank account (IBAN) is used "
                    "during bank import to automatically detect withdrawals and capital "
                    "contributions."
                ),
            },
        ),
        (
            gettext_lazy("Tax"),
            {
                "fields": ("tax_id", "vat_exempt_text_de", "vat_exempt_text_en"),
                "classes": ("collapse",),
            },
        ),
        (
            gettext_lazy("Memberships"),
            {
                "fields": ("memberships_de", "memberships_en"),
                "classes": ("collapse",),
            },
        ),
        (
            gettext_lazy("Images"),
            {
                "fields": (
                    "logo",
                    "logo_preview",
                    "signature",
                    "signature_preview",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            gettext_lazy("Payment Terms"),
            {
                "fields": (
                    "payment_terms_days",
                    "payment_terms_text_de",
                    "payment_terms_text_en",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            gettext_lazy("Email Templates for Invoices"),
            {
                "fields": (
                    "invoice_email_subject_de",
                    "invoice_email_subject_en",
                    "invoice_email_body_de",
                    "invoice_email_body_en",
                    "email_signature",
                ),
                "classes": ("collapse", "wide"),  # Collapsible + wide for text fields
                "description": gettext_lazy(
                    "Templates for invoice emails. Available placeholders: {salutation}, "
                    "{invoice_number}, {amount}, {date}, {client_name}"
                ),
            },
        ),
        (
            gettext_lazy("Capacity Monitoring (P-013)"),
            {
                "fields": (
                    "monthly_target_hours",
                    "monthly_target_revenue",
                ),
                "classes": ("collapse",),
                "description": gettext_lazy(
                    "Monthly targets for hours and revenue. When set, the dashboard shows "
                    "warnings for declining numbers."
                ),
            },
        ),
        (
            gettext_lazy("Travel Costs (P-027)"),
            {
                "fields": (
                    "commute_distance_km",
                    "practice_weekdays",
                ),
                "classes": ("collapse",),
                "description": gettext_lazy(
                    "Distance allowance (§9 (1) no. 4 EStG). One-way distance in km + "
                    "weekdays on which the practice is attended (JSON list, e.g. "
                    "[0, 1, 2, 3, 4] for Mon–Fri)."
                ),
            },
        ),
    )

    readonly_fields = ["logo_preview", "signature_preview"]

    @admin.display(description=gettext_lazy("Logo Preview"))
    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="max-height: 200px;"/>', obj.logo.url)
        return _("No logo uploaded")

    @admin.display(description=gettext_lazy("Signature Preview"))
    def signature_preview(self, obj):
        if obj.signature:
            return format_html('<img src="{}" style="max-height: 100px;"/>', obj.signature.url)
        return _("No signature uploaded")

    def has_add_permission(self, request):
        # Only allow one Practice instance
        return not Practice.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False


class ClientDocumentInline(admin.TabularInline):
    model = ClientDocument
    extra = 0
    fields = ["document_type", "file", "description", "document_date"]
    readonly_fields = ["created_at"]


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Client admin with improved search (Django 5.1 field lookups)"""

    list_display = [
        "client_code",
        "full_name",
        "email",
        "language",
        "practice",
        "online_badge",
        "active_status",
        "hourly_rate_60",
        "hourly_rate_90",
        "tag_list",
    ]
    list_filter = [
        "active",
        "is_online_client",
        "language",
        "practice",
        "tags",
        "created_at",
    ]

    # Django 5.1 feature: Field lookups in search (istartswith for better matching)
    search_fields = [
        "client_code",
        "full_name__istartswith",  # Case-insensitive prefix search
        "email__icontains",
        "notes__icontains",
    ]

    readonly_fields = ["created_at", "updated_at"]
    filter_horizontal = ["tags"]
    inlines = [ClientDocumentInline]

    fieldsets = (
        (
            gettext_lazy("Basic Information"),
            {
                "fields": (
                    "client_code",
                    "full_name",
                    "date_of_birth",
                    "language",
                    "practice",
                )
            },
        ),
        (gettext_lazy("Contact"), {"fields": ("email", "phone", "address")}),
        (
            gettext_lazy("Email Settings"),
            {
                "fields": ("salutation",),
                "description": gettext_lazy(
                    "Custom email salutation (e.g., 'Dear John', 'Liebe Maria'). If empty, "
                    "defaults to 'Dear {name}' (EN) or 'Liebe:r {name}' (DE)"
                ),
            },
        ),
        (
            gettext_lazy("Rates"),
            {
                "fields": ("hourly_rate_60", "hourly_rate_90", "cancellation_fee"),
                "description": gettext_lazy("Standard hourly rates for this client"),
            },
        ),
        (
            gettext_lazy("Organization"),
            {
                "fields": ("tags",),
                "description": gettext_lazy("Tags for organizing and categorizing clients"),
            },
        ),
        (
            gettext_lazy("Additional"),
            {"fields": ("notes", "active", "is_online_client", "needs_gebueh_invoice")},
        ),
        (
            gettext_lazy("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description=gettext_lazy("Status"))
    def active_status(self, obj):
        if obj.active:
            return mark_safe(
                f'<span style="color: green; font-weight: bold;">✓ {_("Active")}</span>'
            )
        return mark_safe(f'<span style="color: red;">✗ {_("Inactive")}</span>')

    @admin.display(description=gettext_lazy("Format"), ordering="is_online_client")
    def online_badge(self, obj):
        if obj.is_online_client:
            return mark_safe(f'<span style="color: #667eea;">💻 {_("Online")}</span>')
        return mark_safe(f'<span style="color: #48bb78;">🏢 {_("On-site")}</span>')

    @admin.display(description=gettext_lazy("Tags"))
    def tag_list(self, obj):
        tags = obj.tags.all()
        if not tags:
            return "-"
        return ", ".join([tag.name for tag in tags])


@admin.register(ClientAlias)
class ClientAliasAdmin(admin.ModelAdmin):
    """Admin interface for client payment name aliases."""

    list_display = ["alias_name", "client_link", "notes_display", "created_at"]
    list_filter = ["client", "created_at"]
    search_fields = ["alias_name", "client__client_code", "client__full_name", "notes"]
    date_hierarchy = "created_at"
    ordering = ["client", "alias_name"]
    readonly_fields = ["created_at"]

    fieldsets = (
        (
            gettext_lazy("Assignment"),
            {
                "fields": ("client", "alias_name"),
            },
        ),
        (
            gettext_lazy("Details"),
            {
                "fields": ("notes", "created_at"),
            },
        ),
    )

    @admin.display(description=gettext_lazy("Client"), ordering="client")
    def client_link(self, obj):
        """Display link to client."""
        return format_html(
            '<a href="/admin/my_practice/client/{}/change/">{}</a>',
            obj.client.pk,
            obj.client.client_code,
        )

    @admin.display(description=gettext_lazy("Notes"))
    def notes_display(self, obj):
        """Display truncated notes."""
        if not obj.notes:
            return "-"
        if len(obj.notes) > 50:
            return f"{obj.notes[:47]}..."
        return obj.notes


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


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = ["session", "service_type", "rate", "quantity", "group_size", "total"]
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
        from datetime import date

        updated = 0
        for invoice in queryset:
            invoice.status = "paid"
            if not invoice.paid_date:
                invoice.paid_date = date.today()
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


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    """Central session hub — links billing and clinical records."""

    list_display = [
        "__str__",
        "client",
        "session_date",
        "duration",
        "cancelled",
        "group_size",
        "has_log",
        "has_invoice_item",
    ]
    list_filter = ["cancelled", "session_date", "client__practice"]
    search_fields = ["client__client_code", "client__full_name", "calendar_event_id"]
    date_hierarchy = "session_date"
    ordering = ["-session_date"]
    autocomplete_fields = ["client"]
    readonly_fields = ["calendar_event_id"]

    @admin.display(description=gettext_lazy("Log"), boolean=True)
    def has_log(self, obj):
        return hasattr(obj, "log")

    @admin.display(description=gettext_lazy("Invoice"), boolean=True)
    def has_invoice_item(self, obj):
        return obj.invoice_items.exists()


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    """
    ClientProfile admin — read-only for encrypted fields.
    Fields are displayed but content is Fernet-encrypted at rest.
    """

    list_display = ["client", "arbeitsdiagnose_preview", "updated_at"]
    search_fields = ["client__client_code", "client__full_name"]
    ordering = ["client__client_code"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["client"]

    fieldsets = (
        (gettext_lazy("Client"), {"fields": ("client",)}),
        (
            gettext_lazy("Clinical Fields (Fernet-encrypted)"),
            {"fields": ("arbeitsdiagnose", "intake_notes", "case_notes")},
        ),
        (
            gettext_lazy("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description=gettext_lazy("Working Diagnosis"))
    def arbeitsdiagnose_preview(self, obj):
        val = obj.arbeitsdiagnose or ""
        return val[:60] + "…" if len(val) > 60 else val or "—"


@admin.register(SessionLog)
class SessionLogAdmin(admin.ModelAdmin):
    """
    SessionLog admin — mood_tags and session_type are unencrypted and filterable.
    Content and reflection fields are Fernet-encrypted.
    """

    list_display = ["session", "session_type", "mood_tags_display", "updated_at"]
    list_filter = ["session_type", "session__session_date"]
    search_fields = ["session__client__client_code", "session__client__full_name"]
    ordering = ["-session__session_date"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (gettext_lazy("Session"), {"fields": ("session",)}),
        (gettext_lazy("Metadata (unencrypted)"), {"fields": ("session_type", "mood_tags")}),
        (
            gettext_lazy("Content (Fernet-encrypted)"),
            {"fields": ("content", "therapist_reflection")},
        ),
        (
            gettext_lazy("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description=gettext_lazy("Tags"))
    def mood_tags_display(self, obj):
        tags = obj.mood_tags or []
        return ", ".join(tags) if tags else "—"


@admin.register(SupervisionItem)
class SupervisionItemAdmin(admin.ModelAdmin):
    """SupervisionItem admin — cross-client supervision queue."""

    list_display = ["client", "status", "content_preview", "created_at"]
    list_filter = ["status", "client__practice"]
    search_fields = ["client__client_code", "client__full_name"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["client"]

    fieldsets = (
        (gettext_lazy("Client & Status"), {"fields": ("client", "status")}),
        (gettext_lazy("Content (Fernet-encrypted)"), {"fields": ("content",)}),
        (
            gettext_lazy("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description=gettext_lazy("Content"))
    def content_preview(self, obj):
        val = obj.content or ""
        return val[:80] + "…" if len(val) > 80 else val or "—"


@admin.register(ClientNote)
class ClientNoteAdmin(admin.ModelAdmin):
    """ClientNote admin — dated freeform notes per client (encrypted)."""

    list_display = ["client", "note_date", "note_type", "content_preview", "updated_at"]
    list_filter = ["note_type", "client__practice"]
    search_fields = ["client__client_code", "client__full_name"]
    ordering = ["-note_date", "-created_at"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["client"]

    fieldsets = (
        (gettext_lazy("Client"), {"fields": ("client",)}),
        (gettext_lazy("Metadata"), {"fields": ("note_date", "note_type")}),
        (gettext_lazy("Content (Fernet-encrypted)"), {"fields": ("content",)}),
        (
            gettext_lazy("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description=gettext_lazy("Content"))
    def content_preview(self, obj):
        val = obj.content or ""
        return val[:80] + "…" if len(val) > 80 else val or "—"


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
        from datetime import date

        current_year = date.today().year
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


@admin.register(TimeOff)
class TimeOffAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "type",
        "start_date",
        "end_date",
        "duration_days",
        "status_badge",
    )
    list_filter = ("type", "start_date", "end_date")
    search_fields = ("title", "notes")
    date_hierarchy = "start_date"
    ordering = ("-start_date",)

    fieldsets = (
        (
            None,
            {
                "fields": ("title", "type", "start_date", "end_date"),
            },
        ),
        (
            gettext_lazy("Additional Information"),
            {
                "fields": ("notes",),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description=gettext_lazy("Status"))
    def status_badge(self, obj):
        """Display colored status badge"""
        if obj.is_current:
            color = "#48bb78"  # green
            status = f"🏖️ {_('Currently Off')}"
        elif obj.is_upcoming:
            color = "#667eea"  # blue
            status = f"📅 {_('Upcoming')}"
        else:
            color = "#a0aec0"  # gray
            status = f"✅ {_('Past')}"

        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 0.85em;">{}</span>',
            color,
            status,
        )


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


@admin.register(PracticeTodo)
class PracticeTodoAdmin(admin.ModelAdmin):
    """Practice TODO admin for task management and weekly planning."""

    list_display = [
        "status_icon",
        "title_display",
        "category_badge",
        "priority_badge",
        "due_date",
        "created_at",
        "completed_at",
    ]
    list_filter = [
        "completed_at",
        "category",
        "priority",
        "task_type",
        "due_date",
        "practice",
        "created_at",
    ]
    search_fields = ["title", "description"]
    date_hierarchy = "created_at"
    ordering = ["-completed_at", "-priority", "due_date", "-created_at"]
    readonly_fields = ["task_type", "content_type", "object_id"]

    actions = ["mark_completed", "mark_incomplete", "set_high_priority"]

    fieldsets = (
        (
            gettext_lazy("Task Information"),
            {"fields": ("practice", "title", "description")},
        ),
        (
            gettext_lazy("Organization"),
            {"fields": ("category", "priority", "due_date")},
        ),
        (
            gettext_lazy("Status"),
            {"fields": ("completed_at", "snoozed_until")},
        ),
        (
            gettext_lazy("Focus Queue (P-050)"),
            {
                "fields": ("task_type", "content_type", "object_id"),
                "description": gettext_lazy(
                    "Set automatically for materialized tasks — not manually editable."
                ),
            },
        ),
    )

    @admin.display(description="", ordering="completed_at")
    def status_icon(self, obj):
        """Display checkmark for completed tasks."""
        if obj.is_completed:
            return mark_safe('<span style="font-size: 18px;">✅</span>')
        if obj.is_overdue:
            return mark_safe('<span style="font-size: 18px;">⚠️</span>')
        return mark_safe('<span style="font-size: 18px;">⏳</span>')

    @admin.display(description=gettext_lazy("Task"), ordering="title")
    def title_display(self, obj):
        """Display title with strikethrough if completed."""
        if obj.is_completed:
            return format_html(
                '<span style="text-decoration: line-through; color: #a0aec0;">{}</span>',
                obj.title,
            )
        return obj.title

    @admin.display(description=gettext_lazy("Category"), ordering="category")
    def category_badge(self, obj):
        """Display category as a colored badge."""
        badge_styles = {
            "admin": "background: #bee3f8; color: #2c5282;",
            "learning": "background: #c6f6d5; color: #22543d;",
            "financial": "background: #fbd38d; color: #744210;",
            "client": "background: #fbb6ce; color: #702459;",
            "practice": "background: #d6bcfa; color: #44337a;",
            "other": "background: #e2e8f0; color: #2d3748;",
        }
        base_style = badge_styles.get(obj.category, badge_styles["other"])
        return format_html(
            '<span style="{}; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            base_style,
            obj.get_category_display(),
        )

    @admin.display(description=gettext_lazy("Priority"), ordering="priority")
    def priority_badge(self, obj):
        """Display priority as a colored badge."""
        badge_styles = {
            "urgent": "background: #feb2b2; color: #742a2a; font-weight: 700;",
            "high": "background: #fed7aa; color: #7c2d12;",
            "medium": "background: #fef3c7; color: #78350f;",
            "low": "background: #e2e8f0; color: #4a5568;",
        }
        style = badge_styles.get(obj.priority, badge_styles["medium"])
        return format_html(
            '<span style="{}; padding: 3px 8px; border-radius: 4px; font-size: 11px; text-transform: uppercase;">{}</span>',
            style,
            obj.get_priority_display(),
        )

    @admin.action(description=gettext_lazy("Mark as completed"))
    def mark_completed(self, request, queryset):
        """Mark selected tasks as completed."""
        updated = 0
        for todo in queryset.filter(completed_at__isnull=True):
            todo.mark_completed()
            updated += 1
        self.message_user(
            request,
            ngettext(
                "%(count)s task marked as completed.",
                "%(count)s tasks marked as completed.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=gettext_lazy("Mark as incomplete"))
    def mark_incomplete(self, request, queryset):
        """Mark selected tasks as incomplete."""
        updated = 0
        for todo in queryset.filter(completed_at__isnull=False):
            todo.mark_incomplete()
            updated += 1
        self.message_user(
            request,
            ngettext(
                "%(count)s task marked as incomplete.",
                "%(count)s tasks marked as incomplete.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=gettext_lazy("Set high priority"))
    def set_high_priority(self, request, queryset):
        """Set selected tasks to high priority."""
        updated = queryset.update(priority="high")
        self.message_user(
            request,
            ngettext(
                "%(count)s task set to high priority.",
                "%(count)s tasks set to high priority.",
                updated,
            )
            % {"count": updated},
            messages.SUCCESS,
        )


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


# Customize admin site headers
admin.site.site_header = gettext_lazy("Therapy Practice Management")
admin.site.site_title = gettext_lazy("Payments Admin")
admin.site.index_title = gettext_lazy("Welcome to Therapy Practice Management")


@admin.register(OperationalChecklistCompletion)
class OperationalChecklistCompletionAdmin(admin.ModelAdmin):
    list_display = ["checklist_type", "year_month", "completed_at", "notes"]
    list_filter = ["checklist_type"]
    ordering = ["-year_month", "checklist_type"]
    readonly_fields = ["completed_at"]


@admin.register(ChecklistItemPause)
class ChecklistItemPauseAdmin(admin.ModelAdmin):
    list_display = [
        "checklist_type",
        "item_id",
        "reason",
        "paused_until",
        "is_active",
        "created_at",
    ]
    list_filter = ["checklist_type"]
    ordering = ["checklist_type", "item_id"]
    readonly_fields = ["created_at"]

    @admin.display(boolean=True, description=gettext_lazy("Active"))
    def is_active(self, obj: ChecklistItemPause) -> bool:
        return obj.is_active


@admin.register(PendingCalendarEvent)
class PendingCalendarEventAdmin(admin.ModelAdmin):
    """Admin for pending calendar events queue (P-013)."""

    list_display = [
        "event_date",
        "client_code",
        "summary",
        "duration_minutes",
        "status",
        "fetched_at",
    ]
    list_filter = ["status", "practice", "event_date"]
    search_fields = ["summary", "matched_client__client_code", "google_event_id"]
    ordering = ["-event_date"]
    readonly_fields = ["google_event_id", "fetched_at"]
    date_hierarchy = "event_date"
    actions = ["mark_pending", "mark_skipped"]

    @admin.display(description=gettext_lazy("Client"))
    def client_code(self, obj: PendingCalendarEvent) -> str:
        return obj.matched_client.client_code if obj.matched_client else "—"

    @admin.action(description=gettext_lazy("Mark as pending"))
    def mark_pending(self, request, queryset):
        updated = queryset.update(status=PendingCalendarEvent.Status.PENDING)
        self.message_user(
            request,
            ngettext(
                "%(count)s event marked as pending.", "%(count)s events marked as pending.", updated
            )
            % {"count": updated},
            messages.SUCCESS,
        )

    @admin.action(description=gettext_lazy("Mark as skipped"))
    def mark_skipped(self, request, queryset):
        updated = queryset.update(status=PendingCalendarEvent.Status.SKIPPED)
        self.message_user(
            request,
            ngettext(
                "%(count)s event marked as skipped.", "%(count)s events marked as skipped.", updated
            )
            % {"count": updated},
            messages.SUCCESS,
        )


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
