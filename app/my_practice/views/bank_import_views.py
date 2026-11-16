"""
Bank statement import views.

Handles CSV upload, automatic matching, and manual review of unmatched transactions.
"""

from decimal import Decimal

from django.contrib import messages
from django.db import transaction as db_transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, ngettext, ngettext_lazy
from django.views.generic import FormView
from django.views.generic.edit import FormMixin

from ..import_forms import BankStatementUploadForm, TransactionMatchForm
from ..models import (
    BankTransaction,
    CompanyExpense,
    CompanyWithdrawal,
    ExpenseCategoryRule,
    Invoice,
)
from ..utils import BankStatementImporter, build_counterparty_key
from ..utils.bank_import import amounts_match
from ..utils.bank_matching import (
    InvoiceNotPayableError,
    create_payer_alias,
    payer_needs_alias,
    record_payment,
)
from ..utils.bank_review_helpers import annotate_review_rows, paid_invoice_matches
from .crud_mixins import PracticeScopedListView


class BankImportView(FormView):
    """
    Upload and process bank statement CSV files.

    Shows upload form, processes CSV, and displays import results.
    """

    template_name = "my_practice/bank_import.html"
    form_class = BankStatementUploadForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Show recent imports
        recent_transactions = (
            BankTransaction.objects.for_current_practice(self.request)
            .select_related("matched_invoice", "matched_invoice__client")
            .order_by("-imported_at")[:10]
        )
        context["recent_transactions"] = recent_transactions

        return context

    def form_valid(self, form):
        """Process uploaded CSV file"""
        csv_file = form.cleaned_data["csv_file"]
        skip_expenses = form.cleaned_data["skip_expenses"]

        # Import and process transactions
        importer = BankStatementImporter(csv_file, self.request.current_practice)
        results = importer.process(skip_negatives=skip_expenses)

        # Abort if CSV belongs to the wrong bank account
        if results.get("account_mismatch"):
            for error in results["errors"]:
                messages.error(self.request, error)
            return self.form_invalid(form)

        # Store results in session for review page
        self.request.session["import_results"] = {
            "total": results["total"],
            "matched": results["matched"],
            "unmatched": results["unmatched"],
            "needs_review": results["needs_review"],
            "ignored": results["ignored"],
            "errors": results["errors"],
        }

        msg_parts = [
            _("%(count)s automatically matched") % {"count": results["matched"]},
            _("%(count)s require manual review") % {"count": results["unmatched"]},
        ]
        if results["needs_review"] > 0:
            msg_parts.append(
                _("%(count)s expenses detected automatically") % {"count": results["needs_review"]}
            )
        msg_parts.append(_("%(count)s ignored") % {"count": results["ignored"]})
        messages.success(
            self.request,
            _("Import complete: %(details)s.") % {"details": ", ".join(msg_parts)},
        )

        # Redirect to review page
        return redirect("bank_review")


