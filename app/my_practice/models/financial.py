"""Financial tracking models for withdrawals and expenses"""

from enum import StrEnum
from pathlib import Path

from django.db import models
from django.utils.text import slugify

from .base import PracticeScopedManager, TimestampedModel


def expense_receipt_upload_path(instance: "CompanyExpense", filename: str) -> str:
    """Store receipts under taxes/<year>/<slug>.<ext> using the expense description.

    If a file with the same name already exists, appends " #2", " #3", etc.
    e.g. supervision.pdf → supervision #2.pdf → supervision #3.pdf
    """
    from django.conf import settings

    year = instance.date.year if instance.date else "unknown"
    # Prefer the expense description as the filename; fall back to original filename stem
    title = instance.description or Path(filename).stem
    stem = slugify(title)[:50] or "receipt"
    ext = Path(filename).suffix.lower()

    # Enumerate if a file with this name already exists in MEDIA_ROOT.
    # Exception: if the file belongs to THIS instance (update/replace), allow
    # overwriting in place rather than creating a new enumerated filename.
    candidate = f"taxes/{year}/{stem}{ext}"
    media_root = Path(settings.MEDIA_ROOT)
    existing_name = instance.receipt.name if instance.receipt else None
    counter = 2
    while (media_root / candidate).exists():
        if existing_name and candidate == existing_name:
            break  # File belongs to this instance — overwrite in place
        candidate = f"taxes/{year}/{stem} #{counter}{ext}"
        counter += 1

    return candidate


