"""Bank statement and transaction models"""

from enum import StrEnum

from django.core.exceptions import ValidationError
from django.db import models


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
        (Confidence.EXACT, "Exact Match"),
        (Confidence.FUZZY, "Fuzzy Match (±5€)"),
        (Confidence.MANUAL, "Manual Assignment"),
        (Confidence.IGNORED, "Ignored (Expense/Duplicate)"),
        (Confidence.UNMATCHED, "Unmatched"),
        (Confidence.AUTO_WITHDRAWAL, "Auto-Created Withdrawal"),
        (Confidence.AUTO_EXPENSE, "Auto-Created Expense"),
        (Confidence.AUTO_CONTRIBUTION, "Auto-Created Contribution (Kapitaleinlage)"),
        (Confidence.AUTO_CORRECTION, "Auto-Created Correction (Fehlbuchung)"),
    ]

    # Practice relationship
    practice = models.ForeignKey(
        "Practice",
        on_delete=models.CASCADE,
        related_name="bank_transactions",
        verbose_name="Praxis",
    )

    # Transaction details (from CSV)
    transaction_date = models.DateField(
        verbose_name="Buchungstag",
        help_text="Transaction booking date",
    )
    value_date = models.DateField(
        verbose_name="Valutadatum",
        help_text="Value date",
    )
    payer_name = models.CharField(
        max_length=200,
        verbose_name="Name Zahlungsbeteiligter",
        help_text="Name of payer/payee",
    )
    payer_iban = models.CharField(
        max_length=34,
        blank=True,
        verbose_name="IBAN Zahlungsbeteiligter",
    )
    reference = models.TextField(
        verbose_name="Verwendungszweck",
        help_text="Payment reference text",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Betrag",
        help_text="Transaction amount (positive=income, negative=expense)",
    )
    balance_after = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Saldo nach Buchung",
        help_text="Account balance after transaction",
    )

    # Matching information
    matched_invoice = models.ForeignKey(
        "Invoice",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bank_transactions",
        verbose_name="Zugeordnete Rechnung",
        help_text="Invoice this transaction was matched to",
    )
    match_confidence = models.CharField(
        max_length=20,
        choices=CONFIDENCE_CHOICES,
        default="unmatched",
        verbose_name="Match-Genauigkeit",
    )
    extracted_invoice_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Extrahierte Rechnungsnummer",
        help_text="Invoice number extracted from reference text",
    )

    # Metadata
    imported_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Importiert am",
    )
    processed = models.BooleanField(
        default=False,
        verbose_name="Verarbeitet",
        help_text="Whether transaction has been processed/matched",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notizen",
        help_text="Manual notes about this transaction",
    )

    # Links to auto-created financial records
    linked_expense = models.ForeignKey(
        "CompanyExpense",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bank_transactions",
        verbose_name="Verknüpfte Ausgabe",
        help_text="CompanyExpense auto-created or manually assigned for this transaction",
    )
    linked_withdrawal = models.ForeignKey(
        "CompanyWithdrawal",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bank_transactions",
        verbose_name="Verknüpfte Entnahme",
        help_text="CompanyWithdrawal auto-created or manually assigned for this transaction",
    )

    # Source validation
    account_iban = models.CharField(
        max_length=34,
        blank=True,
        verbose_name="Konto-IBAN",
        help_text="IBAN des Auftragskontos aus dem CSV-Export – muss mit der Praxis-IBAN übereinstimmen",
    )

    class Meta:
        unique_together = [["practice", "transaction_date", "amount", "reference"]]
        ordering = ["-transaction_date"]
        verbose_name = "Bank Transaction"
        verbose_name_plural = "Bank Transactions"
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
                        "account_iban": (
                            f"Konto-IBAN {self.account_iban} stimmt nicht mit der "
                            f"Praxis-IBAN {self.practice.iban} überein."
                        )
                    }
                )
