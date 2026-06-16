"""Session models — central Session object."""

from django.db import models

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
        verbose_name="Klient",
    )
    session_date = models.DateField(verbose_name="Sitzungsdatum", db_index=True)
    session_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Uhrzeit",
        help_text="Sitzungsbeginn (aus Kalenderimport)",
    )
    duration = models.IntegerField(
        default=60,
        verbose_name="Dauer (Minuten)",
    )
    cancelled = models.BooleanField(
        default=False,
        verbose_name="Abgesagt",
        help_text="Sitzung wurde abgesagt (Ausfall)",
        db_index=True,
    )
    group_size = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Gruppengröße",
        help_text="Anzahl Teilnehmer (>1 für Gruppensitzungen); beeinflusst Therapeutenstunden-Berechnung",
    )
    billable = models.BooleanField(
        default=True,
        verbose_name="Abrechenbar",
        help_text="Nicht abrechenbare Sitzungen (z.B. Erstgespräch) werden in der Monatsabrechnung ignoriert",
        db_index=True,
    )
    calendar_event_id = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Kalender-Event-ID",
        help_text="Google Calendar event ID if imported",
    )

    class Meta:
        ordering = ["-session_date", "-session_time"]
        verbose_name = "Sitzung"
        verbose_name_plural = "Sitzungen"
        indexes = [
            models.Index(fields=["client", "session_date"], name="session_client_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.client.client_code} – {self.session_date.strftime('%d.%m.%Y')}"
