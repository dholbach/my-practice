"""
GebüH billing models — Ziffern catalogue and per-session service recording.

Only used when Client.needs_gebueh_invoice is True (clients whose insurer
requires itemised GebüH billing). Self-paying clients are unaffected.
"""

from decimal import Decimal

from django.db import models

from .session import Session
from .base import TimestampedModel


class GebuhZiffer(models.Model):
    """
    A single entry in the GebüH fee schedule (Gebührenverzeichnis für Heilpraktiker).

    satz_max is always billed (Höchstsatz); satz_min is stored for reference only.
    Frequency constraints (max_haeufigkeit / bezugszeitraum_tage) drive soft warnings
    in the quick-entry UI but never hard-block saving.
    """

    nummer = models.CharField(max_length=10, unique=True, verbose_name="Ziffer")
    bezeichnung = models.CharField(max_length=300, verbose_name="Bezeichnung")
    satz_max = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Höchstsatz (€)",
        help_text="Wird für die Abrechnung verwendet",
    )
    satz_min = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Mindestsatz (€)",
        help_text="Referenzwert, wird nicht abgerechnet",
    )
    anmerkung = models.TextField(
        blank=True,
        verbose_name="Anmerkung",
        help_text="Abrechnungshinweise (z.B. Alleinleistung, Häufigkeitsbeschränkung)",
    )
    max_haeufigkeit = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Max. Häufigkeit",
        help_text="Maximale Anzahl innerhalb des Bezugszeitraums",
    )
    bezugszeitraum_tage = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Bezugszeitraum (Tage)",
        help_text="Zeitraum in Tagen für die Häufigkeitsprüfung",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Reihenfolge",
        help_text="Anzeigereihenfolge in der Schnellerfassung",
    )

    class Meta:
        ordering = ["sort_order", "nummer"]
        verbose_name = "GebüH-Ziffer"
        verbose_name_plural = "GebüH-Ziffern"

    def __str__(self) -> str:
        return f"Ziffer {self.nummer} – {self.bezeichnung}"


class Leistungserfassung(TimestampedModel):
    """
    A single GebüH service line recorded for one session.

    betrag and vereinbarter_betrag are stored at entry time so they survive
    future changes to the rate table or the client's hourly rate.

    vereinbarter_betrag = client.hourly_rate_60 × (session.duration / 60),
    computed and frozen when the entry is created.
    """

    session = models.ForeignKey(
        Session,
        on_delete=models.PROTECT,
        related_name="gebueh_leistungen",
        verbose_name="Sitzung",
    )
    ziffer = models.ForeignKey(
        GebuhZiffer,
        on_delete=models.PROTECT,
        related_name="leistungen",
        verbose_name="GebüH-Ziffer",
    )
    betrag = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="GebüH-Betrag (€)",
        help_text="= Höchstsatz der Ziffer zum Zeitpunkt der Erfassung",
    )
    vereinbarter_betrag = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Vereinbarter Betrag (€)",
        help_text="Honorar für die Sitzung (hourly_rate × duration/60), eingefroren bei Erfassung",
    )

    class Meta:
        ordering = ["session__session_date", "ziffer__sort_order"]
        verbose_name = "Leistungserfassung"
        verbose_name_plural = "Leistungserfassungen"
        indexes = [
            models.Index(
                fields=["session"],
                name="leistung_session_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.session} – Ziffer {self.ziffer.nummer}"

    @classmethod
    def compute_vereinbarter_betrag(cls, session: Session) -> Decimal:
        """Derive the agreed fee from the client's hourly rate and session duration."""
        client = session.client
        rate = client.hourly_rate_60 or Decimal("0")
        duration_hours = Decimal(str(session.duration)) / Decimal("60")
        return (rate * duration_hours).quantize(Decimal("0.01"))
