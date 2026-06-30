"""
GebüH billing models — Ziffern catalogue and per-session service recording.

Only used when Client.needs_gebueh_invoice is True (clients whose insurer
requires itemised GebüH billing). Self-paying clients are unaffected.
"""

from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import TimestampedModel
from .session import Session


class GebuhZiffer(models.Model):
    """
    A single entry in the GebüH fee schedule (Gebührenverzeichnis für Heilpraktiker).

    satz_max is always billed (Höchstsatz); satz_min is stored for reference only.
    Frequency constraints (max_haeufigkeit / bezugszeitraum_tage) drive soft warnings
    in the quick-entry UI but never hard-block saving.
    """

    nummer = models.CharField(max_length=10, unique=True, verbose_name=_("Ziffer"))
    bezeichnung = models.CharField(max_length=300, verbose_name=_("Bezeichnung"))
    satz_max = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name=_("Höchstsatz (€)"),
        help_text=_("Wird für die Abrechnung verwendet"),
    )
    satz_min = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name=_("Mindestsatz (€)"),
        help_text=_("Referenzwert, wird nicht abgerechnet"),
    )
    anmerkung = models.TextField(
        blank=True,
        verbose_name=_("Anmerkung"),
        help_text=_("Abrechnungshinweise (z.B. Alleinleistung, Häufigkeitsbeschränkung)"),
    )
    max_haeufigkeit = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Max. Häufigkeit"),
        help_text=_("Maximale Anzahl innerhalb des Bezugszeitraums"),
    )
    bezugszeitraum_tage = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Bezugszeitraum (Tage)"),
        help_text=_("Zeitraum in Tagen für die Häufigkeitsprüfung"),
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("Reihenfolge"),
        help_text=_("Anzeigereihenfolge in der Schnellerfassung"),
    )

    class Meta:
        ordering = ["sort_order", "nummer"]
        verbose_name = _("GebüH-Ziffer")
        verbose_name_plural = _("GebüH-Ziffern")

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
        verbose_name=_("Sitzung"),
    )
    ziffer = models.ForeignKey(
        GebuhZiffer,
        on_delete=models.PROTECT,
        related_name="leistungen",
        verbose_name=_("GebüH-Ziffer"),
    )
    betrag = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name=_("GebüH-Betrag (€)"),
        help_text=_("= Höchstsatz der Ziffer zum Zeitpunkt der Erfassung"),
    )
    vereinbarter_betrag = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name=_("Vereinbarter Betrag (€)"),
        help_text=_(
            "Honorar für die Sitzung (hourly_rate × duration/60), eingefroren bei Erfassung"
        ),
    )

    class Meta:
        ordering = ["session__session_date", "ziffer__sort_order"]
        verbose_name = _("Leistungserfassung")
        verbose_name_plural = _("Leistungserfassungen")
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
