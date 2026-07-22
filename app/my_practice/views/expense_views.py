"""
Views for managing company expenses.
"""

import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from ..forms import CompanyExpenseForm
from ..models import BankTransaction, CompanyExpense, ExpenseReceipt
from ..utils.file_processing import process_upload
from ..utils.financial_list_context_builder import FinancialListContextBuilder
from ..utils.view_helpers import get_year_from_request
from .crud_mixins import (
    NextRedirectMixin,
    PracticeScopedCreateView,
    PracticeScopedDeleteView,
    PracticeScopedUpdateView,
)


def expense_list(request: HttpRequest) -> HttpResponse:
    """List all company expenses with yearly/category summaries"""

    year_filter = get_year_from_request(request, "year", None)
    show_missing = request.GET.get("missing_receipt") == "1"

    queryset = CompanyExpense.objects.for_current_practice(request).prefetch_related("receipts")
    if show_missing:
        queryset = queryset.filter(receipts__isnull=True, has_invoice=False)
    builder = FinancialListContextBuilder(queryset, year_filter=year_filter)

    context, expenses = builder.build_context(include_categories=True, include_tax_deductible=True)

    context["expenses"] = expenses
    context["current_year"] = year_filter or "all"
    context["show_missing"] = show_missing

    return render(request, "my_practice/expense_list.html", context)


class ExpenseCreateView(PracticeScopedCreateView):
    """Create a new expense"""

    model = CompanyExpense
    form_class = CompanyExpenseForm
    template_name = "my_practice/expense_form.html"
    success_url = reverse_lazy("expense_list")
    success_message = gettext_lazy("Expense from {obj.date:%d.%m.%Y} created successfully.")

    def form_valid(self, form: CompanyExpenseForm) -> HttpResponse:  # type: ignore[override]
        response = super().form_valid(form)
        for f in self.request.FILES.getlist("receipts"):
            try:
                ExpenseReceipt.objects.create(expense=self.object, file=process_upload(f))  # type: ignore[misc]
            except ValueError as exc:
                messages.error(self.request, str(exc))
        return response


class ExpenseUpdateView(NextRedirectMixin, PracticeScopedUpdateView):
    """Update an existing expense and manage its receipt attachments."""

    model = CompanyExpense
    form_class = CompanyExpenseForm
    template_name = "my_practice/expense_form.html"
    success_url = reverse_lazy("expense_list")
    success_message = gettext_lazy("Expense from {obj.date:%d.%m.%Y} updated successfully.")
    context_object_name = "expense"

    def form_valid(self, form: CompanyExpenseForm) -> HttpResponse:  # type: ignore[override]
        response = super().form_valid(form)
        for f in self.request.FILES.getlist("receipts"):
            try:
                ExpenseReceipt.objects.create(expense=self.object, file=process_upload(f))
            except ValueError as exc:
                messages.error(self.request, str(exc))
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        expense = self.object

        # Merge candidates: same category, same practice, excluding self
        context["merge_candidates"] = (
            CompanyExpense.objects.for_current_practice(self.request)
            .filter(category=expense.category)
            .exclude(pk=expense.pk)
            .order_by("-date")[:50]
        )
        context["linked_transactions"] = (
            BankTransaction.objects.for_current_practice(self.request)
            .filter(linked_expense=expense)
            .order_by("-transaction_date")
        )

        # Available transactions: unlinked negatives, filtered by search params
        tx_search = self.request.GET.get("tx_search", "").strip()
        tx_year = self.request.GET.get("tx_year", "").strip()
        context["tx_search"] = tx_search
        context["tx_year"] = tx_year

        # Base without linked_expense constraint — search path adds it back selectively.
        _base = (
            BankTransaction.objects.for_current_practice(self.request)
            .filter(
                matched_invoice__isnull=True,
                amount__lt=0,
            )
            .order_by("-transaction_date")
        )

        # Strictly free rows (used for the default / no-search view)
        base_qs = _base.filter(
            linked_expense__isnull=True,
            linked_withdrawal__isnull=True,
        )

        if tx_search:
            # Search also surfaces auto-expense stubs (mis-classified by bank import) and
            # auto-withdrawals so the user can re-route them to the correct expense.
            available_qs = (
                _base.filter(
                    Q(linked_expense__isnull=True)
                    | Q(match_confidence=BankTransaction.Confidence.AUTO_EXPENSE)
                    | Q(match_confidence=BankTransaction.Confidence.AUTO_WITHDRAWAL)
                )
                .exclude(
                    linked_expense=expense  # already linked here — no need to show again
                )
                .filter(Q(payer_name__icontains=tx_search) | Q(reference__icontains=tx_search))
            )
            if tx_year:
                available_qs = available_qs.filter(transaction_date__year=tx_year)
            context["available_transactions"] = available_qs[:50]
        else:
            # Without a search term: exclude withdrawals/contributions so they don't
            # clutter the default view.  Users can still find them by searching.
            expense_qs = base_qs.filter(linked_withdrawal__isnull=True).exclude(
                match_confidence__in=[
                    BankTransaction.Confidence.AUTO_WITHDRAWAL,
                    BankTransaction.Confidence.AUTO_CONTRIBUTION,
                ]
            )
            if tx_year:
                expense_qs = expense_qs.filter(transaction_date__year=tx_year)
                context["available_transactions"] = expense_qs[:50]
            else:
                # Default: show nearby transactions (±45 days of expense date)
                delta = datetime.timedelta(days=45)
                context["available_transactions"] = expense_qs.filter(
                    transaction_date__range=(expense.date - delta, expense.date + delta)
                )[:50]

        return context


