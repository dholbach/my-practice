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
from django.utils.translation import gettext_lazy as _

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
        (Language.DE, _("German")),
        (Language.EN, _("English")),
    ]

    id = models.AutoField(primary_key=True)

    # Practice relationship - which practice this client belongs to
    practice = models.ForeignKey(
        "Practice",
        on_delete=models.PROTECT,
        related_name="clients",
        verbose_name=_("Practice"),
        help_text=_("Which practice this client is assigned to"),
    )

    client_code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name=_("Client code"),
        help_text=_("2-3 letter client initials (e.g., DE, JM)"),
    )
    full_name = models.CharField(max_length=200, verbose_name=_("Full name"))
    date_of_birth = models.DateField(null=True, blank=True, verbose_name=_("Date of birth"))
    first_seen_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("First appointment"),
        help_text=_("Date of the first intro session/appointment"),
    )
    email = models.EmailField(blank=True, validators=[EmailValidator()], verbose_name=_("Email"))
    phone = models.CharField(max_length=50, blank=True, verbose_name=_("Phone"))
    address = models.TextField(blank=True, verbose_name=_("Address"))
    cost_carrier = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Cost carrier"),
        help_text=_("Cost carrier / health insurance (e.g. 'self-pay', 'Allianz PKV')"),
    )
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    # Onboarding workflow
    intake_sent_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Intake form handed out"),
        help_text=_("Date the intake form was handed out/sent"),
    )
    contract_signed_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Contract signed"),
        help_text=_("Date the treatment contract was signed"),
    )
    questionnaire_sent_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Questionnaire handed out"),
        help_text=_("Date the anamnesis questionnaire was handed out/sent"),
    )
    onboarding_complete_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Onboarding complete"),
        help_text=_("Date the entire onboarding process was completed"),
    )

    hourly_rate_60 = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("90.00"),
        verbose_name=_("Hourly rate (60 min)"),
        help_text=_("Rate for 60-minute session"),
    )
    hourly_rate_90 = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("130.00"),
        verbose_name=_("Hourly rate (90 min)"),
        help_text=_("Rate for 90-minute session"),
    )
    cancellation_fee = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Cancellation fee"),
    )

    language = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default=Language.DE,
        verbose_name=_("Preferred language"),
    )
    salutation = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Email salutation"),
        help_text=_(
            "Custom salutation for emails (e.g., 'Dear John', 'Liebe Maria'). "
            "If empty, will use 'Dear {name}' (EN) or 'Liebe:r {name}' (DE)."
        ),
    )
    active = models.BooleanField(default=True, verbose_name=_("Active"))
    needs_gebueh_invoice = models.BooleanField(
        default=False,
        verbose_name=_("GebüH-Rechnung"),
        help_text=_("GebüH-Ziffern und Diagnose auf der Rechnung ausweisen (PKV / Beihilfe)"),
    )
    is_online_client = models.BooleanField(
        default=False,
        verbose_name=_("Online client"),
        help_text=_("Check if this client primarily has online sessions"),
    )

    tags: models.ManyToManyField = models.ManyToManyField(
        "ClientTag",
        blank=True,
        related_name="clients",
        verbose_name=_("Tags"),
        help_text=_("Tags for organizing and categorizing clients"),
    )

    # Use custom QuerySet
    objects = ClientQuerySet.as_manager()

    class Meta:
        ordering = ["-active", "full_name"]
        verbose_name = _("Client")
        verbose_name_plural = _("Clients")

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
        (DocumentType.INTRO_NOTES, _("Intro meeting (notes)")),
        (DocumentType.INTAKE, _("Intake form")),
        (DocumentType.ANAMNESE, _("Anamnesis questionnaire")),
        (DocumentType.CONTRACT, _("Treatment contract")),
        (DocumentType.REFERRAL, _("Referral")),
        (DocumentType.OTHER, _("Other")),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name=_("Client"),
    )
    document_type = models.CharField(
        max_length=20,
        choices=DOC_TYPE_CHOICES,
        default=DocumentType.OTHER,
        verbose_name=_("Document type"),
    )
    file = models.FileField(
        upload_to=client_document_upload_path,
        verbose_name=_("File"),
        help_text=_("PDF, JPG, PNG or DOCX"),
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Description"),
    )
    document_date = models.DateField(
        default=date.today,
        verbose_name=_("Document date"),
        help_text=_("Date of the document (e.g. signing date)"),
    )

    class Meta:
        ordering = ["-document_date", "-created_at"]
        verbose_name = _("Client document")
        verbose_name_plural = _("Client documents")

    def __str__(self) -> str:
        return (
            f"{self.client.client_code} — {self.get_document_type_display()} ({self.document_date})"
        )

    @property
    def filename(self) -> str:
        """Return just the filename without directory path."""
        return Path(self.file.name or "").name if self.file else ""
