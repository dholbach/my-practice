"""
Tests for the bank expense and withdrawal review views.
"""

from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from ..models import (
    BankTransaction,
    CompanyExpense,
    ExpenseCategoryRule,
    ExpenseReceipt,
)
from .bank_import_helpers import PRACTICE_IBAN, BankImportViewBase


class BankExpenseReviewViewTest(BankImportViewBase):
    def _make_expense_transaction(self, ref="Ausgabe Ref"):
        return BankTransaction.objects.create(
            practice=self.practice,
            transaction_date=date(2026, 1, 15),
            value_date=date(2026, 1, 15),
            payer_name="Vermieter",
            payer_iban="",
            reference=ref,
            amount=Decimal("-120.00"),
            balance_after=Decimal("880.00"),
            account_iban=PRACTICE_IBAN,
            match_confidence="unmatched",
            processed=False,
        )

    def test_get_loads(self):
        self._make_expense_transaction()
        response = self.http.get(reverse("bank_expense_review"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "my_practice/bank_expense_review.html")
        self.assertContains(response, "Ausgabe Ref")
        self.assertContains(response, "Vermieter")
        self.assertNotContains(response, "Auto-Entnahme")

    def test_empty_state_when_nothing_is_pending(self):
        response = self.http.get(reverse("bank_expense_review"))
        self.assertContains(response, "expense-empty-state")
        self.assertContains(response, "Es gibt keine unzugeordneten negativen Transaktionen.")

    def test_group_creates_expense(self):
        trans = self._make_expense_transaction()
        response = self.http.post(
            reverse("bank_expense_review"),
            {
                "action": "group",
                "transactions": [trans.id],
                "category": "miete",
                "description": "Praxismiete Januar",
            },
        )
        self.assertRedirects(response, reverse("bank_expense_review"))
        self.assertEqual(CompanyExpense.objects.filter(practice=self.practice).count(), 1)
        trans.refresh_from_db()
        self.assertTrue(trans.processed)

    def test_ignore_marks_transactions(self):
        trans = self._make_expense_transaction()
        self.http.post(
            reverse("bank_expense_review"),
            {
                "action": "ignore",
                "transactions": [trans.id],
            },
        )
        trans.refresh_from_db()
        self.assertEqual(trans.match_confidence, "ignored")
        self.assertTrue(trans.processed)

    def test_ignore_deletes_linked_auto_expense(self):
        # An "auto-expense" transaction carries an expense the importer created
        # from a category rule; ignoring it must not leave that in the books.
        expense = CompanyExpense.objects.create(
            practice=self.practice,
            date=date(2026, 1, 15),
            amount=Decimal("120.00"),
            description="Miete",
            category="miete",
        )
        trans = self._make_expense_transaction()
        trans.match_confidence = "auto-expense"
        trans.linked_expense = expense
        trans.save()

        self.http.post(
            reverse("bank_expense_review"),
            {"action": "ignore", "transactions": [trans.id]},
        )
        self.assertFalse(CompanyExpense.objects.filter(id=expense.id).exists())
        trans.refresh_from_db()
        self.assertEqual(trans.match_confidence, "ignored")
        self.assertIsNone(trans.linked_expense)

    def test_group_rejects_unknown_category(self):
        trans = self._make_expense_transaction()
        self.http.post(
            reverse("bank_expense_review"),
            {"action": "group", "transactions": [trans.id], "category": "not-a-category"},
        )
        self.assertFalse(CompanyExpense.objects.filter(practice=self.practice).exists())
        self.assertFalse(ExpenseCategoryRule.objects.filter(practice=self.practice).exists())
        trans.refresh_from_db()
        self.assertFalse(trans.processed)

    def test_group_ignores_transactions_the_page_does_not_list(self):
        # A matched transaction is not on this page; a posted id for it must
        # not regroup it (which would also delete the record it is linked to).
        manual = CompanyExpense.objects.create(
            practice=self.practice,
            date=date(2026, 1, 15),
            amount=Decimal("120.00"),
            description="Miete",
            category="miete",
        )
        trans = self._make_expense_transaction()
        trans.match_confidence = "manual"
        trans.processed = True
        trans.linked_expense = manual
        trans.save()

        self.http.post(
            reverse("bank_expense_review"),
            {"action": "group", "transactions": [trans.id], "category": "miete"},
        )
        self.assertTrue(CompanyExpense.objects.filter(id=manual.id).exists())
        trans.refresh_from_db()
        self.assertEqual(trans.linked_expense, manual)

    def test_ignore_keeps_linked_expense_with_receipts(self):
        # The importer reuses an existing expense with the same date, amount and
        # description, which may be one entered by hand with its receipts.
        expense = CompanyExpense.objects.create(
            practice=self.practice,
            date=date(2026, 1, 15),
            amount=Decimal("120.00"),
            description="Miete",
            category="miete",
        )
        ExpenseReceipt.objects.create(
            expense=expense, file=SimpleUploadedFile("beleg.pdf", b"%PDF-1.4")
        )
        trans = self._make_expense_transaction()
        trans.match_confidence = "auto-expense"
        trans.linked_expense = expense
        trans.save()

        self.http.post(
            reverse("bank_expense_review"),
            {"action": "ignore", "transactions": [trans.id]},
        )
        self.assertTrue(CompanyExpense.objects.filter(id=expense.id).exists())
        trans.refresh_from_db()
        self.assertIsNone(trans.linked_expense)

    def test_group_learns_category_rule_by_name(self):
        trans = self._make_expense_transaction()
        self.http.post(
            reverse("bank_expense_review"),
            {
                "action": "group",
                "transactions": [trans.id],
                "category": "miete",
                "description": "Praxismiete Januar",
            },
        )
        rule = ExpenseCategoryRule.objects.get(practice=self.practice, match_key="name:vermieter")
        self.assertEqual(rule.category, "miete")

    def test_group_learns_one_rule_per_distinct_counterparty(self):
        trans_a = self._make_expense_transaction(ref="Miete Jan")
        trans_b = BankTransaction.objects.create(
            practice=self.practice,
            transaction_date=date(2026, 1, 20),
            value_date=date(2026, 1, 20),
            payer_name="Anderer Vermieter",
            payer_iban="",
            reference="Miete Feb",
            amount=Decimal("-120.00"),
            balance_after=Decimal("760.00"),
            account_iban=PRACTICE_IBAN,
            match_confidence="unmatched",
            processed=False,
        )
        self.http.post(
            reverse("bank_expense_review"),
            {
                "action": "group",
                "transactions": [trans_a.id, trans_b.id],
                "category": "miete",
            },
        )
        self.assertEqual(ExpenseCategoryRule.objects.filter(practice=self.practice).count(), 2)

    def test_group_re_learning_updates_existing_rule(self):
        trans = self._make_expense_transaction()
        ExpenseCategoryRule.objects.create(
            practice=self.practice, match_key="name:vermieter", category="other"
        )
        self.http.post(
            reverse("bank_expense_review"),
            {
                "action": "group",
                "transactions": [trans.id],
                "category": "miete",
            },
        )
        self.assertEqual(ExpenseCategoryRule.objects.filter(practice=self.practice).count(), 1)
        rule = ExpenseCategoryRule.objects.get(practice=self.practice, match_key="name:vermieter")
        self.assertEqual(rule.category, "miete")