class ExpenseDeleteView(NextRedirectMixin, PracticeScopedDeleteView):
    """Delete an expense"""

    model = CompanyExpense
    template_name = "my_practice/expense_confirm_delete.html"
    success_url = reverse_lazy("expense_list")
    context_object_name = "expense"
    success_message = gettext_lazy(
        "Expense from {obj.date:%d.%m.%Y} of {obj.amount}€ deleted successfully."
    )


def _sync_expense_amount(expense: CompanyExpense) -> None:
    """Recalculate and save expense amount from its linked bank transactions.

    If at least one transaction is linked, sets expense.amount to the sum of
    absolute transaction amounts. If no transactions are linked, leaves the
    amount unchanged so a manually-entered amount is not wiped out.
    """
    linked = list(expense.bank_transactions.values_list("amount", flat=True))
    if linked:
        expense.amount = sum(abs(a) for a in linked)
        expense.save(update_fields=["amount"])


@login_required
@require_POST
def expense_receipt_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a single receipt attachment from an expense."""
    receipt = get_object_or_404(ExpenseReceipt, pk=pk)
    if receipt.expense.practice != request.current_practice:
        raise PermissionDenied
    expense_pk = receipt.expense_id
    receipt.file.delete(save=False)
    receipt.delete()
    messages.success(request, _("Receipt deleted successfully."))
    return redirect("expense_update", pk=expense_pk)


@login_required
@require_POST
def expense_link_transaction(request: HttpRequest, pk: int) -> HttpResponse:
    """Link a bank transaction to this expense and sync the expense amount."""
    expense = get_object_or_404(CompanyExpense, pk=pk)
    if expense.practice != request.current_practice:
        raise PermissionDenied
    transaction_id = request.POST.get("transaction_id")
    transaction = get_object_or_404(
        BankTransaction.objects.for_current_practice(request), pk=transaction_id
    )
    # Clean up any auto-created stub that this transaction was previously linked to.
    if transaction.linked_expense_id and transaction.linked_expense_id != expense.pk:
        old_expense = transaction.linked_expense
        if transaction.match_confidence == BankTransaction.Confidence.AUTO_EXPENSE:
            transaction.linked_expense = None
            transaction.save(update_fields=["linked_expense"])
            # Delete the stub only if it has no receipts and no other transactions.
            if not old_expense.receipts.exists() and not old_expense.bank_transactions.exists():
                old_expense.delete()

    if transaction.linked_withdrawal_id:
        old_withdrawal = transaction.linked_withdrawal
        transaction.linked_withdrawal = None
        transaction.save(update_fields=["linked_withdrawal"])
        remaining = old_withdrawal.bank_transactions.count()
        if (
            remaining == 0
            and transaction.match_confidence == BankTransaction.Confidence.AUTO_WITHDRAWAL
        ):
            old_withdrawal.delete()

    transaction.linked_expense = expense
    transaction.match_confidence = BankTransaction.Confidence.MANUAL
    transaction.save()

    _sync_expense_amount(expense)

    messages.success(
        request,
        _("Transaction from %(date)s (%(payer)s) linked.")
        % {
            "date": transaction.transaction_date.strftime("%d.%m.%Y"),
            "payer": transaction.payer_name,
        },
    )
    return redirect("expense_update", pk=pk)


@login_required
@require_POST
def expense_merge(request: HttpRequest, pk: int) -> HttpResponse:
    """Merge a source expense into this (target) expense.

    Moves all bank transactions and receipts from source → target, recalculates
    the target amount from its linked transactions (or adds amounts when none are
    linked), then deletes the source.
    """
    from django.db import transaction as db_transaction

    target = get_object_or_404(CompanyExpense, pk=pk)
    if target.practice != request.current_practice:
        raise PermissionDenied

    source_pk = request.POST.get("source_id")
    source = get_object_or_404(CompanyExpense, pk=source_pk, practice=request.current_practice)

    if source.pk == target.pk:
        messages.error(request, _("Source and target must not be identical."))
        return redirect("expense_update", pk=pk)

    with db_transaction.atomic():
        # Capture state BEFORE moving source's transactions, so the post-merge
        # amount calculation knows which amounts were manual vs. transaction-backed.
        target_had_transactions = target.bank_transactions.exists()
        target_original_amount = target.amount

        moved_txns = source.bank_transactions.count()
        source.bank_transactions.update(linked_expense=target)

        moved_receipts = source.receipts.count()
        source.receipts.update(expense=target)

        if target.bank_transactions.exists():
            # At least one side had bank transactions — sync from all linked amounts.
            _sync_expense_amount(target)
            if not target_had_transactions:
                # Target was manual-only before the merge; its original amount is not
                # captured by the transaction sync, so add it on top.
                target.amount += target_original_amount
                target.save(update_fields=["amount"])
        else:
            # Neither side had linked transactions — sum the manually entered amounts.
            target.amount = target_original_amount + source.amount
            target.save(update_fields=["amount"])

        source.delete()

    messages.success(
        request,
        _("Expense merged: %(txns)s transaction(s) and %(receipts)s receipt(s) taken over.")
        % {"txns": moved_txns, "receipts": moved_receipts},
    )
    return redirect("expense_update", pk=pk)


@login_required
@require_POST
def expense_unlink_transaction(request: HttpRequest, pk: int, transaction_pk: int) -> HttpResponse:
    """Remove the link between a bank transaction and this expense and sync the amount."""
    expense = get_object_or_404(CompanyExpense, pk=pk)
    if expense.practice != request.current_practice:
        raise PermissionDenied
    transaction = get_object_or_404(
        BankTransaction.objects.for_current_practice(request),
        pk=transaction_pk,
        linked_expense=expense,
    )
    transaction.linked_expense = None
    transaction.save()

    _sync_expense_amount(expense)

    messages.success(
        request,
        _("Link with transaction from %(date)s removed.")
        % {"date": transaction.transaction_date.strftime("%d.%m.%Y")},
    )
    return redirect("expense_update", pk=pk)