class CompanyWithdrawal(TimestampedModel):
    """Track money withdrawn from company account for personal use"""

    class Category(StrEnum):
        """Withdrawal category — determines cash-flow direction for accounting."""

        SALARY = "salary"
        TAX = "tax"
        PRIVATE_TRANSFER = "private_transfer"
        OTHER = "other"
        # Incoming / adjustments
        CONTRIBUTION = "contribution"
        CORRECTION = "correction"

    CATEGORY_CHOICES = [
        (Category.SALARY, "Gehalt / Personal"),
        (Category.TAX, "Steuervorauszahlung"),
        (Category.PRIVATE_TRANSFER, "Privat-Überweisung"),
        (Category.OTHER, "Sonstiges"),
        # Incoming / adjustments
        (Category.CONTRIBUTION, "Kapitaleinlage"),
        (Category.CORRECTION, "Fehlbuchung / Korrektur"),
    ]

    # Categories that represent money flowing *out* of the business account
    OUTGOING_CATEGORIES = {
        Category.SALARY,
        Category.TAX,
        Category.PRIVATE_TRANSFER,
        Category.OTHER,
    }
    # Categories that represent money flowing *in* or adjustments
    INCOMING_CATEGORIES = {Category.CONTRIBUTION, Category.CORRECTION}

    # Practice relationship
    practice = models.ForeignKey(
        "Practice",
        on_delete=models.PROTECT,
        related_name="withdrawals",
        verbose_name="Praxis",
    )

    date = models.DateField(verbose_name="Datum")
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Betrag",
        help_text="Negativer Betrag für Korrekturen/Rückbuchungen",
    )
    description = models.TextField(
        blank=True, verbose_name="Notizen", help_text="Optional: Verwendungszweck"
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default=Category.SALARY,
        verbose_name="Kategorie",
    )

    # Practice-scoped manager
    objects = PracticeScopedManager()

    class Meta:
        ordering = ["-date"]
        verbose_name = "Company Withdrawal / Entnahme"
        verbose_name_plural = "Company Withdrawals / Entnahmen"
        indexes = [
            models.Index(fields=["date"], name="withdrawal_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.date.strftime('%d.%m.%Y')}: {self.amount}€"


class CompanyExpense(TimestampedModel):
    """Track company business expenses for tax and profit calculation"""

    class Category(StrEnum):
        """Expense category for tax reporting and profit calculation."""

        MIETE = "miete"
        TELEFON = "telefon"
        VERBAND = "verband"
        VERSICHERUNG = "versicherung"
        KONTO = "konto"
        WEBSEITE = "webseite"
        WERBUNG = "werbung"
        SOFTWARE = "software"
        SELBSTERFAHRUNG = "selbsterfahrung"
        SUPERVISION = "supervision"
        TRAINING = "training"
        AUSBILDUNG_ORT = "ausbildung_ort"
        GRUPPE = "gruppe"
        MATERIALIEN = "materialien"
        HARDWARE = "hardware"
        LITERATUR = "literatur"
        KONGRESS = "kongress"
        OTHER = "other"

    CATEGORY_CHOICES = [
        (Category.MIETE, "Miete"),
        (Category.TELEFON, "Telefon"),
        (Category.VERBAND, "Verband / Mitgliedsbeiträge"),
        (Category.VERSICHERUNG, "Versicherung"),
        (Category.KONTO, "Konto / Kontoführung"),
        (Category.WEBSEITE, "Webseite / Domain"),
        (Category.WERBUNG, "Werbung / Marketing"),
        (Category.SOFTWARE, "Software"),
        (Category.SELBSTERFAHRUNG, "Selbsterfahrung"),
        (Category.SUPERVISION, "Supervision"),
        (Category.TRAINING, "Training / Weiterbildung"),
        (Category.AUSBILDUNG_ORT, "Ausbildung Ort"),
        (Category.GRUPPE, "Gruppe"),
        (Category.MATERIALIEN, "Materialien"),
        (Category.HARDWARE, "Hardware"),
        (Category.LITERATUR, "Literatur"),
        (Category.KONGRESS, "Kongress"),
        (Category.OTHER, "Sonstiges"),
    ]

    # Practice relationship
    practice = models.ForeignKey(
        "Practice",
        on_delete=models.PROTECT,
        related_name="expenses",
        verbose_name="Praxis",
    )

    date = models.DateField(verbose_name="Datum")
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Betrag",
        help_text="Betrag als positive Zahl eingeben",
    )
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default=Category.OTHER,
        verbose_name="Kategorie",
    )
    has_invoice = models.BooleanField(default=False, verbose_name="Rechnung vorhanden")
    is_tax_deductible = models.BooleanField(default=True, verbose_name="Steuerlich absetzbar")
    is_filed_in_tax_return = models.BooleanField(
        default=False, verbose_name="In Steuererklärung eingetragen"
    )

    # Practice-scoped manager
    objects = PracticeScopedManager()

    class Meta:
        ordering = ["-date"]
        verbose_name = "Company Expense / Ausgabe"
        verbose_name_plural = "Company Expenses / Ausgaben"
        indexes = [
            models.Index(fields=["date"], name="expense_date_idx"),
            models.Index(fields=["category"], name="expense_category_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.date} - {self.get_category_display()}: {self.amount}€"


def expense_attachment_upload_path(instance: "ExpenseReceipt", filename: str) -> str:
    """Store attachments under taxes/<year>/<slug> with enumeration for collisions."""
    from django.conf import settings

    expense = instance.expense
    year = expense.date.year if expense.date else "unknown"
    title = expense.description or Path(filename).stem
    stem = slugify(title)[:50] or "receipt"
    ext = Path(filename).suffix.lower()
    candidate = f"taxes/{year}/{stem}{ext}"
    media_root = Path(settings.MEDIA_ROOT)
    counter = 2
    while (media_root / candidate).exists():
        candidate = f"taxes/{year}/{stem} #{counter}{ext}"
        counter += 1
    return candidate


class ExpenseReceipt(models.Model):
    """A single file attachment (Beleg) for a CompanyExpense."""

    expense = models.ForeignKey(
        CompanyExpense,
        on_delete=models.CASCADE,
        related_name="receipts",
        verbose_name="Ausgabe",
    )
    file = models.FileField(
        upload_to=expense_attachment_upload_path,
        verbose_name="Datei",
        help_text="PDF, JPG oder PNG der Quittung / Rechnung",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "Beleg"
        verbose_name_plural = "Belege"

    def __str__(self) -> str:
        return f"{self.expense} — {Path(self.file.name or '').name}"


class TaxYearNote(models.Model):
    """
    A short practitioner note recording the chosen allocation key for a tax year.

    Stores things like "Revenue ratio 95/5 for 2025 — HO and commute split accordingly."
    One note per practice per year; used as audit documentation.
    """

    practice = models.ForeignKey(
        "Practice",
        on_delete=models.CASCADE,
        related_name="tax_year_notes",
        verbose_name="Praxis",
    )
    year = models.PositiveSmallIntegerField(verbose_name="Steuerjahr", db_index=True)
    allocation_note = models.TextField(
        blank=True,
        verbose_name="Aufteilungsnotiz",
        help_text=(
            "Dokumentierter Aufteilungsschluessel, z. B. "
            '"Einnahmenanteil 95/5 fuer 2025 - HO-Pauschale und Pendlerpauschale anteilig."'
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("practice", "year")]
        ordering = ["-year"]
        verbose_name = "Steuer-Jahresnotiz"
        verbose_name_plural = "Steuer-Jahresnotizen"

    def __str__(self) -> str:
        return f"{self.practice} — {self.year}"
