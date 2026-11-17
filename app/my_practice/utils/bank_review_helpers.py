"""Read-side helpers for the bank review page: which unmatched transactions already have an invoice."""

from collections import Counter

from ..models import BankTransaction, Client, ClientAlias, Invoice
from ..models.base import PracticeScope, scope_to_practice
from .bank_import import amounts_match


def fetch_invoice_maps(
    invoice_numbers: set[str], statuses: list[str], *, practice: PracticeScope
) -> dict[str, dict[str, Invoice]]:
    """Batch-fetch invoices by number and split them by status.

    Returns ``{status: {invoice_number: Invoice}}`` for each requested status.
    """
    result: dict[str, dict[str, Invoice]] = {status: {} for status in statuses}
    if invoice_numbers:
        invoices = scope_to_practice(Invoice.objects.all(), practice).filter(
            invoice_number__in=invoice_numbers, status__in=statuses
        )
        for invoice in invoices:
            if invoice.status in result:
                result[invoice.status][invoice.invoice_number] = invoice
    return result


def known_payer_names(*, practice: PracticeScope) -> set[str]:
    """Names that already resolve to a client: exact client names + existing aliases."""
    client_names = scope_to_practice(Client.objects.all(), practice).values_list(
        "full_name", flat=True
    )
    alias_names = scope_to_practice(
        ClientAlias.objects.all(), practice, "client__practice"
    ).values_list("alias_name", flat=True)
    return {n.lower().strip() for n in client_names} | {n.lower().strip() for n in alias_names}


def _invoice_for_amount(
    transaction: BankTransaction, invoices_by_number: dict[str, Invoice]
) -> Invoice | None:
    """The invoice carrying the transaction's invoice number, if its total equals the amount."""
    number = transaction.extracted_invoice_number
    invoice = invoices_by_number.get(number) if number else None
    if invoice and amounts_match(invoice.total, transaction.amount):
        return invoice
    return None


def _invoice_numbers(transactions: list[BankTransaction]) -> set[str]:
    return {t.extracted_invoice_number for t in transactions if t.extracted_invoice_number}


def annotate_review_rows(
    transactions: list[BankTransaction], *, practice: PracticeScope
) -> list[BankTransaction]:
    """Set what the review page shows per transaction, and return the same list.

    - ``matching_paid_invoice``: a paid invoice with the extracted number and amount
    - ``matching_unpaid_invoice``: a sent invoice with the extracted number and amount
    - ``payer_name_known``: the payer already resolves to a client or alias
    """
    maps = fetch_invoice_maps(_invoice_numbers(transactions), ["paid", "sent"], practice=practice)
    known_names = known_payer_names(practice=practice)
    for transaction in transactions:
        transaction.matching_paid_invoice = _invoice_for_amount(transaction, maps["paid"])
        transaction.matching_unpaid_invoice = _invoice_for_amount(transaction, maps["sent"])
        transaction.payer_name_known = bool(
            transaction.payer_name and transaction.payer_name.lower().strip() in known_names
        )
    return transactions


def paid_invoice_matches(
    transactions: list[BankTransaction], *, practice: PracticeScope
) -> list[tuple[BankTransaction, Invoice]]:
    """Transactions whose invoice number and amount match an already paid invoice."""
    paid = fetch_invoice_maps(_invoice_numbers(transactions), ["paid"], practice=practice)["paid"]
    pairs = []
    for transaction in transactions:
        invoice = _invoice_for_amount(transaction, paid)
        if invoice:
            pairs.append((transaction, invoice))
    return pairs


def review_page_stats(*, practice: PracticeScope) -> dict:
    """The counts and recent matches the review page shows beside the unmatched list.

    Only unprocessed transactions are counted. ``expense_count`` includes
    auto-detected and ignored expenses, so a negative amount stays reachable from
    the expense tab until it is processed.
    """
    Confidence = BankTransaction.Confidence
    all_rows = scope_to_practice(BankTransaction.objects.all(), practice)
    unprocessed = all_rows.filter(processed=False)
    return {
        "stats": dict(Counter(unprocessed.values_list("match_confidence", flat=True))),
        "expense_count": unprocessed.filter(
            match_confidence__in=[
                Confidence.UNMATCHED,
                Confidence.AUTO_EXPENSE,
                Confidence.IGNORED,
            ],
            amount__lt=0,
        ).count(),
        "withdrawal_count": unprocessed.filter(match_confidence=Confidence.AUTO_WITHDRAWAL).count(),
        "recently_matched": all_rows.filter(
            match_confidence__in=[Confidence.EXACT, Confidence.FUZZY, Confidence.MANUAL],
            matched_invoice__isnull=False,
        )
        .select_related("matched_invoice", "matched_invoice__client")
        .order_by("-imported_at")[:10],
    }