class BankReviewView(FormMixin, PracticeScopedListView):
    """
    Review and manually match unmatched transactions.

    Shows unmatched transactions with form to assign invoices.
    """

    model = BankTransaction
    template_name = "my_practice/bank_review.html"
    context_object_name = "transactions"
    paginate_by = 20
    form_class = TransactionMatchForm

    def get_queryset(self):
        """Get unmatched transactions for current practice"""
        transactions = (
            super()
            .get_queryset()
            .filter(
                match_confidence=BankTransaction.Confidence.UNMATCHED,
                processed=False,
            )
            .select_related("matched_invoice")
            .order_by("-transaction_date")
        )

        return annotate_review_rows(list(transactions), practice=self.request.current_practice)

    def get_form_kwargs(self):
        """Add practice to form kwargs"""
        kwargs = super().get_form_kwargs()
        kwargs["practice"] = self.request.current_practice
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get import results from session
        import_results = self.request.session.pop("import_results", None)
        context["import_results"] = import_results

        # Get statistics - only unprocessed transactions
        stats = (
            BankTransaction.objects.for_current_practice(self.request)
            .filter(
                processed=False,
            )
            .values("match_confidence")
        )

        confidence_counts: dict[str, int] = {}
        for stat in stats:
            conf = stat["match_confidence"]
            confidence_counts[conf] = confidence_counts.get(conf, 0) + 1

        context["stats"] = confidence_counts

        # Count negative amounts (expenses) for review - includes auto-expense
        expense_count = (
            BankTransaction.objects.for_current_practice(self.request)
            .filter(
                match_confidence__in=[
                    BankTransaction.Confidence.UNMATCHED,
                    BankTransaction.Confidence.AUTO_EXPENSE,
                    BankTransaction.Confidence.IGNORED,
                ],
                processed=False,
                amount__lt=0,
            )
            .count()
        )
        context["expense_count"] = expense_count

        # Count auto-withdrawal transactions for review
        withdrawal_count = (
            BankTransaction.objects.for_current_practice(self.request)
            .filter(
                match_confidence=BankTransaction.Confidence.AUTO_WITHDRAWAL,
                processed=False,
            )
            .count()
        )
        context["withdrawal_count"] = withdrawal_count

        # Get recently matched transactions for reference (last 10)
        recently_matched = (
            BankTransaction.objects.for_current_practice(self.request)
            .filter(
                match_confidence__in=[
                    BankTransaction.Confidence.EXACT,
                    BankTransaction.Confidence.FUZZY,
                    BankTransaction.Confidence.MANUAL,
                ],
                matched_invoice__isnull=False,
            )
            .select_related("matched_invoice", "matched_invoice__client")
            .order_by("-imported_at")[:10]
        )
        context["recently_matched"] = recently_matched

        # Count transactions with already-paid invoices (for bulk ignore button).
        # Use self.object_list (the full, unpaginated queryset from get_queryset()),
        # not context["transactions"] (the paginated page) — otherwise the banner and
        # count are wrong on any page beyond the first, and don't match what
        # _handle_bulk_ignore_paid actually acts on.
        paid_invoice_count = 0
        for trans in self.object_list:
            if hasattr(trans, "matching_paid_invoice") and trans.matching_paid_invoice:
                paid_invoice_count += 1
        context["paid_invoice_count"] = paid_invoice_count

        return context

    def post(self, request, *args, **kwargs):
        """Dispatch to bulk or single-transaction action handlers."""
        action = request.POST.get("action")

        # Bulk actions — no transaction_id needed
        if action == "bulk_ignore_paid":
            return self._handle_bulk_ignore_paid(request)
        if action == "ignore_all_expenses":
            return self._handle_ignore_all_expenses(request)
        if action == "ignore_all_unmatched":
            return self._handle_ignore_all_unmatched(request)

        # Single-transaction actions
        transaction_id = request.POST.get("transaction_id")
        if not transaction_id:
            messages.error(request, _("No transaction selected."))
            return redirect("bank_review")

        transaction = get_object_or_404(
            BankTransaction.objects.for_current_practice(request),
            id=transaction_id,
        )
        redirect_url = self._next_redirect_url(request, transaction)

        if action == "ignore":
            return self._handle_ignore(request, transaction, redirect_url)
        if action == "confirm_paid":
            return self._handle_confirm_paid(request, transaction, redirect_url)
        if action == "auto_match":
            return self._handle_auto_match(request, transaction, redirect_url)
        if action == "match":
            return self._handle_match(request, transaction, redirect_url)

        return redirect(redirect_url)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _next_redirect_url(self, request, exclude_transaction) -> str:
        """Build review URL anchored to the next unmatched transaction."""
        next_transaction = (
            BankTransaction.objects.for_current_practice(request)
            .filter(
                processed=False,
                match_confidence=BankTransaction.Confidence.UNMATCHED,
            )
            .exclude(id=exclude_transaction.id)
            .order_by("transaction_date")
            .first()
        )
        url = reverse("bank_review")
        if next_transaction:
            url += f"#trans-{next_transaction.id}"
        return url

    # ── bulk action handlers ──────────────────────────────────────────────────

    def _handle_bulk_ignore_paid(self, request):
        transactions = list(
            BankTransaction.objects.for_current_practice(request)
            .filter(
                match_confidence=BankTransaction.Confidence.UNMATCHED,
                processed=False,
            )
            .select_related("matched_invoice")
        )

        ignored_count = 0
        for trans, paid_invoice in paid_invoice_matches(
            transactions, practice=request.current_practice
        ):
            trans.match_confidence = BankTransaction.Confidence.IGNORED
            trans.processed = True
            trans.notes = _("Auto-ignored: invoice %(number)s already paid") % {
                "number": paid_invoice.invoice_number
            }
            trans.save()
            ignored_count += 1

        if ignored_count > 0:
            messages.success(
                request,
                ngettext(
                    "✅ %(count)s transaction with already-paid invoice ignored.",
                    "✅ %(count)s transactions with already-paid invoices ignored.",
                    ignored_count,
                )
                % {"count": ignored_count},
            )
        else:
            messages.info(request, _("No matching transactions to ignore."))
        return redirect("bank_review")

    def _handle_ignore_all_expenses(self, request):
        updated = (
            BankTransaction.objects.for_current_practice(request)
            .filter(
                match_confidence=BankTransaction.Confidence.UNMATCHED,
                processed=False,
                amount__lt=0,
            )
            .update(match_confidence=BankTransaction.Confidence.IGNORED)
        )
        messages.success(
            request,
            ngettext(
                "%(count)s expense ignored.",
                "%(count)s expenses ignored.",
                updated,
            )
            % {"count": updated},
        )
        return redirect("bank_review")

    def _handle_ignore_all_unmatched(self, request):
        updated = (
            BankTransaction.objects.for_current_practice(request)
            .filter(
                match_confidence=BankTransaction.Confidence.UNMATCHED,
                processed=False,
            )
            .update(match_confidence=BankTransaction.Confidence.IGNORED)
        )
        messages.success(
            request,
            ngettext(
                "%(count)s transaction ignored.",
                "%(count)s transactions ignored.",
                updated,
            )
            % {"count": updated},
        )
        return redirect("bank_review")

    # ── single-transaction action handlers ───────────────────────────────────

    def _handle_ignore(self, request, transaction, redirect_url):
        transaction.match_confidence = BankTransaction.Confidence.IGNORED
        transaction.processed = True
        transaction.save()
        messages.success(request, _("Transaction ignored."))
        return redirect(redirect_url)

    def _handle_confirm_paid(self, request, transaction, redirect_url):
        invoice_id = request.POST.get("suggested_invoice_id")
        invoice = None

        if invoice_id:
            invoice = Invoice.objects.filter(
                id=invoice_id,
                practice=request.current_practice,
            ).first()

            if invoice:
                transaction.matched_invoice = invoice
                self._maybe_create_alias(request, transaction, invoice, "confirm")

        transaction.match_confidence = BankTransaction.Confidence.MANUAL
        transaction.processed = True
        transaction.save()

        if invoice_id and invoice:
            messages.success(
                request,
                _("Transaction linked to %(number)s (already paid).")
                % {"number": invoice.invoice_number},
            )
        else:
            messages.success(request, _("Transaction confirmed (invoice already paid)."))
        return redirect(redirect_url)

    def _handle_auto_match(self, request, transaction, redirect_url):
        invoice_id = request.POST.get("suggested_invoice_id")
        if not invoice_id:
            messages.error(request, _("No invoice specified."))
            return redirect(redirect_url)

        invoice = get_object_or_404(
            Invoice,
            id=invoice_id,
            practice=request.current_practice,
            status=Invoice.Status.SENT,
        )

        # The suggestion arrives as a hidden form field, so re-apply the
        # importer's exact-amount rule rather than trusting it.
        if not amounts_match(invoice.calculate_total(), transaction.amount):
            messages.error(
                request,
                _("The amount does not match invoice %(number)s.")
                % {"number": invoice.invoice_number},
            )
            return redirect(redirect_url)

        try:
            record_payment(transaction, [invoice], confidence=BankTransaction.Confidence.EXACT)
        except InvoiceNotPayableError as exc:
            return self._refuse_unpayable(request, exc, redirect_url)

        messages.success(
            request,
            _("Transaction automatically linked to %(number)s and marked as paid.")
            % {"number": invoice.invoice_number},
        )
        return redirect(redirect_url)

    @staticmethod
    def _refuse_unpayable(request, error: InvoiceNotPayableError, redirect_url):
        messages.error(
            request,
            _("Invoice %(number)s could not be marked as paid: %(error)s")
            % {"number": error.invoice.invoice_number, "error": " ".join(error.reasons)},
        )
        return redirect(redirect_url)

    def _handle_match(self, request, transaction, redirect_url):

        form = self.get_form()
        if not form.is_valid():
            messages.error(request, _("Error processing form."))
            return redirect(redirect_url)

        invoices = form.cleaned_data["invoice"]
        if not invoices:
            messages.error(request, _("Please select at least one invoice."))
            return redirect(redirect_url)

        notes = form.cleaned_data.get("notes", "")
        create_alias = request.POST.get("create_alias") == "1"
        invoice_list = list(invoices)
        first_invoice = invoice_list[0] if invoice_list else None

        # Stored notes are written in the signed-in user's language, like any message.
        if len(invoice_list) > 1:
            invoice_numbers = ", ".join(inv.invoice_number for inv in invoice_list)
            bulk_note = _("Combined payment for: %(numbers)s") % {"numbers": invoice_numbers}
            notes = f"{bulk_note}\n{notes}" if notes else bulk_note

        try:
            record_payment(
                transaction, invoice_list, confidence=BankTransaction.Confidence.MANUAL, notes=notes
            )
        except InvoiceNotPayableError as exc:
            return self._refuse_unpayable(request, exc, redirect_url)

        if create_alias and transaction.payer_name and first_invoice:
            self._maybe_create_alias(request, transaction, first_invoice, "import")

        if len(invoice_list) == 1 and first_invoice:
            messages.success(
                request,
                _("Payment successfully assigned to invoice %(number)s.")
                % {"number": first_invoice.invoice_number},
            )
        else:
            invoice_numbers = ", ".join(inv.invoice_number for inv in invoice_list)
            messages.success(
                request,
                _("Payment successfully assigned to %(count)s invoices: %(numbers)s")
                % {"count": len(invoice_list), "numbers": invoice_numbers},
            )
        return redirect(redirect_url)

    def _maybe_create_alias(self, request, transaction, invoice, context: str) -> None:
        """Create a ClientAlias for the transaction's payer name if it differs from the client."""
        if not payer_needs_alias(transaction, invoice):
            return

        if context == "confirm":
            notes = _("Created automatically on confirming the payment of %(date)s") % {
                "date": date_format(transaction.transaction_date, "SHORT_DATE_FORMAT")
            }
            messages.info(
                request,
                _("📌 Alias '%(name)s' for %(code)s saved.")
                % {"name": transaction.payer_name, "code": invoice.client.client_code},
            )
        else:
            notes = _("Created during the bank import of %(date)s") % {
                "date": date_format(transaction.transaction_date, "SHORT_DATE_FORMAT")
            }
            messages.success(
                request,
                _("Alias '%(name)s' for %(code)s saved.")
                % {"name": transaction.payer_name, "code": invoice.client.client_code},
            )

        create_payer_alias(transaction, invoice, notes)


