"""Financial tracking models for withdrawals and expenses"""

from enum import StrEnum
from pathlib import Path

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

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
        (Category.SALARY, _("Salary / personal")),
        (Category.TAX, _("Tax prepayment")),
        (Category.PRIVATE_TRANSFER, _("Private transfer")),
        (Category.OTHER, _("Other")),
        # Incoming / adjustments
        (Category.CONTRIBUTION, _("Capital contribution")),
        (Category.CORRECTION, _("Incorrect posting / correction")),
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
        verbose_name=_("Practice"),
    )

    date = models.DateField(verbose_name=_("Date"))
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Amount"),
        help_text=_("Negative amount for corrections/reversals"),
    )
    description = models.TextField(
        blank=True, verbose_name=_("Notes"), help_text=_("Optional: purpose")
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default=Category.SALARY,
        verbose_name=_("Category"),
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

    # Wording matches the existing choices already reused verbatim in
    # bank_expense_review.html — keep in sync if either changes.
    CATEGORY_CHOICES = [
        (Category.MIETE, _("Rent")),
        (Category.TELEFON, _("Phone")),
        (Category.VERBAND, _("Association / membership fees")),
        (Category.VERSICHERUNG, _("Insurance")),
        (Category.KONTO, _("Account / account fees")),
        (Category.WEBSEITE, _("Website / domain")),
        (Category.WERBUNG, _("Advertising / marketing")),
        (Category.SOFTWARE, _("Software")),
        (Category.SELBSTERFAHRUNG, _("Personal therapy (training)")),
        (Category.SUPERVISION, _("Supervision")),
        (Category.TRAINING, _("Training / continuing education")),
        (Category.AUSBILDUNG_ORT, _("Training location")),
        (Category.GRUPPE, _("Group")),
        (Category.MATERIALIEN, _("Materials")),
        (Category.HARDWARE, _("Hardware")),
        (Category.LITERATUR, _("Literature")),
        (Category.KONGRESS, _("Conference")),
        (Category.OTHER, _("Other")),
    ]

    # Practice relationship
    practice = models.ForeignKey(
        "Practice",
        on_delete=models.PROTECT,
        related_name="expenses",
        verbose_name=_("Practice"),
    )

    date = models.DateField(verbose_name=_("Date"))
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Amount"),
        help_text=_("Enter amount as a positive number"),
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default=Category.OTHER,
        verbose_name=_("Category"),
    )
    has_invoice = models.BooleanField(default=False, verbose_name=_("Invoice available"))
    is_tax_deductible = models.BooleanField(default=True, verbose_name=_("Tax deductible"))
    is_filed_in_tax_return = models.BooleanField(
        default=False, verbose_name=_("Filed in tax return")
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
        verbose_name=_("Expense"),
    )
    file = models.FileField(
        upload_to=expense_attachment_upload_path,
        verbose_name=_("File"),
        help_text=_("PDF, JPG or PNG of the receipt / invoice"),
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = _("Receipt")
        verbose_name_plural = _("Receipts")

    def __str__(self) -> str:
        return f"{self.expense} — {Path(self.file.name or '').name}"


class TaxYearNote(models.Model):
    """
    Per-year tax record: allocation note, and the annual settlement result.

    Stores things like "Revenue ratio 95/5 for 2025 — HO and commute split accordingly."
    Also records the Steuerbescheid outcome (Nachzahlung or Erstattung) once known.
    One record per practice per year; used as audit documentation.
    """

    practice = models.ForeignKey(
        "Practice",
        on_delete=models.CASCADE,
        related_name="tax_year_notes",
        verbose_name=_("Practice"),
    )
    year = models.PositiveSmallIntegerField(verbose_name=_("Tax year"), db_index=True)
    allocation_note = models.TextField(
        blank=True,
        verbose_name=_("Allocation note"),
        help_text=_(
            "Documented split key, e.g. "
            '"Revenue share 95/5 for 2025 — HO allowance and commuter allowance split accordingly."'
        ),
    )
    settlement_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Tax back payment / refund"),
        help_text=_(
            "Positive = back payment to the tax office, negative = refund from the tax office"
        ),
    )
    settlement_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Assessment date"),
        help_text=_("Date of the tax assessment notice"),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("practice", "year")]
        ordering = ["-year"]
        verbose_name = _("Tax year note")
        verbose_name_plural = _("Tax year notes")

    def __str__(self) -> str:
        return f"{self.practice} — {self.year}"
