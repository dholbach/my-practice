"""Recording a bank payment against invoices, remembering payer names as aliases, and bulk-ignoring transactions."""

from collections.abc import Sequence

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils.translation import gettext as _

from ..models import BankTransaction, ClientAlias, Invoice
from ..models.base import PracticeScope, scope_to_practice
from .bank_review_helpers import paid_invoice_matches


class InvoiceNotPayableError(Exception):
    """An invoice failed validation when it was marked as paid."""

    def __init__(self, invoice: Invoice, reasons: list[str]) -> None:
        self.invoice = invoice
        self.reasons = reasons
        super().__init__(f"{invoice.invoice_number}: {' '.join(reasons)}")


def record_payment(
    bank_transaction: BankTransaction,
    invoices: Sequence[Invoice],
    *,
    confidence: str,
    notes: str = "",
) -> None:
    """Mark ``invoices`` paid on the transaction's date and link the transaction to the first.

    All or nothing: a transaction recorded as matched while one of its invoices
    failed validation would vanish from review with that invoice still unpaid, so
    the first invoice that cannot be saved (a payment dated before the invoice, for
    one) raises InvoiceNotPayableError and nothing is written.
    """
    if not invoices:
        raise ValueError("record_payment needs at least one invoice")
    with db_transaction.atomic():
        for invoice in invoices:
            try:
                invoice.mark_paid(bank_transaction.transaction_date)
            except ValidationError as exc:
                raise InvoiceNotPayableError(invoice, exc.messages) from exc

        bank_transaction.matched_invoice = invoices[0]
        bank_transaction.match_confidence = confidence
        bank_transaction.processed = True
        if notes:
            bank_transaction.notes = notes
        bank_transaction.save()


def payer_needs_alias(bank_transaction: BankTransaction, invoice: Invoice) -> bool:
    """True if the payer is a name the invoice's client is not yet known by.

    Not for a transaction without a payer name, nor one whose payer is the client's
    own name or already an alias (case and surrounding spaces ignored).
    """
    payer = bank_transaction.payer_name
    client = invoice.client
    if not (payer and client.full_name):
        return False
    if payer.lower().strip() == client.full_name.lower().strip():
        return False
    return not ClientAlias.objects.filter(client=client, alias_name__iexact=payer).exists()


def create_payer_alias(
    bank_transaction: BankTransaction, invoice: Invoice, notes: str
) -> ClientAlias:
    """Remember the transaction's payer name as an alias of the invoice's client."""
    return ClientAlias.objects.create(
        client=invoice.client, alias_name=bank_transaction.payer_name, notes=notes
    )


def _unmatched(practice: PracticeScope):
    return scope_to_practice(BankTransaction.objects.all(), practice).filter(
        match_confidence=BankTransaction.Confidence.UNMATCHED, processed=False
    )


def ignore_already_paid(*, practice: PracticeScope) -> int:
    """Ignore and process the unmatched transactions whose invoice is already paid.

    Returns how many were ignored.
    """
    transactions = list(_unmatched(practice).select_related("matched_invoice"))
    pairs = paid_invoice_matches(transactions, practice=practice)
    for transaction, paid_invoice in pairs:
        transaction.match_confidence = BankTransaction.Confidence.IGNORED
        transaction.processed = True
        transaction.notes = _("Auto-ignored: invoice %(number)s already paid") % {
            "number": paid_invoice.invoice_number
        }
        transaction.save()
    return len(pairs)


def ignore_unmatched(*, practice: PracticeScope, expenses_only: bool) -> int:
    """Ignore every unmatched transaction, or only the outgoing ones. Returns how many.

    The rows stay unprocessed, so they remain on the expense tab for review.
    """
    unmatched = _unmatched(practice)
    if expenses_only:
        unmatched = unmatched.filter(amount__lt=0)
    return unmatched.update(match_confidence=BankTransaction.Confidence.IGNORED)
