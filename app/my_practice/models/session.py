"""Session models — central Session object."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from .client import Client


class Session(models.Model):
    """
    Central session object linking billing (InvoiceItem) and clinical records (SessionLog).

    Both InvoiceItem and SessionLog FK to this model — they never reference each other directly.
    A Session may exist without a linked InvoiceItem (e.g., cancelled session with a note)
    and without a SessionLog (e.g., historical billing data before P-009).
    """

    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="sessions",
        verbose_name=_("Client"),
    )
    session_date = models.DateField(verbose_name=_("Session date"), db_index=True)
    session_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Time"),
        help_text=_("Session start (from calendar import)"),
    )
    duration = models.IntegerField(
        default=60,
        verbose_name=_("Duration (minutes)"),
    )
    cancelled = models.BooleanField(
        default=False,
        verbose_name=_("Cancelled"),
        help_text=_("Session was cancelled (no-show)"),
        db_index=True,
    )
    group_size = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_("Group size"),
        help_text=_(
            "Number of participants (>1 for group sessions); affects therapist-hours calculation"
        ),
    )
    billable = models.BooleanField(
        default=True,
        verbose_name=_("Billable"),
        help_text=_("Non-billable sessions (e.g. intro meeting) are ignored in monthly billing"),
        db_index=True,
    )
    calendar_event_id = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Calendar event ID"),
        help_text=_("Google Calendar event ID if imported"),
    )

    class Meta:
        ordering = ["-session_date", "-session_time"]
        verbose_name = _("Session")
        verbose_name_plural = _("Sessions")
        indexes = [
            models.Index(fields=["client", "session_date"], name="session_client_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.client.client_code} – {self.session_date.strftime('%d.%m.%Y')}"
