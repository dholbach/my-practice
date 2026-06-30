"""Client model for managing therapy clients"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import cast

from django.core.validators import EmailValidator
from django.db import models
from django.db.models import Max, Prefetch
from django.utils.text import slugify

from .base import PracticeScopedQuerySet, TimestampedModel


class ClientQuerySet(PracticeScopedQuerySet):
    """Custom QuerySet for Client model with optimized queries"""

    def with_invoices(
        self, order_by: str = "-invoice_date", include_tags: bool = True
    ) -> "ClientQuerySet":
        """
        Prefetch invoices with items and optionally tags.

        Args:
            order_by: Order for invoices ("-invoice_date" or "invoice_date")
            include_tags: Whether to also prefetch client tags

        Returns:
            QuerySet: Clients with optimized prefetches
        """
        from .invoice import Invoice

        qs = self.prefetch_related(
            Prefetch(
                "invoices",
                queryset=Invoice.objects.order_by(order_by).prefetch_related("items"),
            )
        )
        if include_tags:
            qs = qs.prefetch_related("tags")
        return qs

    def with_activity_data(self) -> "ClientQuerySet":
        """
        Annotate clients with activity metrics:
        - last_invoice_date: Date of most recent invoice
        - last_session_date: Date of most recent session
        - total_revenue: Total revenue from paid invoices
        - total_sessions: Total number of sessions from paid invoices

        Returns:
            QuerySet: Clients annotated with activity data
        """
        from ..utils import RevenueCalculator

        return cast(
            "ClientQuerySet",
            self.annotate(
                last_invoice_date=Max("invoices__invoice_date"),
                last_session_date=Max("sessions__session_date"),
                total_revenue=RevenueCalculator.get_client_revenue_subquery(),
                total_sessions=RevenueCalculator.get_client_sessions_subquery(),
            ),
        )


class Client(TimestampedModel):
    """Client model - matches existing 'clients' table"""

    class Language(StrEnum):
        """Invoice language for bilingual invoice generation."""

        DE = "de"
        EN = "en"

    LANGUAGE_CHOICES = [
        (Language.DE, "Deutsch"),
        (Language.EN, "English"),
    ]

    id = models.AutoField(primary_key=True)

    # Practice relationship - which practice this client belongs to
    practice = models.ForeignKey(
        "Practice",
        on_delete=models.PROTECT,
        related_name="clients",
        verbose_name="Praxis",
        help_text="Welcher Praxis dieser Klient zugeordnet ist",
    )

    client_code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Klientenkürzel",
        help_text="2-3 letter client initials (e.g., DE, JM)",
    )
    full_name = models.CharField(max_length=200, verbose_name="Vollständiger Name")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Geburtsdatum")
    first_seen_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Ersttermin",
        help_text="Datum des ersten Vorgespräch/Termin",
    )
    email = models.EmailField(blank=True, validators=[EmailValidator()], verbose_name="E-Mail")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Telefon")
    address = models.TextField(blank=True, verbose_name="Adresse")
    cost_carrier = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Kostenträger",
        help_text="Kostenträger / Krankenversicherung (z.B. 'Selbstzahler', 'Allianz PKV')",
    )
    notes = models.TextField(blank=True, verbose_name="Notizen")

    # Onboarding workflow
    intake_sent_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Aufnahmebogen ausgehändigt",
        help_text="Datum, an dem der Aufnahmebogen übergeben/versendet wurde",
    )
    contract_signed_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Vertrag unterzeichnet",
        help_text="Datum, an dem der Behandlungsvertrag unterschrieben wurde",
    )
    questionnaire_sent_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fragebogen ausgehändigt",
        help_text="Datum, an dem der Anamnesebogen übergeben/versendet wurde",
    )
    onboarding_complete_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Aufnahme abgeschlossen",
        help_text="Datum, an dem der gesamte Aufnahmeprozess abgeschlossen wurde",
    )

    hourly_rate_60 = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("90.00"),
        verbose_name="Stundensatz (60 Min)",
        help_text="Rate for 60-minute session",
    )
    hourly_rate_90 = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("130.00"),
        verbose_name="Stundensatz (90 Min)",
        help_text="Rate for 90-minute session",
    )
    cancellation_fee = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Ausfall-Gebühr",
    )

    language = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default=Language.DE,
        verbose_name="Bevorzugte Sprache",
    )
    salutation = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="E-Mail Anrede",
        help_text="Custom salutation for emails (e.g., 'Dear John', 'Liebe Maria'). "
        "If empty, will use 'Dear {name}' (EN) or 'Liebe:r {name}' (DE).",
    )
    active = models.BooleanField(default=True, verbose_name="Aktiv")
    needs_gebueh_invoice = models.BooleanField(
        default=False,
        verbose_name="GebüH-Rechnung",
        help_text="GebüH-Ziffern und Diagnose auf der Rechnung ausweisen (PKV / Beihilfe)",
    )
    is_online_client = models.BooleanField(
        default=False,
        verbose_name="Online Klient",
        help_text="Check if this client primarily has online sessions",
    )

    tags: models.ManyToManyField = models.ManyToManyField(
        "ClientTag",
        blank=True,
        related_name="clients",
        verbose_name="Tags",
        help_text="Tags for organizing and categorizing clients",
    )

    # Use custom QuerySet
    objects = ClientQuerySet.as_manager()

    class Meta:
        ordering = ["-active", "full_name"]
        verbose_name = "Klient"
        verbose_name_plural = "Klienten"

    def __str__(self) -> str:
        return self.client_code


def client_document_upload_path(instance: "ClientDocument", filename: str) -> str:
    """Store client documents under clients/<code>/<year>/<type>-<date>.<ext> with collision handling."""
    from django.conf import settings

    client_code = instance.client.client_code.lower()
    doc_date = instance.document_date or date.today()
    year = doc_date.year
    doc_type = instance.document_type
    date_str = doc_date.isoformat()
    ext = Path(filename).suffix.lower()
    slug = slugify(Path(filename).stem)[:40] or "document"
    candidate = f"clients/{client_code}/{year}/{doc_type}-{date_str}-{slug}{ext}"
    media_root = Path(settings.MEDIA_ROOT)
    counter = 2
    while (media_root / candidate).exists():
        candidate = f"clients/{client_code}/{year}/{doc_type}-{date_str}-{slug}-{counter}{ext}"
        counter += 1
    return candidate


class ClientDocument(TimestampedModel):
    """A document attached to a client (contract, intake form, referral, etc.)."""

    class DocumentType(StrEnum):
        INTRO_NOTES = "intro_notes"
        INTAKE = "intake"
        ANAMNESE = "anamnese"
        CONTRACT = "contract"
        REFERRAL = "referral"
        OTHER = "other"

    DOC_TYPE_CHOICES = [
        (DocumentType.INTRO_NOTES, "Vorgespräch (Notizen)"),
        (DocumentType.INTAKE, "Aufnahmebogen"),
        (DocumentType.ANAMNESE, "Anamnesebogen"),
        (DocumentType.CONTRACT, "Behandlungsvertrag"),
        (DocumentType.REFERRAL, "Überweisung"),
        (DocumentType.OTHER, "Sonstiges"),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="Klient",
    )
    document_type = models.CharField(
        max_length=20,
        choices=DOC_TYPE_CHOICES,
        default=DocumentType.OTHER,
        verbose_name="Dokumententyp",
    )
    file = models.FileField(
        upload_to=client_document_upload_path,
        verbose_name="Datei",
        help_text="PDF, JPG, PNG oder DOCX",
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Beschreibung",
    )
    document_date = models.DateField(
        default=date.today,
        verbose_name="Dokumentdatum",
        help_text="Datum des Dokuments (z.B. Unterzeichnungsdatum)",
    )

    class Meta:
        ordering = ["-document_date", "-created_at"]
        verbose_name = "Klientendokument"
        verbose_name_plural = "Klientendokumente"

    def __str__(self) -> str:
        return (
            f"{self.client.client_code} — {self.get_document_type_display()} ({self.document_date})"
        )

    @property
    def filename(self) -> str:
        """Return just the filename without directory path."""
        return Path(self.file.name or "").name if self.file else ""
