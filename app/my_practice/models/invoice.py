"""Invoice and invoice item models"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from .base import PracticeScopedManager, PracticeScopedQuerySet, TimestampedModel
from .client import Client
from .service import ServiceType


class InvoiceQuerySet(PracticeScopedQuerySet):
    """Custom QuerySet for Invoice with common access patterns."""

    def with_client(self) -> "InvoiceQuerySet":
        """Add select_related for client and practice — avoids N+1 on invoice lists."""
        return self.select_related("client", "practice")

    def with_items(self) -> "InvoiceQuerySet":
        """Prefetch line items with their session and service type."""
        return self.prefetch_related("items__session", "items__service_type")

    def paid_in_year(self, year: int) -> "InvoiceQuerySet":
        """Paid invoices where payment was received in *year* (uses paid_date)."""
        return self.filter(status="paid", paid_date__year=year)

    def in_year(self, year: int) -> "InvoiceQuerySet":
        """Invoices issued in *year* (uses invoice_date)."""
        return self.filter(invoice_date__year=year)


class Invoice(TimestampedModel):
    """Invoice model"""

    class Status(StrEnum):
        """Invoice lifecycle status values."""

        DRAFT = "draft"
        SENT = "sent"
        PAID = "paid"
        CANCELLED = "cancelled"
        WRITTEN_OFF = "written_off"

    STATUS_CHOICES = [
        (Status.DRAFT, gettext_lazy("Draft")),
        (Status.SENT, gettext_lazy("Sent")),
        (Status.PAID, gettext_lazy("Paid")),
        (Status.CANCELLED, gettext_lazy("Cancelled")),
        (Status.WRITTEN_OFF, gettext_lazy("Written off")),
    ]

    # Practice relationship - inherited by InvoiceItems
    practice = models.ForeignKey(
        "Practice",
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name=gettext_lazy("Practice"),
    )

    invoice_number = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name=gettext_lazy("Invoice number"),
        help_text=gettext_lazy("Auto-generated (e.g., JL-5) or enter manually"),
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name=gettext_lazy("Client"),
    )

    invoice_date = models.DateField(
        default=date.today,
        verbose_name=gettext_lazy("Invoice date"),
        help_text=gettext_lazy("Defaults to today"),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=Status.DRAFT,
        verbose_name=gettext_lazy("Status"),
    )

    paid_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=gettext_lazy("Paid on"),
        help_text=gettext_lazy("Date of payment"),
    )

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=gettext_lazy("Subtotal"),
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=gettext_lazy("Tax rate (%)"),
        help_text=gettext_lazy("Kleinunternehmer = 0%"),
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=gettext_lazy("Tax amount"),
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=gettext_lazy("Total amount"),
    )

    notes = models.TextField(blank=True, verbose_name=gettext_lazy("Notes"))

    # Practice-scoped manager with InvoiceQuerySet helpers
    objects = PracticeScopedManager.from_queryset(InvoiceQuerySet)()

    class Meta:
        ordering = ["-invoice_date", "-invoice_number"]
        verbose_name = gettext_lazy("Invoice")
        verbose_name_plural = gettext_lazy("Invoices")
        indexes = [
            models.Index(fields=["invoice_date"], name="invoice_invoice_date_idx"),
            models.Index(fields=["paid_date"], name="invoice_paid_date_idx"),
            models.Index(fields=["status"], name="invoice_status_idx"),
            models.Index(fields=["client", "status"], name="invoice_client_status_idx"),
            models.Index(fields=["-invoice_date", "status"], name="invoice_date_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["invoice_number"],
                name="unique_invoice_number",
                violation_error_message=gettext_lazy("This invoice number already exists."),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.invoice_number} - {self.client.client_code}"

    def clean(self) -> None:
        """Validate invoice data"""
        super().clean()

        # Validate invoice_number uniqueness with helpful error message
        if self.invoice_number:
            # Check if another invoice with same number exists (excluding self)
            duplicate = Invoice.objects.filter(invoice_number=self.invoice_number)
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)

            if duplicate.exists():
                existing = duplicate.first()
                if existing:  # guard for mypy (first() can return None)
                    raise ValidationError(
                        {
                            "invoice_number": _(
                                'Invoice number "%(number)s" already exists '
                                "(invoice for %(client_code)s dated %(date)s)"
                            )
                            % {
                                "number": self.invoice_number,
                                "client_code": existing.client.client_code,
                                "date": existing.invoice_date.strftime("%d.%m.%Y"),
                            }
                        }
                    )

        # Validate paid_date is not before invoice_date
        if self.paid_date and self.invoice_date and self.paid_date < self.invoice_date:
            raise ValidationError(
                {"paid_date": _("Payment date must not be before the invoice date")}
            )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Set invoice_date on creation, then allow manual changes"""
        # Only auto-set date on initial creation, not on every save
        if self.status == Invoice.Status.DRAFT and not self.pk:
            self.invoice_date = date.today()

        # Run validation before saving (unless explicitly skipped)
        skip_validation = kwargs.pop("skip_validation", False)
        if not skip_validation:
            self.full_clean()

        super().save(*args, **kwargs)

    def computed_invoice_date(self) -> date:
        """Return the correct invoice_date for a draft: max(today, latest_session_date)."""
        today = date.today()
        item_dates = [
            item.session.session_date
            for item in self.items.select_related("session").all()
            if item.session_id
        ]
        if item_dates:
            latest = max(item_dates)
            return latest if latest >= today else today
        return today

    def sync_invoice_date(self) -> bool:
        """Persist computed_invoice_date() if it differs from the stored value. Returns True if saved."""
        if self.status != Invoice.Status.DRAFT:
            return False
        correct = self.computed_invoice_date()
        if self.invoice_date != correct:
            self.invoice_date = correct
            self.save(update_fields=["invoice_date"])
            return True
        return False

    def calculate_total(self) -> Decimal:
        """Calculate invoice total from items"""
        from django.db.models import Sum

        # Use database aggregation instead of Python loop for better performance
        subtotal_sum = self.items.aggregate(total=Sum("total"))["total"] or Decimal("0")
        self.subtotal = Decimal(str(subtotal_sum)).quantize(Decimal("0.01"))

        # Calculate tax
        tax_calc = self.subtotal * (self.tax_rate / Decimal("100"))
        self.tax_amount = tax_calc.quantize(Decimal("0.01"))

        # Calculate total
        total_calc = self.subtotal + self.tax_amount
        self.total = total_calc.quantize(Decimal("0.01"))

        return self.total


