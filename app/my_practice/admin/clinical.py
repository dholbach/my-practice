"""Admin configuration for ClientProfile, SessionLog, SupervisionItem, ClientNote."""

from django.contrib import admin
from django.utils.translation import gettext_lazy

from ..models import ClientNote, ClientProfile, SessionLog, SupervisionItem


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
