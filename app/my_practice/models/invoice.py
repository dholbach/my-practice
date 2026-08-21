"""Invoice and invoice item models"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from .base import PracticeScopedManager, PracticeScopedQuerySet, TimestampedModel
from .client import Client
from .service import ServiceType

if TYPE_CHECKING:
    from .practice import Practice


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
        default=timezone.localdate,
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

        # Defense in depth: client and practice are independent FKs, so nothing else
        # guarantees they agree — catch a cross-practice mismatch before it's saved.
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            raise ValidationError({"client": _("Client does not belong to the selected practice")})

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Set invoice_date on creation, then allow manual changes"""
        # Only auto-set date on initial creation, not on every save
        if self.status == Invoice.Status.DRAFT and not self.pk:
            self.invoice_date = timezone.localdate()

        # Run validation before saving (unless explicitly skipped)
        skip_validation = kwargs.pop("skip_validation", False)
        if not skip_validation:
            self.full_clean()

        super().save(*args, **kwargs)

    def computed_invoice_date(self) -> date:
        """Return the correct invoice_date for a draft: max(today, latest_session_date)."""
        today = timezone.localdate()
        item_dates = [
            item.session.session_date
            for item in self.items.select_related("session").all()
            if item.session_id
        ]
        if item_dates:
            latest = max(item_dates)
            return latest if latest >= today else today
        return today

    @staticmethod
    def days_overdue(invoice_date: date, today: date | None = None) -> int:
        """Days elapsed since invoice_date, for comparing against practice.overdue_after_days
        (or any other threshold). Shared by InvoiceActionsWidgetBuilder.get_overdue_invoices
        (dashboard_widgets.py) and ClientDetailContextBuilder._build_billing_context
        (client_detail_builder.py) so the two don't independently re-derive the same
        elapsed-days calculation."""
        today = today or timezone.localdate()
        return (today - invoice_date).days

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
        validators=[MinValueValidator(Decimal("0.01"))],
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

    # Link to central Session object — required for therapy/coaching items.
    # Nullable for free-form items (day-rate/project billing, P-122); the
    # `description` field below carries the free-text label instead.
    session = models.ForeignKey(
        "Session",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoice_items",
        verbose_name=gettext_lazy("Session"),
        help_text=gettext_lazy(
            "Linked session (central reference for clinical documentation + billing)"
        ),
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=gettext_lazy("Description"),
        help_text=gettext_lazy(
            "Free-text line item label, used instead of a linked session "
            "(day-rate/project billing) — only available when the practice "
            "allows free-form invoice items"
        ),
    )

    class Meta:
        # "pk" tiebreaker: free-form items have session=None, so
        # session__session_date alone leaves them in undefined relative order
        # (Postgres doesn't guarantee stable ordering across NULL-tied rows).
        ordering = ["session__session_date", "pk"]
        verbose_name = gettext_lazy("Invoice item")
        verbose_name_plural = gettext_lazy("Invoice items")
        indexes = []

    def __str__(self) -> str:
        if self.session_id:
            return f"{self.invoice.invoice_number} - {self.session.session_date}"
        return f"{self.invoice.invoice_number} - {self.description}"

    @property
    def is_free_form(self) -> bool:
        """True for description-only items with no linked session (P-122)."""
        return self.session_id is None

    @staticmethod
    def validate_exclusive_session_or_description(has_session: bool, has_description: bool) -> None:
        """Exactly one of session/description must be set. Shared by save()
        below and InvoiceItemAdminForm (admin.py) so the rule and its
        message live in one place."""
        if has_session == has_description:
            raise ValidationError(
                _(
                    "Invoice item needs either a linked session or a description, "
                    "not both or neither."
                )
            )

    @staticmethod
    def validate_free_form_allowed(has_description: bool, practice: "Practice") -> None:
        """Description-only items require the practice's free-form-items
        flag. Shared by clean()/save() below and InvoiceItemAdminForm
        (admin.py)."""
        if has_description and not practice.allows_free_form_items:
            raise ValidationError(
                {"description": _("This practice doesn't allow free-form invoice items.")}
            )

    def clean(self) -> None:
        """Check the free-form-items flag, when reachable.

        Only the free-form-permission half of validation runs here — the
        "exactly one of session/description" structural check lives in
        save() instead: at model-clean time inside the invoice formset,
        session-linked rows haven't had their Session attached yet (the view
        resolves session_date -> Session only after the formset validates,
        see InvoiceFormsetMixin) — checking session_id here would reject
        every ordinary session row before it ever gets a session.

        This also only fires once self.invoice_id is set, i.e. for edits and
        admin operations on an existing item — on create, the formset's
        placeholder Invoice has no pk yet, so invoice_id is still None here.
        save() below re-checks unconditionally and is the backstop for the
        create path.
        """
        if self.invoice_id:
            self.validate_free_form_allowed(bool(self.description), self.invoice.practice)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Auto-calculate total; enforce exactly one of session/description.

        Runs both checks unconditionally: by save() time the invoice FK is
        always set, making this the one point that reliably sees a complete
        instance on every path (create, edit, admin) — see clean()'s
        docstring for why it can only cover part of this at that point.
        """
        has_session = self.session_id is not None
        has_description = bool(self.description)
        self.validate_exclusive_session_or_description(has_session, has_description)
        self.validate_free_form_allowed(has_description, self.invoice.practice)
        self.total = self.rate * self.quantity
        super().save(*args, **kwargs)
