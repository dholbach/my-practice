"""Bank statement and transaction models"""

from enum import StrEnum

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy


def _normalize_iban(iban: str) -> str:
    """Remove spaces and uppercase for IBAN comparison."""
    return iban.replace(" ", "").upper()


class BankTransaction(models.Model):
    """
    Bank statement transaction from CSV import.

    Represents a single transaction line from a bank statement CSV.
    Used for automatic invoice payment matching and reconciliation.
    """

    class Confidence(StrEnum):
        EXACT = "exact"
        FUZZY = "fuzzy"
        MANUAL = "manual"
        IGNORED = "ignored"
        UNMATCHED = "unmatched"
        AUTO_WITHDRAWAL = "auto-withdrawal"
        AUTO_EXPENSE = "auto-expense"
        AUTO_CONTRIBUTION = "auto-contribution"
        AUTO_CORRECTION = "auto-correction"

    CONFIDENCE_CHOICES = [
        (Confidence.EXACT, gettext_lazy("Exact Match")),
        (Confidence.FUZZY, gettext_lazy("Fuzzy Match (±5€)")),
        (Confidence.MANUAL, gettext_lazy("Manual Assignment")),
        (Confidence.IGNORED, gettext_lazy("Ignored (Expense/Duplicate)")),
        (Confidence.UNMATCHED, gettext_lazy("Unmatched")),
        (Confidence.AUTO_WITHDRAWAL, gettext_lazy("Auto-Created Withdrawal")),
        (Confidence.AUTO_EXPENSE, gettext_lazy("Auto-Created Expense")),
        (Confidence.AUTO_CONTRIBUTION, gettext_lazy("Auto-Created Contribution (Kapitaleinlage)")),
        (Confidence.AUTO_CORRECTION, gettext_lazy("Auto-Created Correction (Fehlbuchung)")),
    ]

    # Practice relationship
    practice = models.ForeignKey(
        "Practice",
        on_delete=models.CASCADE,
        related_name="bank_transactions",
        verbose_name=gettext_lazy("Practice"),
    )

    # Transaction details (from CSV)
    transaction_date = models.DateField(
        verbose_name=gettext_lazy("Booking date"),
        help_text=gettext_lazy("Transaction booking date"),
    )
    value_date = models.DateField(
        verbose_name=gettext_lazy("Value date"),
        help_text=gettext_lazy("Value date"),
    )
    payer_name = models.CharField(
        max_length=200,
        verbose_name=gettext_lazy("Payer/payee name"),
        help_text=gettext_lazy("Name of payer/payee"),
    )
    payer_iban = models.CharField(
        max_length=34,
        blank=True,
        verbose_name=gettext_lazy("Payer/payee IBAN"),
    )
    reference = models.TextField(
        verbose_name=gettext_lazy("Payment reference"),
        help_text=gettext_lazy("Payment reference text"),
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=gettext_lazy("Amount"),
        help_text=gettext_lazy("Transaction amount (positive=income, negative=expense)"),
    )
    balance_after = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=gettext_lazy("Balance after transaction"),
        help_text=gettext_lazy("Account balance after transaction"),
    )

    # Matching information
    matched_invoice = models.ForeignKey(
        "Invoice",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bank_transactions",
        verbose_name=gettext_lazy("Matched invoice"),
        help_text=gettext_lazy("Invoice this transaction was matched to"),
    )
    match_confidence = models.CharField(
        max_length=20,
        choices=CONFIDENCE_CHOICES,
        default="unmatched",
        verbose_name=gettext_lazy("Match confidence"),
    )
    extracted_invoice_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=gettext_lazy("Extracted invoice number"),
        help_text=gettext_lazy("Invoice number extracted from reference text"),
    )

    # Metadata
    imported_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=gettext_lazy("Imported on"),
    )
    processed = models.BooleanField(
        default=False,
        verbose_name=gettext_lazy("Processed"),
        help_text=gettext_lazy("Whether transaction has been processed/matched"),
    )
    notes = models.TextField(
        blank=True,
        verbose_name=gettext_lazy("Notes"),
        help_text=gettext_lazy("Manual notes about this transaction"),
    )

    # Links to auto-created financial records
    linked_expense = models.ForeignKey(
        "CompanyExpense",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bank_transactions",
        verbose_name=gettext_lazy("Linked expense"),
        help_text=gettext_lazy(
            "CompanyExpense auto-created or manually assigned for this transaction"
        ),
    )
    linked_withdrawal = models.ForeignKey(
        "CompanyWithdrawal",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bank_transactions",
        verbose_name=gettext_lazy("Linked withdrawal"),
        help_text=gettext_lazy(
            "CompanyWithdrawal auto-created or manually assigned for this transaction"
        ),
    )

    # Source validation
    account_iban = models.CharField(
        max_length=34,
        blank=True,
        verbose_name=gettext_lazy("Account IBAN"),
        help_text=gettext_lazy(
            "IBAN of the source account from the CSV export – must match the practice IBAN"
        ),
    )

    class Meta:
        unique_together = [["practice", "transaction_date", "amount", "reference"]]
        ordering = ["-transaction_date"]
        verbose_name = gettext_lazy("Bank Transaction")
        verbose_name_plural = gettext_lazy("Bank Transactions")
        indexes = [
            models.Index(fields=["practice", "transaction_date"]),
            models.Index(fields=["practice", "processed"]),
            models.Index(fields=["practice", "match_confidence"]),
        ]

    def __str__(self) -> str:
        return f"{self.transaction_date} - {self.payer_name}: {self.amount}€"

    @property
    def is_income(self) -> bool:
        """Check if transaction is income (positive amount)"""
        return self.amount > 0

    @property
    def is_expense(self) -> bool:
        """Check if transaction is expense (negative amount)"""
        return self.amount < 0

    @property
    def is_matched(self) -> bool:
        """Check if transaction is matched to an invoice"""
        return self.matched_invoice is not None

    def clean(self) -> None:
        """Validate that account_iban matches the practice's IBAN."""
        if self.account_iban and self.practice_id:
            practice_iban = _normalize_iban(self.practice.iban)
            csv_iban = _normalize_iban(self.account_iban)
            if practice_iban and csv_iban != practice_iban:
                raise ValidationError(
                    {
                        "account_iban": _(
                            "Account IBAN %(csv_iban)s does not match the practice IBAN %(practice_iban)s."
                        )
                        % {"csv_iban": self.account_iban, "practice_iban": self.practice.iban}
                    }
                )