class BankFinancialReviewView(PracticeScopedListView):
    """
    Review outgoing bank transactions and group them into a financial record.

    Shared by the expense and withdrawal review pages, which differ only in
    which transactions they list, which record they create and how it is
    labelled. Each subclass sets the class attributes below; the grouping and
    ignoring flow — including cleanup of per-transaction records the importer
    auto-created and which the manual decision now supersedes — is the same.
    """

    model = BankTransaction
    context_object_name = "transactions"
    paginate_by = 50

    # The record type a group of transactions becomes, and the BankTransaction
    # field that links a transaction to one of them.
    record_model: type[CompanyExpense] | type[CompanyWithdrawal]
    link_field: str
    redirect_name: str
    page_title: str
    default_category: str
    # Data strings, not UI: written into the record's description / the
    # transaction's notes, so they are deliberately not passed through i18n.
    record_label: str
    grouped_note_prefix: str
    group_success_message: str  # ngettext_lazy with %(count)s and %(amount)s

    def get_queryset(self):
        return super().get_queryset().filter(**self.queryset_filter()).order_by("-transaction_date")

    def queryset_filter(self) -> dict:
        """Filter selecting the transactions this page reviews."""
        raise NotImplementedError

    def total_amount(self, transactions: list[BankTransaction]) -> Decimal:
        """Headline total for the stats card."""
        return sum((abs(trans.amount) for trans in transactions), Decimal("0"))

    def record_fields(self, request) -> dict:
        """Extra fields for the created record, read from the grouping form."""
        return {}

    def after_group(self, request, transactions, category: str) -> None:
        """Hook run after the grouped record is created and linked."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title

        transactions = list(self.get_queryset())
        context["stats"] = {
            "unmatched": len(transactions),
            "total_amount": self.total_amount(transactions),
        }
        context["category_choices"] = self.record_model.CATEGORY_CHOICES
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "group":
            return self._handle_group(request)
        if action == "ignore":
            return self._handle_ignore(request)
        return redirect(self.redirect_name)

    def _selected_transactions(self, request):
        """
        The selected transactions this page lists, or None with an error set.

        Limited to the page's own queryset, not just the practice: a posted id
        for an already-matched or manually linked transaction must not be
        regrouped, which would also delete the record it is linked to.
        """
        transaction_ids = request.POST.getlist("transactions")
        if not transaction_ids:
            messages.error(request, _("Please select at least one transaction."))
            return None
        return BankTransaction.objects.for_current_practice(request).filter(
            id__in=transaction_ids, **self.queryset_filter()
        )

    def _orphan_record_ids(self, transactions) -> list[int]:
        """Records the selected transactions were linked to before this action."""
        link_id = f"{self.link_field}_id"
        return [getattr(trans, link_id) for trans in transactions if getattr(trans, link_id)]

    def _delete_orphans(self, orphan_ids: list[int]) -> None:
        """
        Delete the superseded per-transaction records that nothing else uses.

        Call after the selected transactions have been re-linked or unlinked.
        The importer reuses an existing record with the same date, amount and
        description, which may be one the owner entered by hand, so a record
        that still has receipts or other linked transactions is kept.
        """
        orphans = self.record_model.objects.filter(
            id__in=orphan_ids, bank_transactions__isnull=True
        )
        if self.record_model is CompanyExpense:
            orphans = orphans.filter(receipts__isnull=True)
        orphans.delete()

    def _handle_group(self, request):
        transactions = self._selected_transactions(request)
        if transactions is None or not transactions.exists():
            if transactions is not None:
                messages.error(request, _("No transactions found."))
            return redirect(self.redirect_name)

        category = request.POST.get("category", self.default_category)
        if category not in dict(self.record_model.CATEGORY_CHOICES):
            messages.error(request, _("Invalid category."))
            return redirect(self.redirect_name)
        description = request.POST.get("description", "")
        total_amount = sum(abs(trans.amount) for trans in transactions)
        dates = [trans.transaction_date for trans in transactions]
        min_date, max_date = min(dates), max(dates)

        if not description:
            count = transactions.count()
            if count == 1:
                description = transactions.first().reference
            else:
                label = dict(self.record_model.CATEGORY_CHOICES).get(category, self.record_label)
                description = f"{count}x {label} ({min_date.strftime('%d.%m.%Y')} – {max_date.strftime('%d.%m.%Y')})"

        # Collected before the grouped record exists so it can never be in the list.
        orphan_ids = self._orphan_record_ids(transactions)

        # Evaluated now: the loop below takes every row out of the page's
        # queryset, which would leave a lazy queryset empty.
        transactions = list(transactions)
        with db_transaction.atomic():
            record = self.record_model.objects.create(
                practice=request.current_practice,
                date=max_date,
                amount=total_amount,
                description=description,
                category=category,
                **self.record_fields(request),
            )

            notes = f"{self.grouped_note_prefix}: {record} (ID: {record.id})"
            for trans in transactions:
                trans.match_confidence = BankTransaction.Confidence.IGNORED
                setattr(trans, self.link_field, record)
                trans.notes = notes
                trans.processed = True
                trans.save()

            self.after_group(request, transactions, category)
            self._delete_orphans(orphan_ids)

        messages.success(
            request,
            self.group_success_message
            % {"count": len(transactions), "amount": f"{total_amount:.2f}"},
        )
        return redirect(self.redirect_name)

    def _handle_ignore(self, request):
        transactions = self._selected_transactions(request)
        if transactions is None:
            return redirect(self.redirect_name)

        # Ignoring says "this was never a record": drop what the importer
        # auto-created for it, otherwise the amount stays in the books.
        orphan_ids = self._orphan_record_ids(transactions)
        with db_transaction.atomic():
            count = transactions.update(
                match_confidence=BankTransaction.Confidence.IGNORED,
                notes="Manuell ignoriert",
                processed=True,
                **{self.link_field: None},
            )
            self._delete_orphans(orphan_ids)

        messages.success(
            request,
            ngettext(
                "%(count)s transaction ignored.",
                "%(count)s transactions ignored.",
                count,
            )
            % {"count": count},
        )
        return redirect(self.redirect_name)


class BankExpenseReviewView(BankFinancialReviewView):
    """Group unmatched negative transactions into CompanyExpenses."""

    template_name = "my_practice/bank_expense_review.html"
    record_model = CompanyExpense
    link_field = "linked_expense"
    redirect_name = "bank_expense_review"
    page_title = gettext_lazy("Bank Import - Assign Expenses")
    default_category = "other"
    record_label = "Ausgabe"
    grouped_note_prefix = "Zu Ausgabe zusammengefasst"
    group_success_message = ngettext_lazy(
        "%(count)s transaction successfully grouped into expense: %(amount)s €",
        "%(count)s transactions successfully grouped into expense: %(amount)s €",
        "count",
    )

    def queryset_filter(self) -> dict:
        return {
            "amount__lt": 0,
            "match_confidence__in": [
                BankTransaction.Confidence.UNMATCHED,
                BankTransaction.Confidence.IGNORED,
                BankTransaction.Confidence.AUTO_EXPENSE,
            ],
            "processed": False,
        }

    def total_amount(self, transactions):
        # Shown signed: every listed amount is an outflow and the page renders
        # it as such.
        return sum((trans.amount for trans in transactions), Decimal("0"))

    def record_fields(self, request) -> dict:
        return {
            "has_invoice": request.POST.get("has_invoice") == "on",
            "is_tax_deductible": request.POST.get("is_tax_deductible") == "on",
        }

    def after_group(self, request, transactions, category: str) -> None:
        # Learn a category rule per distinct counterparty in the selection so
        # future imports from the same payer are pre-categorized.
        learned_keys = set()
        for trans in transactions:
            match_key = build_counterparty_key(trans.payer_iban, trans.payer_name)
            if match_key and match_key not in learned_keys:
                learned_keys.add(match_key)
                ExpenseCategoryRule.objects.update_or_create(
                    practice=request.current_practice,
                    match_key=match_key,
                    defaults={"category": category},
                )


class BankWithdrawalReviewView(BankFinancialReviewView):
    """Confirm auto-created withdrawal transactions and group them into CompanyWithdrawals."""

    template_name = "my_practice/bank_withdrawal_review.html"
    record_model = CompanyWithdrawal
    link_field = "linked_withdrawal"
    redirect_name = "bank_withdrawal_review"
    page_title = gettext_lazy("Bank Import - Assign Withdrawals")
    default_category = "salary"
    record_label = "Entnahme"
    grouped_note_prefix = "Zu Entnahme zusammengefasst"
    group_success_message = ngettext_lazy(
        "%(count)s transaction successfully grouped into withdrawal: %(amount)s €",
        "%(count)s transactions successfully grouped into withdrawal: %(amount)s €",
        "count",
    )

    def queryset_filter(self) -> dict:
        return {"match_confidence": BankTransaction.Confidence.AUTO_WITHDRAWAL, "processed": False}
