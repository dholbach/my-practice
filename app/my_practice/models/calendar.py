"""Google Calendar integration model"""

from datetime import date
from enum import StrEnum

from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import PracticeScopedManager, TimestampedModel


class GoogleCalendarToken(TimestampedModel):
    """Store Google Calendar OAuth2 tokens for calendar import"""

    # Practice relationship - each practice has its own calendar token
    practice = models.ForeignKey(
        "Practice",
        on_delete=models.CASCADE,
        related_name="calendar_tokens",
        verbose_name=_("Practice"),
        null=True,  # Temporary - will be required after migration
    )

    # OAuth2 tokens (stored as JSON)
    token = models.TextField(help_text=_("Encrypted OAuth2 token JSON"))
    refresh_token = models.TextField(blank=True, help_text=_("Refresh token for token renewal"))
    token_uri = models.CharField(max_length=500, default="https://oauth2.googleapis.com/token")
    client_id = models.CharField(max_length=500)
    client_secret = models.CharField(max_length=500)
    scopes = models.JSONField(default=list, help_text=_("List of granted scopes"))

    # Metadata
    expires_at = models.DateTimeField(null=True, blank=True, help_text=_("Token expiration time"))
    is_active = models.BooleanField(
        default=True, help_text=_("Whether this token is currently active")
    )

    # Practice-scoped manager
    objects = PracticeScopedManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Google Calendar Token")
        verbose_name_plural = _("Google Calendar Tokens")

    def __str__(self) -> str:
        status = _("Active") if self.is_active else _("Inactive")
        expires = (
            self.expires_at.strftime("%Y-%m-%d %H:%M") if self.expires_at else str(_("No expiry"))
        )
        return f"{_('Calendar Token')} ({status}, {_('expires')}: {expires})"

    @property
    def is_expired(self) -> bool:
        """Check if token is expired"""
        if not self.expires_at:
            return False
        from django.utils import timezone

        return timezone.now() >= self.expires_at


class PendingCalendarEvent(models.Model):
    """
    Persistent queue of calendar events fetched automatically (P-013 Phase 1).

    Events are fetched every few hours by the fetch_calendar_events management
    command and held here until approved/imported to an invoice, skipped, or
    detected as cancelled in Google Calendar.

    google_event_id is unique so repeated fetches are idempotent.
    """

    class Status(StrEnum):
        """Calendar event lifecycle status."""

        PENDING = "pending"
        IMPORTED = "imported"
        SKIPPED = "skipped"
        CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (Status.PENDING, _("Pending")),
        (Status.IMPORTED, _("Imported")),
        (Status.SKIPPED, _("Skipped")),
        (Status.CANCELLED, _("Cancelled")),
    ]

    practice = models.ForeignKey(
        "Practice",
        on_delete=models.CASCADE,
        related_name="pending_calendar_events",
        verbose_name=_("Practice"),
    )
    google_event_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="Google Event ID",
    )
    summary = models.CharField(max_length=500, verbose_name=_("Summary"))
    event_date = models.DateField(verbose_name=_("Date"))
    event_time = models.TimeField(null=True, blank=True, verbose_name=_("Time"))
    duration_minutes = models.IntegerField(verbose_name=_("Duration (minutes)"))
    matched_client = models.ForeignKey(
        "Client",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pending_calendar_events",
        verbose_name=_("Client"),
    )
    suggested_service_type = models.ForeignKey(
        "ServiceType",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pending_calendar_events",
        verbose_name=_("Service type"),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=Status.PENDING,
        verbose_name=_("Status"),
    )
    session = models.OneToOneField(
        "Session",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pending_calendar_event",
        verbose_name=_("Session"),
    )
    fetched_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Fetched on"))
    missing_since = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Missing since"),
        help_text=_("First fetch where the event was no longer found in the calendar"),
    )

    class Meta:
        ordering = ["event_date", "event_time"]
        verbose_name = _("Pending calendar event")
        verbose_name_plural = _("Pending calendar events")
        indexes = [
            models.Index(fields=["practice", "status"], name="pce_practice_status_idx"),
            models.Index(fields=["matched_client", "event_date"], name="pce_client_date_idx"),
        ]

    def __str__(self) -> str:
        client = self.matched_client.client_code if self.matched_client else "?"
        return f"{client} — {self.event_date} ({self.duration_minutes} min) [{self.get_status_display()}]"

    @property
    def billing_month(self) -> "date":
        """First day of the month this session should be billed in."""
        return self.event_date.replace(day=1)