class InvoiceItem(models.Model):
    """Invoice line items"""

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=gettext_lazy("Invoice"),
    )
    service_type = models.ForeignKey(
        ServiceType, on_delete=models.PROTECT, verbose_name=gettext_lazy("Service Type")
    )

    rate = models.DecimalField(max_digits=6, decimal_places=2, verbose_name=gettext_lazy("Rate"))
    quantity = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        verbose_name=gettext_lazy("Quantity"),
    )
    total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=gettext_lazy("Total"))

    group_size = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=gettext_lazy("Group size"),
        help_text=gettext_lazy(
            "Number of participants for group offerings (default 1 = individual session). "
            "Affects the calculation of therapist hours in analytics."
        ),
    )

    # Link to central Session object — required (NOT NULL)
    session = models.ForeignKey(
        "Session",
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        related_name="invoice_items",
        verbose_name=gettext_lazy("Session"),
        help_text=gettext_lazy(
            "Linked session (central reference for clinical documentation + billing)"
        ),
    )

    class Meta:
        ordering = ["session__session_date"]
        verbose_name = gettext_lazy("Invoice item")
        verbose_name_plural = gettext_lazy("Invoice items")
        indexes = []

    def __str__(self) -> str:
        return f"{self.invoice.invoice_number} - {self.session.session_date}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Auto-calculate total"""
        self.total = self.rate * self.quantity
        super().save(*args, **kwargs)
