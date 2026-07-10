"""
Bank statement import views.

Handles CSV upload, automatic matching, and manual review of unmatched transactions.
"""

from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.generic import FormView, ListView
from django.views.generic.edit import FormMixin

from ..import_forms import BankStatementUploadForm, TransactionMatchForm
from ..models import (
    BankTransaction,
    Client,
    ClientAlias,
    CompanyExpense,
    CompanyWithdrawal,
    Invoice,
)
from ..utils import BankStatementImporter


class BankImportView(FormView):
    """
    Upload and process bank statement CSV files.

    Shows upload form, processes CSV, and displays import results.
    """

    template_name = "my_practice/bank_import.html"
    form_class = BankStatementUploadForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Bank Statement Import"

        # Show recent imports
        recent_transactions = (
            BankTransaction.objects.filter(practice=self.request.current_practice)
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


class BankReviewView(FormMixin, ListView):
    """
    Review and manually match unmatched transactions.

    Shows unmatched transactions with form to assign invoices.
    """

    template_name = "my_practice/bank_review.html"
    context_object_name = "transactions"
    paginate_by = 20
    form_class = TransactionMatchForm

    def get_queryset(self):
        """Get unmatched transactions for current practice"""
        transactions = (
            BankTransaction.objects.filter(
                practice=self.request.current_practice,
                match_confidence="unmatched",
                processed=False,
            )
            .select_related("matched_invoice")
            .order_by("-transaction_date")
        )

        transactions_list = list(transactions)

        invoice_numbers = {
            t.extracted_invoice_number for t in transactions_list if t.extracted_invoice_number
        }
        maps = self._fetch_invoice_maps(
            self.request.current_practice, invoice_numbers, ["paid", "sent"]
        )
        paid_map = maps["paid"]
        sent_map = maps["sent"]
        known_names = self._known_payer_names(self.request.current_practice)

        for trans in transactions_list:
            trans.matching_paid_invoice = None
            trans.matching_unpaid_invoice = None
            num = trans.extracted_invoice_number
            if num:
                paid = paid_map.get(num)
                if paid and abs(paid.total - trans.amount) < Decimal("0.01"):
                    trans.matching_paid_invoice = paid
                sent = sent_map.get(num)
                if sent and abs(sent.total - trans.amount) < Decimal("0.01"):
                    trans.matching_unpaid_invoice = sent
            trans.payer_name_known = bool(
                trans.payer_name and trans.payer_name.lower().strip() in known_names
            )

        return transactions_list

    @staticmethod
    def _known_payer_names(practice) -> set[str]:
        """Names that already resolve to a client: exact client names + existing aliases."""
        client_names = Client.objects.filter(practice=practice).values_list("full_name", flat=True)
        alias_names = ClientAlias.objects.filter(client__practice=practice).values_list(
            "alias_name", flat=True
        )
        return {n.lower().strip() for n in client_names} | {n.lower().strip() for n in alias_names}

    def get_form_kwargs(self):
        """Add practice to form kwargs"""
        kwargs = super().get_form_kwargs()
        kwargs["practice"] = self.request.current_practice
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Bank Import - Manuelle Zuordnung"

        # Get import results from session
        import_results = self.request.session.pop("import_results", None)
        context["import_results"] = import_results

        # Get statistics - only unprocessed transactions
        stats = BankTransaction.objects.filter(
            practice=self.request.current_practice,
            processed=False,
        ).values("match_confidence")

        confidence_counts: dict[str, int] = {}
        for stat in stats:
            conf = stat["match_confidence"]
            confidence_counts[conf] = confidence_counts.get(conf, 0) + 1

        context["stats"] = confidence_counts

        # Count negative amounts (expenses) for review - includes auto-expense
        expense_count = BankTransaction.objects.filter(
            practice=self.request.current_practice,
            match_confidence__in=["unmatched", "auto-expense", "ignored"],
            processed=False,
            amount__lt=0,
        ).count()
        context["expense_count"] = expense_count

        # Count auto-withdrawal transactions for review
        withdrawal_count = BankTransaction.objects.filter(
            practice=self.request.current_practice,
            match_confidence="auto-withdrawal",
            processed=False,
        ).count()
        context["withdrawal_count"] = withdrawal_count

        # Get recently matched transactions for reference (last 10)
        recently_matched = (
            BankTransaction.objects.filter(
                practice=self.request.current_practice,
                match_confidence__in=["exact", "fuzzy", "manual"],
                matched_invoice__isnull=False,
            )
            .select_related("matched_invoice", "matched_invoice__client")
            .order_by("-imported_at")[:10]
        )
        context["recently_matched"] = recently_matched

        # Count transactions with already-paid invoices (for bulk ignore button)

        paid_invoice_count = 0
        transactions_list = context.get("transactions", [])
        for trans in transactions_list:
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
            BankTransaction,
            id=transaction_id,
            practice=request.current_practice,
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

    @staticmethod
    def _fetch_invoice_maps(
        practice, invoice_numbers: set[str], statuses: list[str]
    ) -> dict[str, dict[str, Invoice]]:
        """
        Batch-fetch invoices by number and split by status.

        Returns {status_string: {invoice_number: Invoice}} for each requested
        status. Replaces the duplicated per-status query loops in get_queryset
        and _handle_bulk_ignore_paid.
        """
        result: dict[str, dict[str, Invoice]] = {s: {} for s in statuses}
        if invoice_numbers:
            for inv in Invoice.objects.filter(
                practice=practice,
                invoice_number__in=invoice_numbers,
                status__in=statuses,
            ):
                if inv.status in result:
                    result[inv.status][inv.invoice_number] = inv
        return result

    def _next_redirect_url(self, request, exclude_transaction) -> str:
        """Build review URL anchored to the next unmatched transaction."""
        next_transaction = (
            BankTransaction.objects.filter(
                practice=request.current_practice,
                processed=False,
                match_confidence="unmatched",
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
            BankTransaction.objects.filter(
                practice=request.current_practice,
                match_confidence="unmatched",
                processed=False,
            ).select_related("matched_invoice")
        )

        invoice_numbers = {
            t.extracted_invoice_number for t in transactions if t.extracted_invoice_number
        }
        paid_map = self._fetch_invoice_maps(request.current_practice, invoice_numbers, ["paid"])[
            "paid"
        ]

        ignored_count = 0
        for trans in transactions:
            if not trans.extracted_invoice_number:
                continue
            paid_invoice = paid_map.get(trans.extracted_invoice_number)
            if paid_invoice and abs(paid_invoice.total - trans.amount) < Decimal("0.01"):
                trans.match_confidence = "ignored"
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
        updated = BankTransaction.objects.filter(
            practice=request.current_practice,
            match_confidence="unmatched",
            processed=False,
            amount__lt=0,
        ).update(match_confidence="ignored")
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
        updated = BankTransaction.objects.filter(
            practice=request.current_practice,
            match_confidence="unmatched",
            processed=False,
        ).update(match_confidence="ignored")
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
        transaction.match_confidence = "ignored"
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

        transaction.match_confidence = "manual"
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
            status="sent",
        )

        transaction.matched_invoice = invoice
        transaction.match_confidence = "exact"
        transaction.save()

        invoice.status = "paid"
        invoice.paid_date = transaction.transaction_date
        invoice.save()

        messages.success(
            request,
            _("Transaction automatically linked to %(number)s and marked as paid.")
            % {"number": invoice.invoice_number},
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

        if len(invoice_list) > 1:
            invoice_numbers = ", ".join(inv.invoice_number for inv in invoice_list)
            bulk_note = f"Sammelzahlung für: {invoice_numbers}"
            notes = f"{bulk_note}\n{notes}" if notes else bulk_note

        transaction.matched_invoice = first_invoice
        transaction.match_confidence = "manual"
        transaction.processed = True
        if notes:
            transaction.notes = notes
        transaction.save()

        if create_alias and transaction.payer_name and first_invoice:
            self._maybe_create_alias(request, transaction, first_invoice, "import")

        for inv in invoice_list:
            inv.status = "paid"
            inv.paid_date = transaction.transaction_date
            inv.save()

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
        if not (transaction.payer_name and invoice.client.full_name):
            return
        if transaction.payer_name.lower().strip() == invoice.client.full_name.lower().strip():
            return
        if ClientAlias.objects.filter(
            client=invoice.client,
            alias_name__iexact=transaction.payer_name,
        ).exists():
            return

        if context == "confirm":
            notes = f"Auto-erstellt beim Bestätigen am {transaction.transaction_date}"
            messages.info(
                request,
                _("📌 Alias '%(name)s' for %(code)s saved.")
                % {"name": transaction.payer_name, "code": invoice.client.client_code},
            )
        else:
            notes = f"Erstellt beim Bank Import am {transaction.transaction_date}"
            messages.success(
                request,
                _("Alias '%(name)s' for %(code)s saved.")
                % {"name": transaction.payer_name, "code": invoice.client.client_code},
            )

        ClientAlias.objects.create(
            client=invoice.client,
            alias_name=transaction.payer_name,
            notes=notes,
        )


def bank_transaction_detail(request, pk):
    """Detail view for a single bank transaction"""
    transaction = get_object_or_404(
        BankTransaction,
        pk=pk,
        practice=request.current_practice,
    )

    context = {
        "transaction": transaction,
        "page_title": f"Transaktion vom {transaction.transaction_date}",
    }

    return render(request, "my_practice/bank_transaction_detail.html", context)


class BankExpenseReviewView(ListView):
    """
    Review and group negative bank transactions into expenses.

    Shows unmatched negative transactions with form to group them into CompanyExpenses.
    """

    template_name = "my_practice/bank_expense_review.html"
    context_object_name = "transactions"
    paginate_by = 50

    def get_queryset(self):
        """Get unmatched/ignored/auto-created negative transactions (potential expenses)"""
        return BankTransaction.objects.filter(
            practice=self.request.current_practice,
            amount__lt=0,  # Negative amounts
            match_confidence__in=["unmatched", "ignored", "auto-expense"],
            processed=False,
        ).order_by("-transaction_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Bank Import - Ausgaben zuordnen"

        qs = self.get_queryset()
        transactions = list(qs)
        context["stats"] = {
            "unmatched": len(transactions),
            "total_amount": sum(trans.amount for trans in transactions),
        }
        return context

    def post(self, request, *args, **kwargs):
        """Handle expense grouping"""
        action = request.POST.get("action")

        if action == "group":
            # Get selected transaction IDs
            transaction_ids = request.POST.getlist("transactions")
            if not transaction_ids:
                messages.error(request, _("Please select at least one transaction."))
                return redirect("bank_expense_review")

            transactions = BankTransaction.objects.filter(
                id__in=transaction_ids,
                practice=request.current_practice,
            )

            if not transactions.exists():
                messages.error(request, _("No transactions found."))
                return redirect("bank_expense_review")

            # Get form data
            category = request.POST.get("category", "other")
            description = request.POST.get("description", "")
            has_invoice = request.POST.get("has_invoice") == "on"
            is_tax_deductible = request.POST.get("is_tax_deductible") == "on"

            # Calculate total amount (absolute value)
            total_amount = sum(abs(trans.amount) for trans in transactions)

            # Get date range for description
            dates = [trans.transaction_date for trans in transactions]
            min_date = min(dates)
            max_date = max(dates)

            # Generate description if not provided
            if not description:
                count = len(transaction_ids)
                if count == 1:
                    first_trans = transactions.first()
                    description = first_trans.reference if first_trans else ""
                else:
                    description = f"{count}x {dict(CompanyExpense.CATEGORY_CHOICES).get(category, 'Ausgabe')} ({min_date.strftime('%d.%m.%Y')} - {max_date.strftime('%d.%m.%Y')})"

            # Delete any per-transaction auto-created expenses being superseded
            orphan_expense_ids = [
                trans.linked_expense_id
                for trans in transactions
                if trans.linked_expense_id is not None
            ]

            # Create CompanyExpense
            expense = CompanyExpense.objects.create(
                practice=request.current_practice,
                date=max_date,  # Use most recent date
                amount=total_amount,
                description=description,
                category=category,
                has_invoice=has_invoice,
                is_tax_deductible=is_tax_deductible,
            )

            # Mark transactions as processed and link to grouped expense
            transaction_notes = f"Zu Ausgabe zusammengefasst: {expense} (ID: {expense.id})"
            for trans in transactions:
                trans.match_confidence = "ignored"
                trans.linked_expense = expense
                trans.notes = transaction_notes
                trans.processed = True
                trans.save()

            # Clean up orphaned per-transaction auto-created expenses
            if orphan_expense_ids:
                CompanyExpense.objects.filter(id__in=orphan_expense_ids).delete()

            # Success message
            messages.success(
                request,
                ngettext(
                    "%(count)s transaction successfully grouped into expense: %(amount)s €",
                    "%(count)s transactions successfully grouped into expense: %(amount)s €",
                    len(transaction_ids),
                )
                % {"count": len(transaction_ids), "amount": f"{total_amount:.2f}"},
            )
            return redirect("bank_expense_review")

        elif action == "ignore":
            # Mark selected transactions as ignored
            transaction_ids = request.POST.getlist("transactions")
            if not transaction_ids:
                messages.error(request, _("Please select at least one transaction."))
                return redirect("bank_expense_review")

            count = BankTransaction.objects.filter(
                id__in=transaction_ids,
                practice=request.current_practice,
            ).update(
                match_confidence="ignored",
                notes="Manuell ignoriert",
                processed=True,
            )

            messages.success(
                request,
                ngettext(
                    "%(count)s transaction ignored.",
                    "%(count)s transactions ignored.",
                    count,
                )
                % {"count": count},
            )
            return redirect("bank_expense_review")

        return redirect("bank_expense_review")


class BankWithdrawalReviewView(ListView):
    """
    Review and group auto-created withdrawal transactions.

    Shows auto-withdrawal transactions for confirmation and grouping into CompanyWithdrawals.
    """

    template_name = "my_practice/bank_withdrawal_review.html"
    context_object_name = "transactions"
    paginate_by = 50

    def get_queryset(self):
        """Get auto-created withdrawal transactions pending review"""
        return BankTransaction.objects.filter(
            practice=self.request.current_practice,
            match_confidence="auto-withdrawal",
            processed=False,
        ).order_by("-transaction_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Bank Import - Entnahmen zuordnen"

        qs = self.get_queryset()
        context["stats"] = {
            "unmatched": qs.count(),
            "total_amount": sum(abs(trans.amount) for trans in qs),
        }
        context["category_choices"] = CompanyWithdrawal.CATEGORY_CHOICES
        return context

    def post(self, request, *args, **kwargs):
        """Handle withdrawal grouping and ignoring"""
        action = request.POST.get("action")

        if action == "group":
            transaction_ids = request.POST.getlist("transactions")
            if not transaction_ids:
                messages.error(request, _("Please select at least one transaction."))
                return redirect("bank_withdrawal_review")

            transactions = BankTransaction.objects.filter(
                id__in=transaction_ids,
                practice=request.current_practice,
            )

            if not transactions.exists():
                messages.error(request, _("No transactions found."))
                return redirect("bank_withdrawal_review")

            category = request.POST.get("category", "salary")
            description = request.POST.get("description", "")

            total_amount = sum(abs(trans.amount) for trans in transactions)
            dates = [trans.transaction_date for trans in transactions]
            min_date = min(dates)
            max_date = max(dates)

            if not description:
                count = len(transaction_ids)
                if count == 1:
                    first_trans = transactions.first()
                    description = first_trans.reference if first_trans else ""
                else:
                    description = (
                        f"{count}x {dict(CompanyWithdrawal.CATEGORY_CHOICES).get(category, 'Entnahme')}"
                        f" ({min_date.strftime('%d.%m.%Y')} – {max_date.strftime('%d.%m.%Y')})"
                    )

            # Collect orphaned auto-created withdrawals to delete after creating the grouped one
            orphan_ids = [
                trans.linked_withdrawal_id
                for trans in transactions
                if trans.linked_withdrawal_id is not None
            ]

            withdrawal = CompanyWithdrawal.objects.create(
                practice=request.current_practice,
                date=max_date,
                amount=total_amount,
                description=description,
                category=category,
            )

            notes = f"Zu Entnahme zusammengefasst: {withdrawal} (ID: {withdrawal.id})"
            for trans in transactions:
                trans.match_confidence = "ignored"
                trans.linked_withdrawal = withdrawal
                trans.notes = notes
                trans.processed = True
                trans.save()

            # Delete orphaned single-transaction auto-created withdrawals
            if orphan_ids:
                CompanyWithdrawal.objects.filter(id__in=orphan_ids).exclude(
                    id=withdrawal.id
                ).delete()

            messages.success(
                request,
                ngettext(
                    "%(count)s transaction successfully grouped into withdrawal: %(amount)s €",
                    "%(count)s transactions successfully grouped into withdrawal: %(amount)s €",
                    len(transaction_ids),
                )
                % {"count": len(transaction_ids), "amount": f"{total_amount:.2f}"},
            )
            return redirect("bank_withdrawal_review")

        elif action == "ignore":
            transaction_ids = request.POST.getlist("transactions")
            if not transaction_ids:
                messages.error(request, _("Please select at least one transaction."))
                return redirect("bank_withdrawal_review")

            transactions_qs = BankTransaction.objects.filter(
                id__in=transaction_ids,
                practice=request.current_practice,
            )

            # Delete orphaned auto-created withdrawals before ignoring
            orphan_ids = [
                trans.linked_withdrawal_id
                for trans in transactions_qs
                if trans.linked_withdrawal_id is not None
            ]
            if orphan_ids:
                CompanyWithdrawal.objects.filter(id__in=orphan_ids).delete()

            count = transactions_qs.update(
                match_confidence="ignored",
                notes="Manuell ignoriert",
                processed=True,
                linked_withdrawal=None,
            )

            messages.success(
                request,
                ngettext(
                    "%(count)s transaction ignored.",
                    "%(count)s transactions ignored.",
                    count,
                )
                % {"count": count},
            )
            return redirect("bank_withdrawal_review")

        return redirect("bank_withdrawal_review")
