"""Client inquiry / lead tracking model."""

from datetime import date
from enum import StrEnum

from django.db import models

from .base import PracticeScopedManager, PracticeScopedQuerySet, TimestampedModel


class InquirySource(StrEnum):
    """Channel through which the prospective client found the practice."""

    GOOGLE_ADS = "google_ads"
    GOOGLE_ORGANIC = "google_organic"
    WEBSITE = "website"
    REFERRAL = "referral"
    DIRECTORY = "directory"
    ITS_COMPLICATED = "its_complicated"
    NETWORK = "network"
    OTHER = "other"


INQUIRY_SOURCE_CHOICES = [
    (InquirySource.GOOGLE_ADS, "Google Ads"),
    (InquirySource.GOOGLE_ORGANIC, "Google (organisch)"),
    (InquirySource.WEBSITE, "Website"),
    (InquirySource.REFERRAL, "Empfehlung"),
    (InquirySource.DIRECTORY, "Therapeutenliste"),
    (InquirySource.ITS_COMPLICATED, "It's Complicated"),
    (InquirySource.NETWORK, "Netzwerk / Kolleg:innen"),
    (InquirySource.OTHER, "Sonstiges"),
]


class InquiryStatus(StrEnum):
    """Pipeline stage for an incoming inquiry."""

    NEW = "new"
    CONTACTED = "contacted"
    INTRO_MEETING = "intro_meeting"
    WAITLIST = "waitlist"
    IN_INTAKE = "in_intake"
    CONVERTED = "converted"
    DECLINED = "declined"
    UNREACHABLE = "unreachable"
    NOT_SUITABLE = "not_suitable"


INQUIRY_STATUS_CHOICES = [
    (InquiryStatus.NEW, "Neu"),
    (InquiryStatus.CONTACTED, "Kontaktiert"),
    (InquiryStatus.INTRO_MEETING, "Vorgespräch"),
    (InquiryStatus.WAITLIST, "Warteliste"),
    (InquiryStatus.IN_INTAKE, "Aufnahme läuft"),
    (InquiryStatus.CONVERTED, "Aufgenommen"),
    (InquiryStatus.DECLINED, "Abgelehnt"),
    (InquiryStatus.UNREACHABLE, "Nicht erreichbar"),
    (InquiryStatus.NOT_SUITABLE, "Kein Match"),
]


class ClientInquiryQuerySet(PracticeScopedQuerySet):
    """Custom QuerySet for ClientInquiry."""

    def open(self) -> "ClientInquiryQuerySet":
        """Return inquiries that are still in-progress (not closed)."""
        closed = {
            InquiryStatus.CONVERTED,
            InquiryStatus.DECLINED,
            InquiryStatus.UNREACHABLE,
            InquiryStatus.NOT_SUITABLE,
        }
        return self.exclude(status__in=closed)


INQUIRY_LANGUAGE_CHOICES = [
    ("de", "Deutsch"),
    ("en", "English"),
]


class ClientInquiry(TimestampedModel):
    """
    Tracks a prospective client from first contact through intake.

    Separate from Client — represents a lead before conversion.
    After conversion, links to the resulting Client via converted_client.
    """

    practice = models.ForeignKey(
        "Practice",
        on_delete=models.CASCADE,
        related_name="inquiries",
        verbose_name="Praxis",
    )
    full_name = models.CharField(max_length=200, verbose_name="Name")
    email = models.EmailField(blank=True, verbose_name="E-Mail")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Telefon")
    source = models.CharField(
        max_length=20,
        choices=INQUIRY_SOURCE_CHOICES,
        verbose_name="Quelle",
    )
    status = models.CharField(
        max_length=20,
        choices=INQUIRY_STATUS_CHOICES,
        default=InquiryStatus.NEW,
        verbose_name="Status",
    )
    inquiry_date = models.DateField(
        default=date.today,
        verbose_name="Eingangsdatum",
    )
    language = models.CharField(
        max_length=2,
        choices=INQUIRY_LANGUAGE_CHOICES,
        default="de",
        verbose_name="Sprache",
        help_text="Bevorzugte Sprache der anfragenden Person",
    )
    notes = models.TextField(blank=True, verbose_name="Notizen")
    initial_contact_notes = models.TextField(
        blank=True,
        verbose_name="Erstkontakt-Notizen",
        help_text="Notizen aus dem ersten Vorgespräch (Anliegen, Erwartungen, Eindrücke)",
    )

    # Milestone dates — each records when that pipeline stage was reached
    contacted_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Rückmeldung am",
        help_text="Datum deiner ersten Antwort / Kontaktaufnahme",
    )
    intro_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Vorgespräch am",
        help_text="Datum des Vorgesprächs",
    )
    decision_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Entscheidung am",
        help_text="Datum der Klient:in-Entscheidung (Aufnahme oder Absage / Kein Match)",
    )
    converted_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Aufgenommen am",
        help_text="Datum der Aufnahme als Klient:in",
    )

    converted_client = models.OneToOneField(
        "Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_inquiry",
        verbose_name="Klient:in (nach Aufnahme)",
    )

    objects = PracticeScopedManager.from_queryset(ClientInquiryQuerySet)()

    class Meta:
        ordering = ["-inquiry_date", "-created_at"]
        verbose_name = "Anfrage"
        verbose_name_plural = "Anfragen"

    def __str__(self) -> str:
        return f"{self.full_name} ({self.get_status_display()})"

    def is_closed(self) -> bool:
        """Return True if inquiry is in a terminal state."""
        return self.status in {
            InquiryStatus.CONVERTED,
            InquiryStatus.DECLINED,
            InquiryStatus.UNREACHABLE,
            InquiryStatus.NOT_SUITABLE,
        }


class MarketingPeriod(TimestampedModel):
    """
    Records a marketing channel or budget active during a given timeframe.

    Examples:
      - "Google Ads 5 €/Tag" from April to August 2026
      - "It's Complicated Premium" from January 2026 onwards

    Used to correlate inquiry sources with active spend / subscription periods.
    Future: show stats (leads per period, conversion rate) on the inquiry list.
    """

    practice = models.ForeignKey(
        "Practice",
        on_delete=models.CASCADE,
        related_name="marketing_periods",
        verbose_name="Praxis",
    )
    start_date = models.DateField(verbose_name="Von")
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Bis",
        help_text="Leer lassen wenn noch aktiv",
    )
    description = models.CharField(
        max_length=500,
        verbose_name="Beschreibung",
        help_text='z.B. "Google Ads 5 €/Tag" oder "It\'s Complicated Premium"',
    )

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Marketing-Zeitraum"
        verbose_name_plural = "Marketing-Zeiträume"

    def __str__(self) -> str:
        end = self.end_date.strftime("%m/%Y") if self.end_date else "laufend"
        return f"{self.start_date.strftime('%m/%Y')}–{end}: {self.description}"

    def is_active(self) -> bool:
        """Return True if this period covers today."""
        today = date.today()
        return self.start_date <= today and (self.end_date is None or self.end_date >= today)
